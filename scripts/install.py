#!/usr/bin/env python3
"""
(SheepFox) Firefox — Cross-Platform Drop-In Installer & Profile Manager
Applies SheepFox speed & privacy configurations to Mozilla Firefox *and*
Zen Browser (the same Gecko engine, a different profile folder):
  1. Per-profile `user.js` (+ optional personal or `--strict` overrides)
  2. Per-profile UI theme: `chrome/userChrome.css` + `chrome/userContent.css`
     (the floating Zen/Arc-style new-tab search pill; skip with --no-ui).
     Firefox: on by default. Zen: opt-in with --ui, because Zen already has
     its own floating omnibox and its own chrome.
  3. SheepShields Enterprise Policy (`distribution/policies.json`), which
     preinstalls uBlock Origin + Decentraleyes and locks the privacy defaults.
     Existing policies in that file are preserved, not overwritten - a packaged
     Zen ships its own (DisableAppUpdate, ...) and losing those would be worse
     than skipping the install.
  4. Optional `--system` AutoConfig (`sheepfox.cfg` + `local-settings.js`)

Which browser: `--browser auto` (default) installs into every browser it finds,
`firefox` / `zen` pin one, `both` means both. `--zen` is shorthand for
`--browser zen`.
"""

from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
import platform
import re
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
CHROME_SRC_DIR = REPO_ROOT / "config" / "chrome"

#: The browsers this installer knows about. Zen is Firefox underneath, so it
#: takes the same user.js - only the profile folder, the installation folder,
#: the policy file it reads and the UI default differ.
FIREFOX = "firefox"
ZEN = "zen"
BROWSERS = (FIREFOX, ZEN)


def browser_label(browser: str) -> str:
    """Human name for log lines and the doctor."""
    return "Zen Browser" if browser == ZEN else "Firefox"
