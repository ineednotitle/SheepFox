#!/usr/bin/env python3
# ============================================================================
# (SheepFox) Firefox — build the distributable installers
#
#   python3 mozbuild/scripts/build-installers.py            # both
#   python3 mozbuild/scripts/build-installers.py --windows  # .exe only
#   python3 mozbuild/scripts/build-installers.py --macos    # .dmg + .iso only
#
# Windows  -> dist/SheepFox-Setup-<version>.exe
#             A real PE32+ executable: the whole payload is embedded as a byte
#             array, and at run time it unpacks to %TEMP% and runs the same
#             scripts\install-windows.ps1 a git checkout would run. Needs the
#             Zig toolchain (pip install ziglang) to cross-compile from any OS.
#
# macOS    -> dist/SheepFox-<version>.dmg  (UDIF image containing the payload
#             plus "Install SheepFox.command")
#             dist/SheepFox-<version>.iso  (plain ISO9660/Joliet copy, in case
#             a host refuses the UDIF container)
#
# Both artifacts carry the exact files from config/, not a re-implementation.
# ============================================================================

from __future__ import annotations

import argparse
import base64
import datetime as _dt
import io
import os
import plistlib
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIST_DIR = REPO_ROOT / "dist"
INSTALLER_DIR = REPO_ROOT / "installer"
VERSION_FILE = INSTALLER_DIR / "version.txt"

#: Everything the installers need at run time. Paths are repo-relative.
PAYLOAD_FILES = (
    "scripts/install.py",
    "scripts/install-unix.sh",
    "scripts/install-windows.ps1",
    "scripts/install-windows.bat",
    "config/user.js",
    "config/modules/01-speedfox.js",
    "config/modules/02-shieldfox.js",
    "config/modules/03-cleanfox.js",
    "config/modules/04-smoothfox.js",
    "config/chrome/userChrome.css",
    "config/chrome/userContent.css",
    "config/overrides/strict-paranoia.override.js",
    "config/overrides/low-memory.override.js",
    "config/overrides/user-overrides.example.js",
    "config/autoconfig/sheepfox.cfg",
    "config/autoconfig/defaults/pref/local-settings.js",
    "config/distribution/policies.json",
    "mozbuild/scripts/build-configs.py",
    "LICENSE",
    "README.md",
)

#: Files that must stay executable once unpacked on macOS.
EXECUTABLE = (
    "scripts/install-unix.sh",
    "Install SheepFox.command",
)

BLOCK_SIZE = 512
KOLY_SIZE = 512
CHUNK_RAW = 0x00000001


def read_version() -> str:
    if VERSION_FILE.is_file():
        version = VERSION_FILE.read_text(encoding="utf-8").strip()
        if version:
            return version
    return "0.0.0"


def payload_paths() -> list[Path]:
    missing = [rel for rel in PAYLOAD_FILES if not (REPO_ROOT / rel).is_file()]
    if missing:
        raise SystemExit("[error] payload files are missing: " + ", ".join(missing))
    return [REPO_ROOT / rel for rel in PAYLOAD_FILES]


