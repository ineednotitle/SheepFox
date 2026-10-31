# (SheepFox) Zen browser installers

The source of the two artifacts published on every `v*` tag (compatible with both **Zen Browser** and stock **Mozilla Firefox**):

| Artifact | Built from | Runs |
| --- | --- | --- |
| `dist/SheepFox-Setup-<version>.exe` | `installer/windows/launcher.c` | `scripts\install-windows.ps1` |
| `dist/SheepFox-<version>.dmg` | `installer/macos/Install SheepFox.command` | `scripts/install-unix.sh` |
| `dist/SheepFox-<version>.iso` | the same volume as the `.dmg` | — (fallback) |

Nothing is re-implemented inside an installer. Both launchers unpack the payload
(a copy of `scripts/`, `config/` and `LICENSE`/`README.md`) and then run the same
script a git checkout runs, forwarding every switch, so `--strict`, `--no-ui`,
`--no-extensions`, `--uninstall`, `--low-memory`, `--dry-run`, `--doctor`,
`--probe` and `--report` behave identically however you installed SheepFox.

Both ask for administrator rights exactly once: the SheepShields policy goes next
to the Firefox binary, and that policy is what preinstalls **uBlock Origin and
Decentraleyes**. `-ProfileOnly` / `--profile` keeps the install inside the
profile (no admin, no extension preinstall).

## Build them

```bash
pip install ziglang pycdlib     # Zig cross-compiler + ISO writer
make installers                 # or: python3 mozbuild/scripts/build-installers.py

python3 mozbuild/scripts/build-installers.py --windows   # only the .exe
python3 mozbuild/scripts/build-installers.py --macos     # only the .dmg (+ .iso off macOS)
```

`installer/version.txt` is the single source of the version in the file names.
Every build ends by re-opening the artifacts it wrote and checking them: PE
machine/subsystem and the embedded payload for the `.exe`, the UDIF trailer,
plist and chunk table for the `.dmg`, the volume descriptor and payload files for
the `.iso`. A binary that fails verification fails the build.

## Windows

`launcher.c` is compiled with `zig cc -target x86_64-windows-gnu -Wall -Wextra
-Werror` (a warning is a build failure) and the payload zip is linked in as a
byte array, so the target machine needs no toolchain. At run time it:

1. writes the payload to `%TEMP%\sheepfox-setup\payload.zip`,
2. expands it with PowerShell's `Expand-Archive`,
3. runs `payload\scripts\install-windows.ps1` with your switches, and
4. exits with that script's exit code.

`SheepFox-Setup.exe /?` prints the switch list (`-ProfileOnly`, `-NoExtensions`,
`-System`, `-Strict`, `-LowMemory`, `-NoUI`, `-Doctor`, `-Probe`, `-Unprobe`,
`-Report`, `-Uninstall`, `-DryRun`). Elevation is handled by
`install-windows.ps1`: it re-launches itself through UAC, so there is no "run as
administrator" step. No registry writes, no services, no background processes,
no downloads, and the launcher always passes `-NoProfile -ExecutionPolicy
Bypass`, so an ExecutionPolicy error is impossible.

## macOS

The volume holds `SheepFox/` (the payload) plus `Install SheepFox.command` and
`README.txt`. The `.command` calls `sh ./scripts/install-unix.sh` — through `sh`
on purpose, because a mounted read-only image can drop the execute bit — and it
never blocks on `Press Return` when no terminal is attached.

On macOS the image is created by `hdiutil -format UDZO -fs HFS+`. Anywhere else
the volume is written as ISO9660 + Joliet + Rock Ridge with `pycdlib` and wrapped
in a raw UDIF container, and the `.iso` ships alongside it, because that path
cannot be mount-tested outside macOS. If `hdiutil` fails on a macOS host, the
build warns and falls back to the portable writer rather than failing the
release.

The image is unsigned: the first launch may need Control-click → Open, or
*System Settings → Privacy & Security → Open Anyway*.

## CI

`.github/workflows/release-installers.yml` builds the `.exe` on
`windows-latest`, the `.dmg` on `macos-latest` (with `hdiutil verify` plus a real
attach/detach mount test), and the `.iso` on `ubuntu-latest`; on a `v*` tag the
`publish` job attaches all three to the GitHub release.
