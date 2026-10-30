#!/usr/bin/env python3
"""
(SheepFox) Firefox — Cross-Platform Drop-In Installer & Profile Manager
Applies SheepFox speed & privacy configurations to stock Mozilla Firefox:
  1. Per-profile `user.js` (+ optional personal or `--strict` overrides)
  2. Optional `--system` AutoConfig (`sheepfox.cfg` + `local-settings.js`)
     and SheepShields Enterprise Policy (`distribution/policies.json` with uBlock Origin)
"""

from __future__ import annotations

import argparse
import configparser
import os
import platform
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_JS_SRC = REPO_ROOT / "config" / "user.js"
STRICT_OVERRIDE_SRC = REPO_ROOT / "config" / "overrides" / "strict-paranoia.override.js"
CUSTOM_OVERRIDE_SRC = REPO_ROOT / "config" / "overrides" / "user-overrides.js"
POLICIES_SRC = REPO_ROOT / "config" / "distribution" / "policies.json"
AUTOCONFIG_CFG_SRC = REPO_ROOT / "config" / "autoconfig" / "sheepfox.cfg"
LOCAL_SETTINGS_SRC = REPO_ROOT / "config" / "autoconfig" / "defaults" / "pref" / "local-settings.js"


def candidate_profile_roots() -> list[Path]:
    system = platform.system()
    home = Path.home()
    if system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        return [appdata / "Mozilla" / "Firefox"]
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


def detect_default_profile() -> Path | None:
    for root in candidate_profile_roots():
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


def detect_system_firefox_dir() -> Path | None:
    for path in candidate_system_firefox_dirs():
        if path.is_dir():
            return path
    return None


def compose_user_js(strict: bool) -> str:
    content = USER_JS_SRC.read_text(encoding="utf-8")
    if strict:
        content += "\n\n" + STRICT_OVERRIDE_SRC.read_text(encoding="utf-8")
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Install (SheepFox) Firefox speed & privacy suite.")
    parser.add_argument("--profile", type=Path, help="Explicit path to target Firefox profile directory.")
    parser.add_argument("--firefox-dir", type=Path, help="Explicit path to Firefox binary installation folder.")
    parser.add_argument("--system", action="store_true", help="Also install policies.json (uBlock Origin) & AutoConfig.")
    parser.add_argument("--strict", action="store_true", help="Append strict anti-fingerprinting (RFP) overrides.")
    parser.add_argument("--uninstall", action="store_true", help="Remove SheepFox files from target profile/system.")
    parser.add_argument("--dry-run", action="store_true", help="Preview installation paths without modifying disk.")
    args = parser.parse_args()

    profile_dir = args.profile.resolve() if args.profile else detect_default_profile()
    firefox_dir = args.firefox_dir.resolve() if args.firefox_dir else detect_system_firefox_dir()

    if args.profile and not profile_dir.is_dir():
        print(f"[ERROR] Profile directory does not exist: {profile_dir}", file=sys.stderr)
        return 1
    if args.firefox_dir and not firefox_dir.is_dir():
        print(f"[ERROR] Firefox directory does not exist: {firefox_dir}", file=sys.stderr)
        return 1

    print("=== (SheepFox) Firefox Installer ===")
    print(f"Detected Profile : {profile_dir if profile_dir else 'Not found (pass --profile <dir>)'}")
    print(f"Detected System  : {firefox_dir if firefox_dir else 'Not found (pass --firefox-dir <dir>)'}")

    if args.uninstall:
        if profile_dir and (profile_dir / "user.js").exists():
            if args.dry_run:
                print(f"  [DRY-RUN] Would remove {profile_dir / 'user.js'}")
            else:
                (profile_dir / "user.js").unlink()
                print(f"  [REMOVE] Removed {profile_dir / 'user.js'}")
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

    if profile_dir:
        payload = compose_user_js(strict=args.strict)
        backup_and_write(profile_dir / "user.js", payload, dry_run=args.dry_run)

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