#: Profile-level CSS: the floating new-tab search pill (Zen/Arc style)
UI_FILES = ("userChrome.css", "userContent.css")
#: Extensions SheepShields preinstalls through the policy file. The names are
#: only used for the human-readable log lines.
SHEEPFOX_EXTENSIONS = {
    "uBlock0@raymondhill.net": "uBlock Origin",
    "jid1-BoFifL9Vbdl2zQ@jetpack": "Decentraleyes",
}
#: Optional probe that userChrome.css @imports; proves the stylesheet is read.
PROBE_FILE = "sheepfox-probe.css"
PROBE_CSS = """/* (SheepFox) CSS load probe.
   Written by `install.py --probe`, removed by `--unprobe`.
   If the top of the window is RED, Firefox is definitely reading userChrome.css
   from this profile; if it is not, the stylesheet is not being loaded at all
   (wrong profile, pref off, or Firefox was never restarted).

   Painted on #navigator-toolbox, not #nav-bar: userChrome.css makes the toolbar
   transparent while the pill floats, and that rule is more specific - the red
   used to vanish exactly when you were testing the floating state. The outline
   doubles the #urlbar id for the same reason: it has to outrank the pill's own
   `outline: none`. */
#navigator-toolbox {
  background-color: #cc0000 !important;
}
#urlbar#urlbar:is([pageproxystate="invalid"], [focused="true"], [breakout][breakout-extend], [expanded], [open]) {
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


def candidate_zen_profile_roots() -> list[Path]:
    """Everywhere Zen keeps profiles.ini on this platform.

    Zen kept profiles in ~/.zen for years; new Linux installs (1.18.6b and
    later) use $XDG_CONFIG_HOME/zen, and Flatpak keeps its own copy inside the
    sandbox's app folder. The Flatpak paths are listed for both layouts because
    the layout moved once already.
    """
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        # Roaming is the profile root; Local shows up on some builds and holds
        # a Cache folder on others, so it is last and only used if it has ini.
        return [appdata / "zen", appdata / "Zen", local / "zen"]
    if system == "Darwin":
        return [home / "Library" / "Application Support" / "zen"]
    # Zen uses $XDG_CONFIG_HOME/zen, and ~/.config/zen when that is unset. Both
    # are listed: a user (or CI) may have XDG_CONFIG_HOME pointing somewhere
    # else while the profiles live in the default place, or the reverse.
    xdg_roots = []
    for base in (os.environ.get("XDG_CONFIG_HOME"), str(home / ".config")):
        if base:
            candidate = Path(base) / "zen"
            if candidate not in xdg_roots:
                xdg_roots.append(candidate)
    flatpak = home / ".var" / "app" / "app.zen_browser.zen"
    roots = [home / ".zen", *xdg_roots, flatpak / ".zen", flatpak / "config" / "zen"]
    return roots


def candidate_zen_dirs() -> list[Path]:
    """Everywhere a Zen installation lives, per platform and per packager."""
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        local = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
        return [
            program_files / "Zen Browser",
            program_files_x86 / "Zen Browser",
            # The per-user installer (the default) goes to LocalAppData, not
            # Program Files - the same trap as Store Firefox.
            local / "Programs" / "zen",
            local / "Programs" / "Zen Browser",
            local / "Zen Browser",
        ]
    if system == "Darwin":
        return [Path("/Applications/Zen.app/Contents/Resources")]
    return [
        # AUR zen-browser-bin, then distro packages, then Flatpak.
        Path("/opt/zen-browser-bin"),
        Path("/opt/zen-browser"),
        Path("/opt/zen"),
        Path("/usr/lib/zen-browser"),
        Path("/usr/lib64/zen-browser"),
        Path("/usr/lib/zen"),
        Path("/var/lib/flatpak/app/app.zen_browser.zen/current/active/files"),
        home / ".local" / "share" / "flatpak" / "app" / "app.zen_browser.zen" / "current" / "active" / "files",
    ]


def looks_like_zen(path: Path) -> bool:
    """True when *path* really is a Zen installation, not just an empty folder.

    Guessing wrong here means writing policies.json into somebody else's
    directory, so the check reads the app metadata instead of trusting a name.
    """
    if not path.is_dir():
        return False
    # A Flatpak "files" root keeps the app one or two levels down.
    for base in (path, path / "zen", path / "lib" / "zen", path / "lib" / "zen-browser"):
        if not base.is_dir():
            continue
        ini = base / "application.ini"
        if ini.is_file():
            text = ini.read_text(encoding="utf-8", errors="replace").lower()
            if "zen" in text:
                return True
        for binary in ("zen", "zen.exe", "zen-bin", "zen-browser"):
            if (base / binary).exists():
                return True
    return False


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


def profile_roots(browser: str = FIREFOX) -> list[Path]:
    """The profile roots for *browser* on this platform."""
    return candidate_zen_profile_roots() if browser == ZEN else candidate_profile_roots()


def iter_profile_dirs(roots: list[Path] | None = None) -> list[Path]:
    """Every profile directory that exists on this machine, any install type."""
    dirs: list[Path] = []
    for root in candidate_profile_roots() if roots is None else roots:
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


def detect_default_profile(roots: list[Path] | None = None) -> Path | None:
    for root in candidate_profile_roots() if roots is None else roots:
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


def all_profiles(roots: list[Path] | None = None) -> list[Path]:
    """Every profile for one browser on this machine, across every install type.

    Installing into all of them removes profile detection as a failure mode:
    the CSS lands wherever the browser actually happens to run.
    """
    roots = candidate_profile_roots() if roots is None else roots
    found: list[Path] = []
    for root in roots:
        for candidate in read_install_defaults(root):
            if candidate not in found:
                found.append(candidate)
    default = detect_default_profile(roots)
    if default and default not in found:
        found.insert(0, default)
    for candidate in iter_profile_dirs(roots):
        if candidate not in found:
            found.append(candidate)
    return found


def detect_system_firefox_dir() -> Path | None:
    for path in candidate_system_firefox_dirs():
        if path.is_dir():
            return path
    return None


def detect_zen_dir() -> Path | None:
    """The Zen installation folder (the one policies.json must be written into)."""
    for path in candidate_zen_dirs():
        if looks_like_zen(path):
            # A Flatpak "files" root holds the app one level down; policies are
            # read relative to the real binary, so return that level.
            for base in (path, path / "zen", path / "lib" / "zen"):
                if (base / "application.ini").is_file() or (base / "zen").exists() or (base / "zen-bin").exists():
                    return base
            return path
    return None


def detect_install_dir(browser: str) -> Path | None:
    return detect_zen_dir() if browser == ZEN else detect_system_firefox_dir()


def browser_found(browser: str) -> bool:
    """Is this browser installed *or* has it ever been run on this machine?"""
    return bool(all_profiles(profile_roots(browser))) or detect_install_dir(browser) is not None


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


def doctor(
    profile_dir: Path | None,
    install_dir: Path | None,
    browser: str = FIREFOX,
    ui_expected: bool | None = None,
) -> int:
    """Explain whether the floating-search UI can load, and why not."""
    label = browser_label(browser)
    print(f"=== (SheepFox) {label} doctor ===")
    version = read_firefox_version(install_dir)
    if install_dir:
        print(f"  install   : {install_dir}")
        print(f"  version   : {version}")
    else:
        print("  install   : not detected (pass --firefox-dir / --zen-dir)")

    failures = 0

    def report(ok: bool, label_text: str, detail: str = "") -> None:
        nonlocal failures
        if not ok:
            failures += 1
        mark = "OK  " if ok else "FAIL"
        print(f"  [{mark}] {label_text}{(' -> ' + detail) if detail else ''}")

    if not profile_dir:
        print(f"  [FAIL] no {label} profile found (launch {label} once, or pass --profile)")
        failures += 1
        return 1

    print(f"  profile   : {profile_dir}   <- {label} is launched with this one")

    user_js = profile_dir / "user.js"
    report(user_js.is_file(), "user.js present")
    if user_js.is_file():
        text = user_js.read_text(encoding="utf-8", errors="replace")
        report(
            'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);' in text,
            "user.js enables userChrome.css",
        )

    chrome_dir = profile_dir / "chrome"
    # Zen ships its own omnibox and its own chrome, so SheepFox's pill is opt-in
    # there: a missing stylesheet is the expected state, not a fault.
    if ui_expected is None:
        ui_expected = browser != ZEN or any((chrome_dir / name).is_file() for name in UI_FILES)
    if not ui_expected:
        print("  [info] UI theme not installed (default for Zen; add --ui to install the pill)")
    else:
        for name, minimum in (("userChrome.css", 2000), ("userContent.css", 400)):
            target = chrome_dir / name
            size = target.stat().st_size if target.is_file() else 0
            report(target.is_file() and size >= minimum, f"chrome/{name}", f"{size} bytes")

        # Is the copy in the profile the same file the repo ships? A stale copy
        # from an older version is a classic "the CSS is there but nothing
        # changed".
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
        print(f"  [info] prefs.js has no saved value yet; {label} will take it from user.js on next start")
    elif saved is True:
        report(True, "pref saved as true")
    else:
        report(False, "pref saved as false", "set it to true in about:config, or reinstall")
        print("         (a stale user.js or another hardening tool may have set it false)")

    # Catch the number-one cause: SheepFox was installed into a profile that the
    # browser never opens (Store build, portable build, second profile, ...).
    others = [d for d in iter_profile_dirs(profile_roots(browser)) if d.resolve() != profile_dir.resolve()]
    stray = [d for d in others if (d / "chrome" / "userChrome.css").is_file() or (d / "user.js").is_file()]
    if stray:
        print()
        print(f"  [WARN] Other {label} profiles on this machine also have SheepFox files:")
        for d in stray:
            print(f"         {d}")
        print("         Only the profile above is used at launch. Install into it:")
        print(f'           python3 scripts/install.py --browser {browser} --profile "{profile_dir}"')
    if others and not stray:
        print()
        print(f"  [info] {len(others)} other profile(s) found, none of them modified.")

    # The system half (policies.json + AutoConfig) is optional: a plain
    # per-profile install leaves the installation folder completely untouched,
    # so an absent file there is not a problem - only an opportunity.
    if install_dir:
        system_files = ("sheepfox.cfg", "defaults/pref/local-settings.js", "distribution/policies.json")
        installed = [rel for rel in system_files if (install_dir / rel).is_file()]
        for rel in installed:
            report(True, f"system {rel}")
        if not installed:
            print("  [info] no system install here (--system is optional):")
            print("         policies.json preinstalls uBlock Origin + Decentraleyes and locks the shields.")
            print(f"         add them with:  python3 scripts/install.py --browser {browser} --system")
        policy_file = install_dir / "distribution" / "policies.json"
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
        print(f"  {failures} problem(s) found. Fix the FAIL lines above, then restart {label}.")
        print(f"  Full reinstall:  python3 scripts/install.py --browser {browser} [--profile DIR] [--system]")
        return 1

    if ui_expected:
        print(f"  Files are in place. To prove {label} is actually reading the stylesheet:")
        print("    1. python3 scripts/install.py --probe")
        print(f"    2. QUIT {label} completely, then start it.")
        print("    3. Open a new tab. The toolbar turns RED and the pill gets a green outline")
        print("       if the CSS is loaded. Nothing changes if it is not.")
        print("    4. python3 scripts/install.py --unprobe")
        print(f"  If the toolbar stays dark, the profile above is not the one {label} runs:")
        print(f"    open about:support in {label} and compare 'Profile Folder' with the path")
        print("    printed at the top of this report, then reinstall with --profile <that path>.")
    else:
        print(f"  Files are in place. Restart {label} to apply the preferences and the policy.")
        print("  The floating pill is Firefox-only by default; add --ui to install it here too.")
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


def policy_document(include_extensions: bool = True) -> dict:
    """The SheepShields policy as a dict, optionally without our extensions."""
    policy = json.loads(POLICIES_SRC.read_text(encoding="utf-8"))
    if not include_extensions:
        settings = policy["policies"].get("ExtensionSettings", {})
        for extension_id in SHEEPFOX_EXTENSIONS:
            settings.pop(extension_id, None)
        managed = policy["policies"].get("3rdparty", {}).get("Extensions", {})
        for extension_id in SHEEPFOX_EXTENSIONS:
            managed.pop(extension_id, None)
    return policy


def merge_policies(existing: dict | None, include_extensions: bool = True) -> dict:
    """SheepShields on top of whatever policy file is already there.

    Firefox and Zen take the *first* policy file they find, not a merge of
    several, so writing ours must not silently delete policies the packager or
    an administrator put there - a Zen package ships `DisableAppUpdate` and
    dropping it would let the browser update itself behind the package manager.
    SheepFox's own keys win; everything else is kept.
    """
    merged = policy_document(include_extensions)
    ours = merged.setdefault("policies", {})
    prior = (existing or {}).get("policies") if isinstance(existing, dict) else None
    if isinstance(prior, dict):
        for key, value in prior.items():
            if key not in ours:
                ours[key] = value
    if not include_extensions:
        # --no-extensions has to remove our entries even from a file that
        # already had them, otherwise the flag would do nothing on a reinstall.
        for extension_id in SHEEPFOX_EXTENSIONS:
            ours.get("ExtensionSettings", {}).pop(extension_id, None)
            ours.get("3rdparty", {}).get("Extensions", {}).pop(extension_id, None)
    return merged


def preserved_policy_keys(existing: dict | None) -> list[str]:
    """Policy names the existing file has and SheepFox does not set."""
    if not isinstance(existing, dict) or not isinstance(existing.get("policies"), dict):
        return []
    ours = policy_document(True)["policies"]
    return sorted(key for key in existing["policies"] if key not in ours)


def render_policies(include_extensions: bool = True, existing: dict | None = None) -> str:
    """The SheepShields policy, optionally merged over *existing*."""
    return json.dumps(merge_policies(existing, include_extensions), indent=2, ensure_ascii=False) + "\n"


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


def read_existing_policy(target: Path) -> dict | None:
    if not target.is_file():
        return None
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def install_policy(
    install_dir: Path,
    include_extensions: bool,
    dry_run: bool,
    policy_dir: Path | None = None,
    browser: str = FIREFOX,
) -> bool:
    """Write <install>/distribution/policies.json, elevating only if needed.

    *policy_dir* overrides the destination folder. On Linux the one useful
    override is `/etc/zen/policies`: Zen reads that file *instead of* the one in
    its installation folder, and a package upgrade rewrites the latter.
    """
    target = (policy_dir or install_dir / "distribution") / "policies.json"
    existing = read_existing_policy(target)
    content = render_policies(include_extensions, existing)
    kept = preserved_policy_keys(existing)
    if kept:
        print(f"  [KEEP]   Preserved {len(kept)} existing policy entr{'y' if len(kept) == 1 else 'ies'}: {', '.join(kept)}")
    if dry_run:
        print(f"  [DRY-RUN] Would write {target} ({len(content)} bytes)")
        return True
    try:
        backup_and_write(target, content, dry_run=False)
    except (PermissionError, OSError):
        if not _elevated_copy(target, content):
            print(f"  [WARN]   Could not write {target} (administrator rights required).")
            print("           Run the installer once as an administrator:")
            print(f"             sudo python3 scripts/install.py --browser {browser} --system")
            print(f"           or copy distribution/policies.json into {install_dir}")
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


def uninstall_policy(target: Path, dry_run: bool) -> None:
    """Remove SheepFox's policies, keep whatever the packager put there.

    Whatever we merged in on install has to come back out on --uninstall:
    deleting the whole file would drop a Zen package's `DisableAppUpdate` and
    let the browser update itself behind the package manager.
    """
    if not target.exists():
        return
    existing = read_existing_policy(target)
    if existing is None:
        if dry_run:
            print(f"  [DRY-RUN] Would remove {target}")
        else:
            target.unlink()
            print(f"  [REMOVE] Removed {target}")
        return

    policies = existing.get("policies")
    if not isinstance(policies, dict):
        policies = {}
    for key in policy_document(True)["policies"]:
        policies.pop(key, None)
    for extension_id in SHEEPFOX_EXTENSIONS:
        policies.get("ExtensionSettings", {}).pop(extension_id, None)
        policies.get("3rdparty", {}).get("Extensions", {}).pop(extension_id, None)
    remaining = {key: value for key, value in policies.items() if key not in ("ExtensionSettings", "3rdparty")}
    extension_settings = policies.get("ExtensionSettings") or {}
    if set(extension_settings) - {"*"}:
        remaining["ExtensionSettings"] = extension_settings
    if remaining:
        content = json.dumps({"policies": remaining}, indent=2, ensure_ascii=False) + "\n"
        if dry_run:
            print(f"  [DRY-RUN] Would keep {len(remaining)} policy entr{'y' if len(remaining) == 1 else 'ies'} in {target}")
        else:
            target.write_text(content, encoding="utf-8")
            print(f"  [KEEP]   Left {len(remaining)} non-SheepFox policy entr{'y' if len(remaining) == 1 else 'ies'} in {target}")
        return
    if dry_run:
        print(f"  [DRY-RUN] Would remove {target}")
    else:
        target.unlink()
        print(f"  [REMOVE] Removed {target}")


def _uninstall_profile(profile: Path, dry_run: bool) -> None:
    for target in [profile / "user.js"] + [profile / "chrome" / name for name in (*UI_FILES, PROBE_FILE)]:
        if not target.exists():
            continue
        if dry_run:
            print(f"  [DRY-RUN] Would remove {target}")
        else:
            target.unlink()
            print(f"  [REMOVE] Removed {target}")


def ui_enabled(browser: str, args: argparse.Namespace) -> bool:
    """Is the SheepFox pill part of this install?

    Firefox: yes, that is the whole point of the theme. Zen: only with --ui -
    Zen already ships its own floating omnibox, so our pill is a choice there,
    not a default.
    """
    if args.no_ui:
        return False
    if args.ui:
        return True
    return browser == FIREFOX


def parse_browsers(args: argparse.Namespace) -> list[str]:
    """Which browsers this run should touch, in a stable order."""
    if args.zen:
        chosen = ZEN
    else:
        chosen = args.browser
    if chosen == FIREFOX:
        return [FIREFOX]
    if chosen == ZEN:
        return [ZEN]
    if chosen == "both":
        return [FIREFOX, ZEN]

    # auto: everything that is actually installed or has ever been run. With
    # nothing detectable, fall back to Firefox so the error messages stay the
    # ones people already know.
    # An explicit --firefox-dir / --zen-dir only pins that browser's install
    # location; it does not mean "skip the other browser".
    if args.profile:
        lowered = str(args.profile).lower()
        if "zen" in lowered:
            return [ZEN]
        if "firefox" in lowered or ".mozilla" in lowered:
            return [FIREFOX]
    found = [browser for browser in BROWSERS if browser_found(browser)]
    return found or [FIREFOX]


def install_into_browser(browser: str, args: argparse.Namespace) -> int:
    """One browser's worth of work: profiles, UI, policy, doctor, uninstall."""
    label = browser_label(browser)
    explicit_dir = args.zen_dir if browser == ZEN else args.firefox_dir
    install_dir = explicit_dir.resolve() if explicit_dir else detect_install_dir(browser)
    roots = profile_roots(browser)
    profiles = [args.profile.resolve()] if args.profile else all_profiles(roots)
    profile_dir = profiles[0] if profiles else None
    ui = ui_enabled(browser, args)
    # Doctor and report describe the disk, not the flags: only override what
    # they should expect when the user said so explicitly.
    ui_expectation = ui if (args.ui or args.no_ui) else None

    if args.profile and not profile_dir.is_dir():
        print(f"[ERROR] Profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 1
    if explicit_dir and install_dir and not install_dir.is_dir():
        print(f"[ERROR] {label} directory does not exist: {install_dir}", file=sys.stderr)
        return 1

    print(f"=== (SheepFox) {label} Installer ===")
    if len(profiles) > 1:
        print(f"Detected Profiles: {len(profiles)} (installing into all of them)")
        for target in profiles:
            print(f"                 - {target}")
    else:
        print(f"Detected Profile : {profile_dir if profile_dir else 'Not found (pass --profile <dir>)'}")
    dir_hint = "--zen-dir <dir>" if browser == ZEN else "--firefox-dir <dir>"
    print(f"Detected System  : {install_dir if install_dir else 'Not found (pass ' + dir_hint + ')'}")
    if browser == ZEN and not (args.doctor or args.report or args.uninstall or args.probe or args.unprobe):
        print(f"UI theme         : {'installed' if ui else 'not installed (Zen keeps its own omnibox; add --ui)'}")

    if args.report is not None:
        import contextlib
        import io as _io

        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            print(f"=== (SheepFox) {label} report ===")
            print(f"platform     : {platform.platform()}")
            print(f"browser      : {label}")
            print(f"repo         : {REPO_ROOT}")
            print(f"install dir  : {install_dir}")
            print(f"version      : {read_firefox_version(install_dir)}")
            print("profiles found:")
            for candidate in all_profiles(roots):
                print(f"  - {candidate}")
            print()
            code = doctor(profile_dir, install_dir, browser=browser, ui_expected=ui_expectation)
        text = buffer.getvalue()
        destination = args.report if args.report.is_absolute() else Path.cwd() / args.report
        destination.write_text(text + f"\nexit_code={code}\n", encoding="utf-8")
        print(text)
        print(f"[REPORT] Written to {destination}")
        print("         Paste that file (or its contents) into the issue/chat.")
        return code

    if args.doctor:
        return doctor(profile_dir, install_dir, browser=browser, ui_expected=ui_expectation)

    if args.probe or args.unprobe:
        targets = [t for t in profiles if t.is_dir()]
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
            print(f"\n  Now QUIT {label} completely, start it and open a new tab:")
            print("  a RED toolbar + green pill outline means the CSS is loading.")
            print("  Remove it with:  python3 scripts/install.py --unprobe")
        return 0

    if args.uninstall:
        for target_profile in [t for t in profiles if t.is_dir()]:
            _uninstall_profile(target_profile, args.dry_run)
        # Mirrors the install rule: a plain run wrote the policy, so a plain
        # --uninstall has to remove it again.
        if (args.system or not args.profile) and install_dir:
            for rel in ["sheepfox.cfg", "defaults/pref/local-settings.js"]:
                target = install_dir / rel
                if target.exists():
                    if args.dry_run:
                        print(f"  [DRY-RUN] Would remove {target}")
                    else:
                        target.unlink()
                        print(f"  [REMOVE] Removed {target}")
            uninstall_policy(install_dir / "distribution" / "policies.json", args.dry_run)
            if args.policy_dir:
                uninstall_policy(args.policy_dir / "policies.json", args.dry_run)
        return 0

    if profile_dir and not profile_dir.is_dir() and not args.dry_run:
        print(f"[ERROR] Profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 1

    if not profile_dir and not args.system:
        if args.dry_run:
            print(f"[INFO] Dry-run completed (no {label} profile currently exists on this machine).")
            return 0
        print(
            f"[ERROR] Could not auto-detect a {label} profile. Launch {label} once or pass --profile <path>.",
            file=sys.stderr,
        )
        return 1

    payload = compose_user_js(strict=args.strict, low_memory=args.low_memory)
    for target in [t for t in profiles if t.is_dir()]:
        if len(profiles) > 1:
            print(f"\n  -> {target}")
        backup_and_write(target / "user.js", payload, dry_run=args.dry_run)

        if not ui:
            if browser == ZEN and not args.no_ui:
                print("  [SKIP]   UI theme not installed (Zen's own omnibox is used; add --ui for SheepFox's pill)")
            else:
                print("  [SKIP]   UI theme skipped (--no-ui)")
            continue
        for name in UI_FILES:
            src = CHROME_SRC_DIR / name
            if not src.is_file():
                print(f"  [WARN]   Missing UI asset: {src}")
                continue
            backup_and_write(target / "chrome" / name, src.read_text(encoding="utf-8"), args.dry_run)

    if args.system:
        if not install_dir:
            print(f"[ERROR] Could not locate the {label} installation directory. Pass --firefox-dir/--zen-dir <path>.", file=sys.stderr)
            return 1
        backup_and_write(install_dir / "sheepfox.cfg", AUTOCONFIG_CFG_SRC.read_text(encoding="utf-8"), args.dry_run)
        backup_and_write(
            install_dir / "defaults" / "pref" / "local-settings.js",
            LOCAL_SETTINGS_SRC.read_text(encoding="utf-8"),
            args.dry_run,
        )

    # The SheepShields policy is what preinstalls uBlock Origin + Decentraleyes,
    # so it is part of a normal install - not something to discover later. A
    # --profile run means "this profile only" and stays off the system tree.
    if args.system or not args.profile:
        if install_dir:
            install_policy(
                install_dir,
                include_extensions=args.extensions,
                dry_run=args.dry_run,
                policy_dir=args.policy_dir,
                browser=browser,
            )
        else:
            print(f"  [info]   {label} installation directory not found; extension preinstall skipped.")
            print("           uBlock Origin + Decentraleyes arrive on the next start once it is installed.")

    print(f"\n[DONE] Restart {label} to activate (SheepFox) speed & privacy protections!")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install the (SheepFox) speed & privacy suite into Firefox and/or Zen Browser."
    )
    parser.add_argument("--profile", type=Path, help="Explicit path to the target profile directory.")
    parser.add_argument("--firefox-dir", type=Path, help="Explicit path to the Firefox installation folder.")
    parser.add_argument("--zen-dir", type=Path, help="Explicit path to the Zen Browser installation folder.")
    parser.add_argument(
        "--browser",
        choices=("auto", "firefox", "zen", "both"),
        default="auto",
        help="Which browser to configure (default: auto - every one that is installed or has been run).",
    )
    parser.add_argument(
        "--zen",
        action="store_true",
        help="Shorthand for --browser zen.",
    )
    parser.add_argument(
        "--policy-dir",
        type=Path,
        help="Write policies.json into this folder instead of <install>/distribution "
        "(Linux Zen reads /etc/zen/policies first, and package upgrades leave it alone).",
    )
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
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Install the floating-search theme even where it is opt-in (Zen Browser).",
    )
    args = parser.parse_args()

    browsers = parse_browsers(args)
    if len(browsers) > 1 and args.profile:
        # A named profile belongs to exactly one browser.
        browsers = [FIREFOX]

    status = 0
    for browser in browsers:
        if len(browsers) > 1:
            print()
        code = install_into_browser(browser, args)
        status = status or code
    return status


if __name__ == "__main__":
    sys.exit(main())
