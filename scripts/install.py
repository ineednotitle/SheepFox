#!/usr/bin/env python3
"""
(SheepFox) Firefox — Cross-Platform Drop-In Installer & Profile Manager
Applies SheepFox speed & privacy configurations to stock Mozilla Firefox:
  1. Per-profile `user.js` (+ optional personal or `--strict` overrides)
  2. Per-profile UI theme: `chrome/userChrome.css` + `chrome/userContent.css`
     (the floating Zen/Arc-style new-tab search pill; skip with --no-ui)
  3. Optional `--system` AutoConfig (`sheepfox.cfg` + `local-settings.js`)
     and SheepShields Enterprise Policy (`distribution/policies.json` with uBlock Origin)
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import re
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_JS_SRC = REPO_ROOT / "config" / "user.js"
STRICT_OVERRIDE_SRC = REPO_ROOT / "config" / "overrides" / "strict-paranoia.override.js"
LOW_MEMORY_OVERRIDE_SRC = REPO_ROOT / "config" / "overrides" / "low-memory.override.js"
CUSTOM_OVERRIDE_SRC = REPO_ROOT / "config" / "overrides" / "user-overrides.js"
POLICIES_SRC = REPO_ROOT / "config" / "distribution" / "policies.json"
AUTOCONFIG_CFG_SRC = REPO_ROOT / "config" / "autoconfig" / "sheepfox.cfg"
LOCAL_SETTINGS_SRC = REPO_ROOT / "config" / "autoconfig" / "defaults" / "pref" / "local-settings.js"
CHROME_SRC_DIR = REPO_ROOT / "config" / "chrome"
#: Profile-level CSS: the floating new-tab search pill (Zen/Arc style)
UI_FILES = ("userChrome.css", "userContent.css")
#: Optional probe that userChrome.css @imports; proves the stylesheet is read.
PROBE_FILE = "sheepfox-probe.css"
PROBE_CSS = """/* (SheepFox) CSS load probe.
   Written by `install.py --probe`, removed by `--unprobe`.
   If the toolbar of a new Firefox window is RED, Firefox is definitely reading
   userChrome.css from this profile; if it is not, the stylesheet is not being
   loaded at all (wrong profile, pref off, or Firefox was never restarted). */
