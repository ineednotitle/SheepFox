#!/usr/bin/env python3
"""
(SheepFox) Floating URL Bar — package and validate the extension.

The extension has no build step: it is plain JavaScript, one manifest and one
SVG. This script exists so "is the shipped zip actually valid?" is answered by
the repository, not by a person clicking through `about:debugging`:

``--check``  validates the source tree only (manifest, referenced files, no
             remote code). CI runs this on every push.
default      does the same, then writes
             ``dist/SheepFox-Floating-URL-Bar-<version>.xpi`` and re-opens the
             archive to confirm it contains exactly what was validated.

Usage
-----
    python3 mozbuild/scripts/build-extension.py            # build the .xpi
    python3 mozbuild/scripts/build-extension.py --check    # validate only
    python3 mozbuild/scripts/build-extension.py --out DIR  # somewhere else
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION_DIR = REPO_ROOT / "extensions" / "floating-urlbar"
MANIFEST = EXTENSION_DIR / "manifest.json"
DIST_DIR = REPO_ROOT / "dist"

#: Fixed timestamp + sorted entries: the same source produces a byte-identical
#: archive, so a rebuilt .xpi is easy to diff and sign reproducibly.
ZIP_EPOCH = (2020, 1, 1, 0, 0, 0)

#: An extension that phones home is an extension that can change under you.
#: The bar is entirely local: no CDN, no analytics, no remote script.
REMOTE_PATTERN = re.compile(r"""(?:src|href)\s*=\s*["']https?://""", re.IGNORECASE)


class ValidationError(SystemExit):
    pass


def fail(message: str) -> None:
    raise ValidationError(f"[error] {message}")


def load_manifest() -> dict:
    if not MANIFEST.is_file():
        fail(f"{MANIFEST.relative_to(REPO_ROOT)} is missing")
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"manifest.json is not valid JSON: {error}")
    return manifest


def validate_paths(manifest: dict) -> list[str]:
    """Every file the manifest points at must exist, with a relative path."""
    referenced: list[str] = []

    def collect(value: object) -> None:
        if isinstance(value, str):
            if value.endswith((".js", ".html", ".svg", ".css", ".png")):
                referenced.append(value)
        elif isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    collect(manifest.get("icons", {}))
    collect(manifest.get("action", {}))
    collect(manifest.get("background", {}))

    for relative in referenced:
        if relative.startswith(("/", "http:", "https:")) or ".." in Path(relative).parts:
            fail(f"manifest references a non-local path: {relative}")
        if not (EXTENSION_DIR / relative).is_file():
            fail(f"manifest references a missing file: {relative}")
    return sorted(set(referenced))


def validate_manifest(manifest: dict) -> None:
    if manifest.get("manifest_version") != 3:
        fail("manifest_version must be 3")
    version = str(manifest.get("version", ""))
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"version must be 1.2.3, found {version!r}")
    if not manifest.get("name") or not manifest.get("description"):
        fail("name and description are required")
    gecko = manifest.get("browser_specific_settings", {}).get("gecko", {})
    if "@" not in str(gecko.get("id", "")):
        fail("browser_specific_settings.gecko.id must be an add-on id")
    if not gecko.get("strict_min_version"):
        fail("browser_specific_settings.gecko.strict_min_version is required")
    commands = manifest.get("commands", {})
    if "open-floating-bar" not in commands:
        fail("the open-floating-bar command is required (it is the whole feature)")
    if not commands["open-floating-bar"].get("suggested_key", {}).get("default"):
        fail("open-floating-bar needs a suggested_key")
    if not manifest.get("permissions"):
        fail("permissions are required")
    # Deliberate: nothing is injected on page load, and no host permission is
    # requested. Both would mean touching pages nobody asked about.
    if manifest.get("content_scripts"):
        fail("the bar is injected on demand; manifest content_scripts must stay empty")
    if manifest.get("host_permissions"):
        fail("no host_permissions: activeTab covers the one tab the user invokes it on")


def validate_sources(referenced: list[str]) -> list[Path]:
    files = sorted(
        path for path in EXTENSION_DIR.rglob("*") if path.is_file() and "__pycache__" not in path.parts
    )
    if not files:
        fail("the extension directory is empty")

    for path in files:
        if path.suffix not in {".js", ".json", ".html", ".svg", ".css", ".md"}:
            fail(f"unexpected file in the payload: {path.relative_to(EXTENSION_DIR)}")

    for path in files:
        if path.suffix not in {".js", ".html"}:
            continue
        text = path.read_text(encoding="utf-8")
        match = REMOTE_PATTERN.search(text)
        if match:
            fail(f"{path.name} loads remote content: {match.group(0)}")

    # search.html must pull in exactly the scripts the overlay also uses.
    html = (EXTENSION_DIR / "search.html").read_text(encoding="utf-8")
    for script in re.findall(r'<script src="([^"]+)"', html):
        if not (EXTENSION_DIR / script).is_file():
            fail(f"search.html loads a missing script: {script}")

    background = (EXTENSION_DIR / "background.js").read_text(encoding="utf-8")
    overlay = re.search(r"OVERLAY_FILES\s*=\s*\[([^\]]+)\]", background)
    if not overlay:
        fail("background.js must declare OVERLAY_FILES")
    for name in re.findall(r'"([^"]+)"', overlay.group(1)):
        if not (EXTENSION_DIR / name).is_file():
            fail(f"OVERLAY_FILES references a missing file: {name}")

    return files


def build(files: list[Path], manifest: dict, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"SheepFox-Floating-URL-Bar-{manifest['version']}.xpi"
    if target.exists():
        target.unlink()

    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            info = zipfile.ZipInfo(path.relative_to(EXTENSION_DIR).as_posix(), date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())

    # Verify what was actually written, not what we think we wrote.
    with zipfile.ZipFile(target) as archive:
        names = archive.namelist()
        if "manifest.json" not in names:
            fail("the archive has no manifest.json at its root")
        if any(name.startswith("/") or ".." in Path(name).parts for name in names):
            fail("the archive contains an absolute or escaping path")
        packed = json.loads(archive.read("manifest.json"))
        if packed.get("manifest_version") != 3 or packed.get("version") != manifest["version"]:
            fail("manifest.json inside the archive does not match the source")
        for relative in ("icons/bar.svg", "background.js", "search.html"):
            if relative not in names:
                fail(f"the archive is missing {relative}")

    shown = target.relative_to(REPO_ROOT) if REPO_ROOT in target.parents else target
    print(f"  [ok] {shown} ({target.stat().st_size} bytes, {len(files)} files)")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and package the SheepFox floating URL bar extension.")
    parser.add_argument("--check", action="store_true", help="Validate the source tree only; write nothing.")
    parser.add_argument("--out", type=Path, default=DIST_DIR, help="Output directory (default: dist/).")
    args = parser.parse_args()

    manifest = load_manifest()
    validate_manifest(manifest)
    referenced = validate_paths(manifest)
    files = validate_sources(referenced)

    print(
        f"OK  (SheepFox) Floating URL Bar {manifest['version']} "
        f"({len(files)} files, MV{manifest['manifest_version']}, {manifest['browser_specific_settings']['gecko']['id']})"
    )
    if args.check:
        return 0

    build(files, manifest, args.out.resolve() if not args.out.is_absolute() else args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
