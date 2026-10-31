#!/usr/bin/env python3
"""
(SheepFox) Firefox — Cross-Platform Drop-In Installer & Profile Manager
Applies SheepFox speed & privacy configurations to stock Mozilla Firefox:
  1. Per-profile `user.js` (+ optional personal or `--strict` overrides)
  2. SheepShields Enterprise Policy (`distribution/policies.json`), which
     preinstalls uBlock Origin + Decentraleyes and locks the privacy defaults
  3. Optional `--system` AutoConfig (`sheepfox.cfg` + `local-settings.js`)

SheepFox does not style Firefox's browser UI: the profile only ever receives a
`user.js`, so the interface stays exactly the one Mozilla ships.
"""

from __future__ import annotations

import argparse
import configparser
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
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
#: Files older SheepFox releases (<= 1.2) wrote into the profile's `chrome/`
#: directory for the floating-search theme. That theme is gone; `--uninstall`
#: and the doctor still recognise these so an upgrade cleans up after itself.
LEGACY_UI_FILES = ("userChrome.css", "userContent.css", "sheepfox-probe.css")
#: Extensions SheepShields preinstalls through the policy file. The names are
#: only used for the human-readable log lines.
SHEEPFOX_EXTENSIONS = {
    "uBlock0@raymondhill.net": "uBlock Origin",
    "jid1-BoFifL9Vbdl2zQ@jetpack": "Decentraleyes",
}
def candidate_profile_roots() -> list[Path]:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        roots = [appdata / "Mozilla" / "Firefox"]
        # Microsoft Store (MSIX) builds redirect AppData, so their profile is
        # NOT under %APPDATA%. This is the single most common reason a per-profile
        # install "does nothing" on Windows.
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
    the config lands wherever Firefox actually happens to run.
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