#nav-bar {
  background: #cc0000 !important;
}
#urlbar {
  outline: 3px solid #00ff88 !important;
  outline-offset: -3px !important;
}
"""


def candidate_profile_roots() -> list[Path]:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        roots = [appdata / "Mozilla" / "Firefox"]
        # Microsoft Store (MSIX) builds redirect AppData, so their profile is
        # NOT under %APPDATA%. This is the single most common reason a userChrome
        # theme "does nothing" on Windows.
        packages = local / "Packages"
        if packages.is_dir():
            for package in sorted(packages.glob("Mozilla.Firefox_*")):
                roots.append(package / "LocalCache" / "Roaming" / "Mozilla" / "Firefox")
        # Portable / hand-unpacked builds keep the profile next to the binary.
        for base in ("ProgramFiles", "ProgramFiles(x86)"):
            program_files = Path(os.environ.get(base, ""))
            if str(program_files) and program_files.is_dir():
                roots.append(program_files / "Mozilla Firefox" / "profile")
        return roots
    if system == "Darwin":
        return [home / "Library" / "Application Support" / "Firefox"]
    # Linux / BSD (Standard, Flatpak, Snap)
    return [
        home / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
    ]


def candidate_system_firefox_dirs() -> list[Path]:
    system = platform.system()
    if system == "Windows":
        return [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Mozilla Firefox",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Mozilla Firefox",
        ]
    if system == "Darwin":
        return [Path("/Applications/Firefox.app/Contents/Resources")]
    return [
        Path("/usr/lib/firefox"),
        Path("/usr/lib64/firefox"),
        Path("/usr/lib/firefox-esr"),
        Path("/opt/firefox"),
        # Flatpak (system + per-user) and Snap keep the real install tree here
        Path("/var/lib/flatpak/app/org.mozilla.firefox/current/active/files/lib/firefox"),
        Path.home() / ".local/share/flatpak/app/org.mozilla.firefox/current/active/files/lib/firefox",
        Path("/snap/firefox/current/usr/lib/firefox"),
    ]


def read_install_defaults(root: Path) -> list[Path]:
    """Profiles named by installs.ini — what Firefox actually opens."""
    ini_path = root / "installs.ini"
    if not ini_path.exists():
        return []
    parser = configparser.RawConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except configparser.Error:
        return []
    found = []
    for section in parser.sections():
        # installs.ini is [Install<hash>] -> Default=<profile path, relative>.
        if section == "General" or not parser.has_option(section, "Default"):
            continue
        candidate = (root / parser.get(section, "Default")).resolve()
        if candidate.is_dir():
            found.append(candidate)
    return found


def iter_profile_dirs() -> list[Path]:
    """Every profile directory that exists on this machine, any install type."""
    dirs: list[Path] = []
    for root in candidate_profile_roots():
        ini_path = root / "profiles.ini"
        if not ini_path.exists():
            continue
        parser = configparser.RawConfigParser()
        try:
            parser.read(ini_path, encoding="utf-8")
        except configparser.Error:
            continue
        for section in parser.sections():
            if not section.startswith("Profile") or not parser.has_option(section, "Path"):
                continue
            raw_path = parser.get(section, "Path")
            is_rel = parser.get(section, "IsRelative", fallback="1") == "1"
            prof_dir = (root / raw_path).resolve() if is_rel else Path(raw_path).resolve()
            if prof_dir.is_dir() and prof_dir not in dirs:
                dirs.append(prof_dir)
    return dirs


def detect_default_profile() -> Path | None:
    for root in candidate_profile_roots():
        # installs.ini wins: it is the install -> profile mapping Firefox itself
        # uses, so it is the only reliable answer when several profiles exist.
        for candidate in read_install_defaults(root):
            return candidate
        ini_path = root / "profiles.ini"
        if not ini_path.exists():
            continue
        parser = configparser.RawConfigParser()
        parser.read(ini_path, encoding="utf-8")

        # Prefer active [Install...] Default entry first (Firefox 67+)
        for section in parser.sections():
            if section.startswith("Install") and parser.has_option(section, "Default"):
                rel = parser.get(section, "Default")
                candidate = (root / rel).resolve()
                if candidate.is_dir():
                    return candidate

        # Fallback to [Profile...] with Default=1 or default-release suffix
        fallback = None
        for section in parser.sections():
            if not section.startswith("Profile") or not parser.has_option(section, "Path"):
                continue
            raw_path = parser.get(section, "Path")
            is_rel = parser.get(section, "IsRelative", fallback="1") == "1"
            prof_dir = (root / raw_path).resolve() if is_rel else Path(raw_path).resolve()
            if not prof_dir.is_dir():
                continue
            if parser.get(section, "Default", fallback="0") == "1":
                return prof_dir
            if prof_dir.name.endswith(".default-release") or fallback is None:
                fallback = prof_dir
        if fallback:
            return fallback
    return None


def all_profiles() -> list[Path]:
    """Every Firefox profile on this machine, across every install type.

    Installing into all of them removes profile detection as a failure mode:
    the CSS lands wherever Firefox actually happens to run.
    """
    found: list[Path] = []
    for root in candidate_profile_roots():
        for candidate in read_install_defaults(root):
            if candidate not in found:
                found.append(candidate)
    default = detect_default_profile()
    if default and default not in found:
        found.insert(0, default)
    for candidate in iter_profile_dirs():
        if candidate not in found:
            found.append(candidate)
    return found


def detect_system_firefox_dir() -> Path | None:
    for path in candidate_system_firefox_dirs():
        if path.is_dir():
            return path
    return None


def read_firefox_version(firefox_dir: Path | None) -> str:
    """Read Version= out of <install>/application.ini (best effort)."""
    if not firefox_dir:
        return "unknown"
    ini = firefox_dir / "application.ini"
    if not ini.is_file():
        return "unknown"
    for line in ini.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("Version="):
            return line.split("=", 1)[1].strip()
    return "unknown"


def pref_value_from_prefs_js(profile_dir: Path, name: str) -> object | None:
    """Return the value Firefox last saved for *name* in prefs.js, else None."""
    prefs_js = profile_dir / "prefs.js"
    if not prefs_js.is_file():
        return None
    pattern = re.compile(r'^user_pref\("' + re.escape(name) + r'",\s*(.+?)\);\s*$', re.MULTILINE)
    match = pattern.search(prefs_js.read_text(encoding="utf-8", errors="replace"))
    if not match:
        return None
    raw = match.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip('"')


def css_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""


def doctor(profile_dir: Path | None, firefox_dir: Path | None) -> int:
    """Explain whether the floating-search UI can load, and why not."""
    print("=== (SheepFox) Firefox doctor ===")
    version = read_firefox_version(firefox_dir)
    if firefox_dir:
        print(f"  install   : {firefox_dir}")
        print(f"  version   : {version}")
    else:
        print("  install   : not detected (pass --firefox-dir)")

    failures = 0

    def report(ok: bool, label: str, detail: str = "") -> None:
        nonlocal failures
        if not ok:
            failures += 1
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {label}{(' -> ' + detail) if detail else ''}")

    if not profile_dir:
        print("  [FAIL] no Firefox profile found (launch Firefox once, or pass --profile)")
        failures += 1
        return 1

    print(f"  profile   : {profile_dir}   <- Firefox is launched with this one")

    user_js = profile_dir / "user.js"
    report(user_js.is_file(), "user.js present")
    if user_js.is_file():
        text = user_js.read_text(encoding="utf-8", errors="replace")
        report(
            'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);' in text,
            "user.js enables userChrome.css",
        )

    chrome_dir = profile_dir / "chrome"
    for name, minimum in (("userChrome.css", 2000), ("userContent.css", 400)):
        target = chrome_dir / name
        size = target.stat().st_size if target.is_file() else 0
        report(target.is_file() and size >= minimum, f"chrome/{name}", f"{size} bytes")

    # Is the copy in the profile the same file the repo ships? A stale copy from
    # an older version is a classic "the CSS is there but nothing changed".
    for name in UI_FILES:
        src = CHROME_SRC_DIR / name
        dst = chrome_dir / name
        if src.is_file() and dst.is_file():
            same = css_hash(src) == css_hash(dst)
            report(same, f"chrome/{name} matches this repo", "stale - re-run the installer" if not same else "")

    probe = chrome_dir / PROBE_FILE
    if probe.is_file():
        print(f"  [info] probe active: {probe} (run --unprobe once you have looked at the toolbar)")

    saved = pref_value_from_prefs_js(profile_dir, "toolkit.legacyUserProfileCustomizations.stylesheets")
    if saved is None:
        print("  [info] prefs.js has no saved value yet; Firefox will take it from user.js on next start")
    elif saved is True:
        report(True, "pref saved as true")
    else:
        report(False, "pref saved as false", "set it to true in about:config, or reinstall")
        print("         (a stale user.js or another hardening tool may have set it false)")

    # Catch the number-one cause: SheepFox was installed into a profile that
    # Firefox never opens (Store build, portable build, second profile, ...).
    others = [d for d in iter_profile_dirs() if d.resolve() != profile_dir.resolve()]
    stray = [d for d in others if (d / "chrome" / "userChrome.css").is_file() or (d / "user.js").is_file()]
    if stray:
        print()
        print("  [WARN] Other Firefox profiles on this machine also have SheepFox files:")
        for d in stray:
            print(f"         {d}")
        print("         Only the profile above is used at launch. Install into it:")
        print(f"           python3 scripts/install.py --profile \"{profile_dir}\"")
    if others and not stray:
        print()
        print(f"  [info] {len(others)} other profile(s) found, none of them modified.")

    # The system half (policies.json + AutoConfig) is optional: a plain
    # per-profile install leaves a Firefox folder completely untouched, so an
    # absent file there is not a problem - only an opportunity.
    if firefox_dir:
        system_files = ("sheepfox.cfg", "defaults/pref/local-settings.js", "distribution/policies.json")
        installed = [rel for rel in system_files if (firefox_dir / rel).is_file()]
        for rel in installed:
            report(True, f"system {rel}")
        if not installed:
            print("  [info] no system install here (--system is optional):")
            print("         policies.json + AutoConfig are what lock uBlock Origin and the shields.")
            print("         add them with:  python3 scripts/install.py --system")

    print()
    if failures:
        print(f"  {failures} problem(s) found. Fix the FAIL lines above, then restart Firefox.")
        print("  Full reinstall:  python3 scripts/install.py [--profile DIR] [--system]")
        return 1

    print("  Files are in place. To prove Firefox is actually reading the stylesheet:")
    print("    1. python3 scripts/install.py --probe")
    print("    2. QUIT Firefox completely (Task Manager -> no firefox.exe), then start it.")
    print("    3. Open a new tab. The toolbar turns RED and the pill gets a green outline")
    print("       if the CSS is loaded. Nothing changes if it is not.")
    print("    4. python3 scripts/install.py --unprobe")
    print("  If the toolbar stays dark, the profile above is not the one Firefox runs:")
    print("    open about:support in Firefox and compare 'Profile Folder' with the path")
    print("    printed at the top of this report, then reinstall with --profile <that path>.")
    return 0


def compose_user_js(strict: bool, low_memory: bool = False) -> str:
    content = USER_JS_SRC.read_text(encoding="utf-8")
    if strict:
        content += "\n\n" + STRICT_OVERRIDE_SRC.read_text(encoding="utf-8")
    if low_memory:
        content += "\n\n" + LOW_MEMORY_OVERRIDE_SRC.read_text(encoding="utf-8")
    if CUSTOM_OVERRIDE_SRC.exists():
        content += "\n\n// --- Personal User Overrides ---\n"
        content += CUSTOM_OVERRIDE_SRC.read_text(encoding="utf-8")
    return content.rstrip() + "\n"


def backup_and_write(dest: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f"  [DRY-RUN] Would write {dest} ({len(content)} bytes)")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = dest.with_name(f"{dest.name}.sheepfox-backup-{stamp}")
        shutil.copy2(dest, bak)
        print(f"  [BACKUP] Saved existing file to {bak}")
    dest.write_text(content, encoding="utf-8")
    print(f"  [WRITE]  Installed {dest}")


def _uninstall_profile(profile: Path, dry_run: bool) -> None:
    for target in [profile / "user.js"] + [profile / "chrome" / name for name in (*UI_FILES, PROBE_FILE)]:
        if not target.exists():
            continue
        if dry_run:
            print(f"  [DRY-RUN] Would remove {target}")
        else:
            target.unlink()
            print(f"  [REMOVE] Removed {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Install (SheepFox) Firefox speed & privacy suite.")
    parser.add_argument("--profile", type=Path, help="Explicit path to target Firefox profile directory.")
    parser.add_argument("--firefox-dir", type=Path, help="Explicit path to Firefox binary installation folder.")
    parser.add_argument("--system", action="store_true", help="Also install policies.json (uBlock Origin) & AutoConfig.")
    parser.add_argument("--strict", action="store_true", help="Append strict anti-fingerprinting (RFP) overrides.")
    parser.add_argument(
        "--low-memory",
        action="store_true",
        help="Append the low-memory override (fewer content processes; disables Fission isolation).",
    )
    parser.add_argument("--uninstall", action="store_true", help="Remove SheepFox files from target profile/system.")
    parser.add_argument("--dry-run", action="store_true", help="Preview installation paths without modifying disk.")
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Diagnose why the floating-search UI (or the install) is not taking effect.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        nargs="?",
        const=Path("sheepfox-report.txt"),
        help="Write a full diagnostic report to a file (default: ./sheepfox-report.txt).",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Write chrome/sheepfox-probe.css (red toolbar) to prove userChrome.css is loading.",
    )
    parser.add_argument(
        "--unprobe",
        action="store_true",
        help="Remove the file written by --probe.",
    )
    parser.add_argument(
        "--no-ui",
        action="store_true",
        help="Skip the chrome/userChrome.css + userContent.css floating-search theme.",
    )
    args = parser.parse_args()

    profile_dir = args.profile.resolve() if args.profile else detect_default_profile()
    firefox_dir = args.firefox_dir.resolve() if args.firefox_dir else detect_system_firefox_dir()
    # With no explicit --profile, install into EVERY profile that exists. Profile
    # detection is the number-one reason a userChrome theme silently does
    # nothing (Store builds, portable builds, a second profile).
    targets = [profile_dir] if args.profile else all_profiles()
    if targets and profile_dir is None:
        profile_dir = targets[0]

    if args.profile and not profile_dir.is_dir():
        print(f"[ERROR] Profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 1
    if args.firefox_dir and not firefox_dir.is_dir():
        print(f"[ERROR] Firefox directory does not exist: {firefox_dir}", file=sys.stderr)
        return 1

    print("=== (SheepFox) Firefox Installer ===")
    if len(targets) > 1:
        print(f"Detected Profiles: {len(targets)} (installing into all of them)")
        for target in targets:
            print(f"                 - {target}")
    else:
        print(f"Detected Profile : {profile_dir if profile_dir else 'Not found (pass --profile <dir>)'}")
    print(f"Detected System  : {firefox_dir if firefox_dir else 'Not found (pass --firefox-dir <dir>)'}")

    if args.report is not None:
        import contextlib
        import io as _io

        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            print("=== (SheepFox) Firefox report ===")
            print(f"platform     : {platform.platform()}")
            print(f"repo         : {REPO_ROOT}")
            print(f"firefox dir  : {firefox_dir}")
            print(f"firefox ver  : {read_firefox_version(firefox_dir)}")
            print("profiles found:")
            for candidate in all_profiles():
                print(f"  - {candidate}")
            print()
            code = doctor(profile_dir, firefox_dir)
        text = buffer.getvalue()
        destination = args.report if args.report.is_absolute() else Path.cwd() / args.report
        destination.write_text(text + f"\nexit_code={code}\n", encoding="utf-8")
        print(text)
        print(f"[REPORT] Written to {destination}")
        print("         Paste that file (or its contents) into the issue/chat.")
        return code

    if args.doctor:
        return doctor(profile_dir, firefox_dir)

    if args.probe or args.unprobe:
        targets = [t for t in targets if t.is_dir()]
        if not targets:
            print("[ERROR] No profile to write the probe into. Pass --profile <dir>.", file=sys.stderr)
            return 1
        for target in targets:
            probe_path = target / "chrome" / PROBE_FILE
            if args.unprobe:
                if probe_path.exists():
                    if args.dry_run:
                        print(f"  [DRY-RUN] Would remove {probe_path}")
                    else:
                        probe_path.unlink()
                        print(f"  [REMOVE] Removed {probe_path}")
                else:
                    print(f"  [INFO]   No probe file present in {target}")
                continue
            backup_and_write(probe_path, PROBE_CSS, dry_run=args.dry_run)
        if args.unprobe:
            return 0
        if not args.dry_run:
            print("\n  Now QUIT Firefox completely (Task Manager -> no firefox.exe), start it and")
            print("  open a new tab: a RED toolbar + green pill outline means the CSS is loading.")
            print("  Remove it with:  python3 scripts/install.py --unprobe")
        return 0

    if args.uninstall:
        for target_profile in [t for t in targets if t.is_dir()]:
            _uninstall_profile(target_profile, args.dry_run)
        if args.system and firefox_dir:
            for rel in ["sheepfox.cfg", "defaults/pref/local-settings.js", "distribution/policies.json"]:
                target = firefox_dir / rel
                if target.exists():
                    if args.dry_run:
                        print(f"  [DRY-RUN] Would remove {target}")
                    else:
                        target.unlink()
                        print(f"  [REMOVE] Removed {target}")
        return 0

    if profile_dir and not profile_dir.is_dir() and not args.dry_run:
        print(f"[ERROR] Profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 1

    if not profile_dir and not args.system:
        if args.dry_run:
            print("[INFO] Dry-run completed (no Firefox profile currently exists on this machine).")
            return 0
        print("[ERROR] Could not auto-detect a Firefox profile. Launch Firefox once or pass --profile <path>.", file=sys.stderr)
        return 1

    payload = compose_user_js(strict=args.strict, low_memory=args.low_memory)
    for target in [t for t in targets if t.is_dir()]:
        if len(targets) > 1:
            print(f"\n  -> {target}")
        backup_and_write(target / "user.js", payload, dry_run=args.dry_run)

        if args.no_ui:
            print("  [SKIP]   UI theme skipped (--no-ui)")
            continue
        for name in UI_FILES:
            src = CHROME_SRC_DIR / name
            if not src.is_file():
                print(f"  [WARN]   Missing UI asset: {src}")
                continue
            backup_and_write(target / "chrome" / name, src.read_text(encoding="utf-8"), args.dry_run)

    if args.system:
        if not firefox_dir:
            print("[ERROR] Could not locate Firefox installation directory. Pass --firefox-dir <path>.", file=sys.stderr)
            return 1
        backup_and_write(firefox_dir / "sheepfox.cfg", AUTOCONFIG_CFG_SRC.read_text(encoding="utf-8"), args.dry_run)
        backup_and_write(
            firefox_dir / "defaults" / "pref" / "local-settings.js",
            LOCAL_SETTINGS_SRC.read_text(encoding="utf-8"),
            args.dry_run,
        )
        backup_and_write(
            firefox_dir / "distribution" / "policies.json",
            POLICIES_SRC.read_text(encoding="utf-8"),
            args.dry_run,
        )

    print("\n[DONE] Restart Firefox to activate (SheepFox) speed & privacy protections!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