def build_payload_zip(prefix: str = "") -> bytes:
    """Zip the payload with repo-relative names (optionally under a prefix)."""
    buffer = io.BytesIO()
    stamp = _dt.datetime(2026, 1, 1, tzinfo=_dt.timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in payload_paths():
            relative = source.relative_to(REPO_ROOT).as_posix()
            info = zipfile.ZipInfo(f"{prefix}{relative}", date_time=stamp)
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if relative in EXECUTABLE else 0o644
            # DOS attributes by default (PowerShell's Expand-Archive is happiest
            # with them); only the shell scripts carry Unix mode bits, so they
            # stay executable if someone unzips the payload on macOS or Linux.
            info.create_system = 3 if mode == 0o755 else 0
            info.external_attr = (0o100000 | mode) << 16
            archive.writestr(info, source.read_bytes())
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Windows: C launcher + embedded payload
# ---------------------------------------------------------------------------
def find_zig(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get("SHEEPFOX_ZIG")
    if env:
        return env
    try:
        import ziglang  # type: ignore

        package = Path(ziglang.__file__).parent
        for name in ("zig", "zig.exe"):
            candidate = package / name
            if candidate.is_file():
                return str(candidate)
    except ImportError:
        pass
    found = shutil.which("zig")
    if found:
        return found
    raise SystemExit(
        "[error] zig not found. Install it with `pip install ziglang`, "
        "or pass --zig /path/to/zig (or set SHEEPFOX_ZIG)."
    )


def c_byte_array(data: bytes, symbol: str, indent: int = 12) -> str:
    lines = []
    pad = " " * indent
    for start in range(0, len(data), 24):
        chunk = data[start : start + 24]
        lines.append(pad + "".join(f"0x{byte:02x}," for byte in chunk))
    body = "\n".join(lines)
    return (
        f"/* generated by build-installers.py - do not edit */\n"
        f"const unsigned char {symbol}[] = {{\n{body}\n}};\n"
        f"const unsigned int {symbol}_size = {len(data)}u;\n"
    )


def build_windows(zig: str, version: str) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    payload = build_payload_zip()
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        (tmpdir / "payload.c").write_text(
            c_byte_array(payload, "sheepfox_payload"), encoding="utf-8"
        )
        shutil.copy2(INSTALLER_DIR / "windows" / "launcher.c", tmpdir / "launcher.c")
        target = DIST_DIR / f"SheepFox-Setup-{version}.exe"
        command = [
            zig,
            "cc",
            "-target",
            "x86_64-windows-gnu",
            "-O2",
            "-s",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-o",
            str(target),
            str(tmpdir / "launcher.c"),
            str(tmpdir / "payload.c"),
        ]
        print("  [zig]", " ".join(command[1:4]), "...")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit("[error] zig cc failed")
        if result.stderr.strip():
            print("  [zig] ", result.stderr.strip()[:400])
            raise SystemExit("[error] the launcher compiled with warnings; fix them")
    print(f"  [ok]   {target.relative_to(REPO_ROOT)}  ({target.stat().st_size} bytes)")
    return target


# ---------------------------------------------------------------------------
# macOS: ISO9660/Joliet volume (pycdlib) wrapped in a UDIF (.dmg) container
# ---------------------------------------------------------------------------
def build_volume_tree(root: Path) -> None:
    """Repo payload under SheepFox/, installer + notes at the volume root."""
    for source in payload_paths():
        relative = source.relative_to(REPO_ROOT)
        destination = root / "SheepFox" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    shutil.copy2(INSTALLER_DIR / "macos" / "Install SheepFox.command", root / "Install SheepFox.command")
    shutil.copy2(INSTALLER_DIR / "macos" / "README.txt", root / "README.txt")
    for relative in EXECUTABLE:
        for candidate in (root / relative, root / "SheepFox" / relative):
            if candidate.exists():
                candidate.chmod(0o755)


def _iso_component(name: str, used: set[tuple[str, str]]) -> str:
    """An ISO9660-compliant (8.3, A-Z0-9_) name, unique inside its directory."""
    stem, _, suffix = name.rpartition(".")
    if not stem or not suffix.isalnum():
        stem, suffix = name, ""
    clean = lambda text: "".join(ch for ch in text.upper() if ch.isalnum() or ch == "_")  # noqa: E731
    stem = clean(stem)[:8] or "FILE"
    suffix = clean(suffix)[:3]
    candidate = stem
    counter = 1
    while (candidate, suffix) in used:
        counter += 1
        candidate = f"{stem[:5]}~{counter}"[:8]
    used.add((candidate, suffix))
    return f"{candidate}.{suffix}" if suffix else candidate


def build_iso(volume: Path, label: str) -> bytes:
    """ISO9660 + Joliet + Rock Ridge. Joliet carries the real file names."""
    try:
        import pycdlib
    except ImportError:
        raise SystemExit("[error] pycdlib is required for the DMG: pip install pycdlib")

    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, joliet=3, rock_ridge="1.09", vol_ident=label[:32].upper())

    used: dict[str, set[tuple[str, str]]] = {"": set()}
    dir_iso: dict[str, str] = {".": ""}

    directories = sorted(
        (path for path in volume.rglob("*") if path.is_dir()),
        key=lambda path: len(path.relative_to(volume).parts),
    )
    for directory in directories:
        relative = directory.relative_to(volume)
        parent = relative.parent.as_posix()
        parent_iso = dir_iso["." if parent == "." else parent]
        name = _iso_component(relative.name, used.setdefault(parent_iso, set()))
        iso_path = f"{parent_iso}/{name}"
        used.setdefault(iso_path, set())
        iso.add_directory(
            iso_path=iso_path,
            rr_name=relative.name,
            joliet_path="/" + relative.as_posix(),
            file_mode=0o040755,
        )
        dir_iso[relative.as_posix()] = iso_path

    for item in sorted(path for path in volume.rglob("*") if path.is_file()):
        relative = item.relative_to(volume)
        parent = relative.parent.as_posix()
        parent_iso = dir_iso["." if parent == "." else parent]
        component = _iso_component(relative.name, used.setdefault(parent_iso, set()))
        mode = 0o100755 if relative.as_posix() in EXECUTABLE else 0o100644
        iso.add_file(
            filename=str(item),
            iso_path=f"{parent_iso}/{component};1",
            rr_name=relative.name,
            joliet_path="/" + relative.as_posix(),
            file_mode=mode,
        )

    buffer = io.BytesIO()
    iso.write_fp(buffer)
    iso.close()
    return buffer.getvalue()


def _checksum_struct(data: bytes) -> bytes:
    crc = zlib.crc32(data) & 0xFFFFFFFF
    return struct.pack(">II", 2, 32) + crc.to_bytes(4, "big").ljust(128, b"\x00")


def _blkx(image: bytes, name: str) -> bytes:
    sectors = (len(image) + BLOCK_SIZE - 1) // BLOCK_SIZE
    header = b"mish" + struct.pack(
        ">IQQQII6I", 1, 0, sectors, 0, 1, 1, 0, 0, 0, 0, 0, 0
    )
    header += _checksum_struct(image)
    chunk = struct.pack(">IIQQQQ", CHUNK_RAW, 0, 0, sectors, 0, len(image))
    return header + chunk


def build_dmg(image: bytes, label: str) -> bytes:
    """Wrap a raw disk image in a UDIF container (uncompressed, UDRO)."""
    sectors = (len(image) + BLOCK_SIZE - 1) // BLOCK_SIZE
    mish = _blkx(image, label)
    plist = {
        "resource-fork": {
            "blkx": [
                {
                    "Attributes": "0x0050",
                    "CFName": label,
                    "Data": mish,
                    "ID": "0",
                    "Name": label,
                }
            ]
        }
    }
    xml = plistlib.dumps(plist, fmt=plistlib.FMT_XML)
    data_offset = 0
    xml_offset = len(image)
    trailer = struct.pack(">4sIII", b"koly", 4, KOLY_SIZE, 1)
    trailer += struct.pack(">QQQQQ", 0, data_offset, len(image), 0, 0)
    trailer += struct.pack(">II16s", 1, 1, b"\x00" * 16)
    trailer += _checksum_struct(image)
    trailer += struct.pack(">QQ", xml_offset, len(xml))
    trailer += b"\x00" * 120
    trailer += _checksum_struct(xml)
    trailer += struct.pack(">IQ", 1, sectors)
    trailer += b"\x00" * 12
    assert len(trailer) == KOLY_SIZE, len(trailer)
    return image + xml + trailer


def build_macos_native(volume: Path, version: str, label: str) -> Path:
    """A real HFS+ DMG via hdiutil (macOS hosts only)."""
    dmg_path = DIST_DIR / f"SheepFox-{version}.dmg"
    command = [
        "hdiutil",
        "create",
        "-volname",
        label,
        "-srcfolder",
        str(volume),
        "-fs",
        "HFS+",
        "-format",
        "UDZO",
        "-ov",
        str(dmg_path),
    ]
    print("  [hdiutil] creating an HFS+ compressed image")
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("[error] hdiutil failed")
    return dmg_path


def build_macos(version: str) -> list[Path]:
    DIST_DIR.mkdir(exist_ok=True)
    label = f"SheepFox {version}"
    with tempfile.TemporaryDirectory() as tmp:
        volume = Path(tmp) / "volume"
        volume.mkdir()
        build_volume_tree(volume)
        if shutil.which("hdiutil"):
            try:
                dmg_path = build_macos_native(volume, version, label)
            except SystemExit as error:
                print(f"  [warn] {error}")
                print("  [warn] falling back to the portable ISO9660/UDIF writer")
            else:
                print(f"  [ok]   {dmg_path.relative_to(REPO_ROOT)}  ({dmg_path.stat().st_size} bytes)")
                return [dmg_path]
        image = build_iso(volume, label)
    iso_path = DIST_DIR / f"SheepFox-{version}.iso"
    iso_path.write_bytes(image)
    dmg_path = DIST_DIR / f"SheepFox-{version}.dmg"
    dmg_path.write_bytes(build_dmg(image, label))
    for path in (dmg_path, iso_path):
        print(f"  [ok]   {path.relative_to(REPO_ROOT)}  ({path.stat().st_size} bytes)")
    return [dmg_path, iso_path]


def verify_windows(path: Path) -> None:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        raise SystemExit(f"[error] {path.name}: not a DOS/PE image")
    offset = int.from_bytes(data[0x3C:0x40], "little")
    if data[offset:offset + 4] != b"PE\0\0":
        raise SystemExit(f"[error] {path.name}: missing the PE signature")
    machine = int.from_bytes(data[offset + 4:offset + 6], "little")
    if machine != 0x8664:
        raise SystemExit(f"[error] {path.name}: machine 0x{machine:04x}, expected x86-64")
    start = data.find(b"PK\x03\x04")
    if start < 0:
        raise SystemExit(f"[error] {path.name}: the payload zip is not embedded")
    payload = zipfile.ZipFile(io.BytesIO(data[start:]))
    names = set(payload.namelist())
    for required in ("scripts/install-windows.ps1", "config/user.js", "config/chrome/userChrome.css"):
        if required not in names:
            raise SystemExit(f"[error] {path.name}: payload is missing {required}")
    print(f"  [verify] {path.name}: PE32+ x86-64, {len(names)} payload files")


def _mish_chunk_types(blkx: bytes) -> list[int]:
    count = max(0, (len(blkx) - 200) // 40)
    return [int.from_bytes(blkx[200 + index * 40 : 204 + index * 40], "big") for index in range(count)]


def verify_dmg(path: Path) -> None:
    data = path.read_bytes()
    trailer = data[-512:]
    if trailer[:4] != b"koly":
        raise SystemExit(f"[error] {path.name}: no UDIF trailer")
    length = int.from_bytes(trailer[32:40], "big")
    xml_offset = int.from_bytes(trailer[216:224], "big")
    xml_length = int.from_bytes(trailer[224:232], "big")
    xml = data[xml_offset:xml_offset + xml_length]
    try:
        fork = plistlib.loads(xml)["resource-fork"]["blkx"][0]["Data"]
    except Exception as error:  # noqa: BLE001 - any malformed plist is fatal
        raise SystemExit(f"[error] {path.name}: unreadable UDIF plist ({error})")
    if fork[:4] != b"mish":
        raise SystemExit(f"[error] {path.name}: missing the blkx mish block")
    chunks = _mish_chunk_types(fork)
    raw = all(kind == 1 for kind in chunks)
    if raw:
        # Our own writer: the layout and both checksums must add up exactly.
        if xml_offset + xml_length + 512 != len(data):
            raise SystemExit(f"[error] {path.name}: the XML plist does not line up with the trailer")
        if int.from_bytes(trailer[360:364], "big") != zlib.crc32(xml) & 0xFFFFFFFF:
            raise SystemExit(f"[error] {path.name}: plist checksum mismatch")
        if int.from_bytes(trailer[88:92], "big") != zlib.crc32(data[:length]) & 0xFFFFFFFF:
            raise SystemExit(f"[error] {path.name}: data fork checksum mismatch")
    kind = "raw" if raw else "compressed"
    print(f"  [verify] {path.name}: UDIF image, {len(chunks)} chunk(s), {kind}")


def verify_iso(path: Path) -> None:
    data = path.read_bytes()
    if data[0x8001:0x8006] != b"CD001":
        raise SystemExit(f"[error] {path.name}: no ISO9660 primary volume descriptor")
    for required in (b"Install SheepFox.command", b"install-unix.sh", b"userChrome.css"):
        if required not in data:
            raise SystemExit(f"[error] {path.name}: {required.decode()} is missing")
    print(f"  [verify] {path.name}: ISO9660 volume with the payload")


def verify_artifacts(paths: list[Path]) -> None:
    print()
    for path in paths:
        suffix = path.suffix.lower()
        if suffix == ".exe":
            verify_windows(path)
        elif suffix == ".dmg":
            verify_dmg(path)
        elif suffix == ".iso":
            verify_iso(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the SheepFox installers.")
    parser.add_argument("--windows", action="store_true", help="build the Windows .exe")
    parser.add_argument("--macos", action="store_true", help="build the macOS .dmg/.iso")
    parser.add_argument("--zig", help="path to the zig compiler (default: from ziglang)")
    args = parser.parse_args()
    both = not args.windows and not args.macos
    version = read_version()
    print(f"=== (SheepFox) installer build  (version {version}) ===")

    artifacts: list[Path] = []
    if both or args.windows:
        artifacts.append(build_windows(find_zig(args.zig), version))
    if both or args.macos:
        artifacts.extend(build_macos(version))

    verify_artifacts(artifacts)

    print()
    for artifact in artifacts:
        print(f"  {artifact}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