def doctor(profile_dir: Path | None, firefox_dir: Path | None) -> int:
    """Explain whether the SheepFox config is installed, and why not."""
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
        count = text.count("user_pref(")
        report(count >= 100, "user.js carries the SheepFox prefs", f"{count} user_pref lines")

    # SheepFox <= 1.2 also installed a floating-search stylesheet. It is gone,
    # but a profile upgraded from that version still has the file: say so once,
    # and point at the one command that removes it.
    leftovers = [path for path in (profile_dir / "chrome" / name for name in LEGACY_UI_FILES) if path.is_file()]
    if leftovers:
        print("  [info] this profile still has files from the retired search-bar theme:")
        for path in leftovers:
            print(f"         {path}")
        print("         the theme is no longer shipped - drop it with:  python3 scripts/install.py --uninstall")

    # Catch the number-one cause: SheepFox was installed into a profile that
    # Firefox never opens (Store build, portable build, second profile, ...).
    others = [d for d in iter_profile_dirs() if d.resolve() != profile_dir.resolve()]
    stray = [d for d in others if (d / "user.js").is_file()]
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
            print("         policies.json preinstalls uBlock Origin + Decentraleyes and locks the shields.")
            print("         add them with:  python3 scripts/install.py --system")
        policy_file = firefox_dir / "distribution" / "policies.json"
        if policy_file.is_file():
            try:
                policy_data = json.loads(policy_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                print(f"  [FAIL] distribution/policies.json parses -> {error}")
                failures += 1
            else:
                ids = set(policy_data.get("policies", {}).get("ExtensionSettings", {}))
                missing = [name for extension_id, name in SHEEPFOX_EXTENSIONS.items() if extension_id not in ids]
                if missing:
                    print(f"  [info] extension preinstall skipped for: {', '.join(missing)}")
                    print("         re-run the installer without --no-extensions to add them")
                else:
                    report(True, "extension preinstall (uBlock Origin + Decentraleyes)")

    print()
    if failures:
        print(f"  {failures} problem(s) found. Fix the FAIL lines above, then restart Firefox.")
        print("  Full reinstall:  python3 scripts/install.py [--profile DIR] [--system]")
        return 1

    print("  Files are in place. Quit Firefox completely, then start it again.")
    print("  If nothing changed, the profile above is probably not the one Firefox runs:")
    print("    open about:support in Firefox, compare 'Profile Folder' with the path")
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


def render_policies(include_extensions: bool = True) -> str:
    """The SheepShields policy, optionally without the extension entries."""
    policy = json.loads(POLICIES_SRC.read_text(encoding="utf-8"))
    if not include_extensions:
        settings = policy["policies"].get("ExtensionSettings", {})
        for extension_id in SHEEPFOX_EXTENSIONS:
            settings.pop(extension_id, None)
        managed = policy["policies"].get("3rdparty", {}).get("Extensions", {})
        for extension_id in SHEEPFOX_EXTENSIONS:
            managed.pop(extension_id, None)
    return json.dumps(policy, indent=2, ensure_ascii=False) + "\n"


def _elevated_copy(target: Path, content: str) -> bool:
    """Install *target* with administrator rights, staging it as the user first.

    Returns False when no elevation path is available, so the caller can print an
    actionable instruction instead of raising.
    """
    staged = Path(tempfile.mkdtemp(prefix="sheepfox-policy-")) / target.name
    staged.write_text(content, encoding="utf-8")
    parent = shlex.quote(str(target.parent))
    source = shlex.quote(str(staged))
    destination = shlex.quote(str(target))

    if sys.platform == "darwin" and shutil.which("osascript"):
        script = f"/bin/mkdir -p {parent} && /bin/cp {source} {destination} && /bin/chmod 644 {destination}"
        result = subprocess.run(
            ["osascript", "-e", f'do shell script "{script}" with administrator privileges'],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.returncode == 0

    if shutil.which("sudo") and sys.stdin.isatty():
        result = subprocess.run(
            ["sudo", "install", "-D", "-m", "644", str(staged), str(target)],
            check=False,
        )
        return result.returncode == 0
    return False


def install_policy(firefox_dir: Path, include_extensions: bool, dry_run: bool) -> bool:
    """Write <firefox>/distribution/policies.json, elevating only if needed."""
    target = firefox_dir / "distribution" / "policies.json"
    content = render_policies(include_extensions)
    if dry_run:
        print(f"  [DRY-RUN] Would write {target} ({len(content)} bytes)")
        return True
    try:
        backup_and_write(target, content, dry_run=False)
    except (PermissionError, OSError):
        if not _elevated_copy(target, content):
            print(f"  [WARN]   Could not write {target} (administrator rights required).")
            print("           Run the installer once as an administrator:")
            print("             sudo python3 scripts/install.py --system")
            print(f"           or copy distribution/policies.json into {firefox_dir}")
            return False
        print(f"  [WRITE]  Installed {target} (as administrator)")
    if include_extensions:
        names = " + ".join(SHEEPFOX_EXTENSIONS.values())
        print(f"  [OK]     SheepShields policy preinstalls {names} on the next start")
    else:
        print("  [SKIP]   Extension preinstall disabled (--no-extensions)")
    return True


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
    # user.js, plus the leftovers of the retired search-bar theme (<= 1.2) so an
    # upgrade from that version really does leave a pristine profile.
    for target in [profile / "user.js"] + [profile / "chrome" / name for name in LEGACY_UI_FILES]:
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
    parser.add_argument(
        "--system",
        action="store_true",
        help="Also install the AutoConfig files (the SheepShields policy is installed anyway).",
    )
    parser.add_argument(
        "--no-extensions",
        dest="extensions",
        action="store_false",
        help="Do not preinstall uBlock Origin + Decentraleyes (keeps the rest of the policy).",
    )
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
        help="Diagnose why the install is not taking effect (wrong profile, stale user.js).",
    )
    parser.add_argument(
        "--report",
        type=Path,
        nargs="?",
        const=Path("sheepfox-report.txt"),
        help="Write a full diagnostic report to a file (default: ./sheepfox-report.txt).",
    )
    args = parser.parse_args()

    profile_dir = args.profile.resolve() if args.profile else detect_default_profile()
    firefox_dir = args.firefox_dir.resolve() if args.firefox_dir else detect_system_firefox_dir()
    # With no explicit --profile, install into EVERY profile that exists. Profile
    # detection is the number-one reason an install silently does nothing
    # (Store builds, portable builds, a second profile).
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

    if args.uninstall:
        for target_profile in [t for t in targets if t.is_dir()]:
            _uninstall_profile(target_profile, args.dry_run)
        # Mirrors the install rule: a plain run wrote the policy, so a plain
        # --uninstall has to remove it again.
        if (args.system or not args.profile) and firefox_dir:
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
        # A profile upgraded from <= 1.2 still carries the retired theme. Leaving
        # it behind would be a stylesheet nothing maintains any more.
        for name in LEGACY_UI_FILES:
            stale = target / "chrome" / name
            if stale.is_file():
                if args.dry_run:
                    print(f"  [DRY-RUN] Would remove retired theme file {stale}")
                else:
                    stale.unlink()
                    print(f"  [REMOVE] Removed retired theme file {stale}")

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

    # The SheepShields policy is what preinstalls uBlock Origin + Decentraleyes,
    # so it is part of a normal install - not something to discover later. A
    # --profile run means "this profile only" and stays off the system tree.
    if args.system or not args.profile:
        if firefox_dir:
            install_policy(firefox_dir, include_extensions=args.extensions, dry_run=args.dry_run)
        else:
            print("  [info]   Firefox installation directory not found; extension preinstall skipped.")
            print("           uBlock Origin + Decentraleyes arrive on the next start once Firefox is installed.")

    print("\n[DONE] Restart Firefox to activate (SheepFox) speed & privacy protections!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
