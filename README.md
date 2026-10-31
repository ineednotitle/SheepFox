# (SheepFox) Firefox

<p align="center">
  <img src="branding/sheepfox/content/sheepfox-logo.svg" alt="(SheepFox) Firefox logo" width="132" height="132" />
</p>

<p align="center">
  <strong>Brave-class page-load speed · LibreFox-grade privacy · upstream Gecko stability · zero site breakage</strong>
</p>

<p align="center">
  <code>MPL-2.0</code> · <code>Firefox 159.0</code> pin · <code>134 prefs</code> · <code>4 verified upstream patches</code>
</p>

---

## What SheepFox is

> **(SheepFox) Firefox — make Firefox as fast as Brave without losing stability, with
> LibreFox-grade privacy and zero site breakage.**

**(SheepFox) Firefox** — repo slug `SheepFox` — is a hybrid Firefox engineering project that fixes
the trade-off every hardening guide forces on you:

* **Stock Firefox** ships telemetry pings, sponsored New Tab tiles, Pocket, background ML/LLM
  workers, conservative network limits and no ad blocker. Pages load measurably slower than in
  Brave.
* **Ultra-strict hardened forks** turn on `privacy.resistFingerprinting`, which caps 120Hz/144Hz
  panels at 60 Hz, forces light mode, spoofs your timezone to UTC, adds Canvas noise that breaks
  real apps — and *hurts* real-world responsiveness.

SheepFox gives you both halves, in one repository, in two independent modes:

| | What it gives you | Works on |
| :--- | :--- | :--- |
| **Mode 1 — Drop-in suite** | Modular prefs → `user.js`, a system AutoConfig (`sheepfox.cfg`), and **SheepShields** enterprise policy that preinstalls **uBlock Origin + Decentraleyes** | Any stock Firefox on Windows, Linux, macOS (standard, Flatpak, Snap) |
| **Mode 2 — Fork scaffold** | Branding, mozconfigs, a verified patch series and CI to compile a standalone **SheepFox** binary from pinned Mozilla source with cross-language LTO, `x86-64-v3`, LLD and optional PGO | Build host: Linux / Windows (MozillaBuild) / macOS |

Mode 1 takes about ten seconds. Mode 2 takes about an hour of CPU and 40 GB of disk.

---

## Why it feels like Brave without inheriting Brave's problems

| Pillar | Stock Firefox | Strict hardening | **(SheepFox) Firefox** |
| :--- | :--- | :--- | :--- |
| **Ad & tracker blocking** | none — every ad byte is downloaded | manual | **SheepShields `policies.json`** auto-installs uBlock Origin + `easylist`, `easyprivacy`, `ublock-badware`, `ublock-privacy`, `urlhaus-1` |
| **GPU / rendering** | conservative defaults | often disables WebGL and Canvas accel | **WebRender + shader precache + accelerated Canvas (capped at 128 MB) + 20 MB Skia font cache** |
| **Caching** | disk-I/O heavy | often disables caches | **256 MB RAM cache (disk cache off) + 4-page bfcache** |
| **Network transport** | paced requests, 6 conns/host | speculative fetches disabled by default | **HTTP/3 QUIC, unpaced bursts, 1800 max conns, 10 persistent per host** |
| **Certificate revocation** | live OCSP (slow, leaks every domain) | hard-fail OCSP (breaks sites) | **local Mozilla CRLite filters — 0 ms, zero domain leakage** (`security.OCSP.enabled = 0`, `crlite_mode = 2`) |
| **Anti-fingerprinting** | minimal | **RFP**: 60 Hz cap, forced light mode, UTC spoofing, Canvas noise | **granular `privacy.fingerprintingProtection`** — protects against fingerprinting *categories*, leaves refresh rate, timezone, dark mode and WebGL intact |
| **Telemetry, PPA, AI** | on by default | stripped | **stripped and `lockPref`-locked**; `browser.ml.enable = false` stops the LLM worker process entirely |
| **High-refresh displays** | standard | capped at 60 Hz | **120/144/240 Hz mass-spring-damper scroll + APZ physics** |

The one rule that makes this safe: **`privacy.resistFingerprinting` stays `false` by default.**
If you *want* strict RFP, install with `--strict` (`config/overrides/strict-paranoia.override.js`);
it is deliberately never part of the default profile.

---

## Repository layout

```text
SheepFox/
├── config/                          # MODE 1 — drop-in config, AutoConfig & SheepShields
│   ├── modules/                     # the only files you edit
│   │   ├── 01-speedfox.js           # WebRender, Skia, RAM cache, HTTP/3, 1800 conns
│   │   ├── 02-shieldfox.js          # dFPI, FPP, GPC, CRLite, DoH, WebRTC, telemetry locks
│   │   ├── 03-cleanfox.js           # Pocket, sponsored tiles, QuickSuggest, browser.ml.*
│   │   └── 04-smoothfox.js          # 120Hz+ MSD scroll & APZ physics
│   ├── user.js                      # generated — `make build-configs`
│   ├── autoconfig/
│   │   ├── defaults/pref/local-settings.js   # general.config.* bootstrap
│   │   └── sheepfox.cfg                      # generated AutoConfig (line 1 is a comment)
│   ├── distribution/policies.json   # SheepShields: telemetry off + uBlock Origin on
│   └── overrides/                   # user-overrides.example.js, strict-paranoia.override.js,
│                                    #   low-memory.override.js
│
├── branding/sheepfox/               # MODE 2 — SheepFox brand assets
│   ├── configure.sh                 # MOZ_APP_NAME=sheepfox, telemetry env cleared
│   ├── branding.nsi                 # Windows installer strings
│   ├── locales/en-US/               # brand.ftl / brand.dtd / brand.properties
│   └── content/                     # sheepfox-logo.svg, about-wordmark.svg
│
├── mozbuild/                        # MODE 2 — fork build scaffold (never `build/`: keep it
│   ├── firefox-version.json         #   visible to every tool and snapshot)
│   ├── mozconfig.common             # release, hardening, rust-simd, no crashreporter/updater
│   ├── mozconfig.linux-x86_64       # x86-64-v3, LLD, --enable-lto=cross, optional PGO
│   ├── mozconfig.linux-aarch64
│   ├── mozconfig.windows-x86_64
│   ├── mozconfig.macos-universal
│   └── scripts/
│       ├── build-configs.py         # module compiler + `--check` gate
│       ├── fetch-source.sh          # download + SHA-512 verify the pinned tarball
│       ├── apply-patches.sh         # branding, staging, patches/series
│       ├── build-browser.sh         # mach configure → build → package → inject config
│       └── build-installers.py      # dist/SheepFox-Setup-*.exe, SheepFox-*.dmg, *.iso
│
├── patches/                         # verified against FIREFOX_159_0_RELEASE
│   ├── series
│   └── 0001…0004-*.patch
├── installer/                       # MODE 1 — the double-click installers
│   ├── version.txt                  # the version stamped into the artifact names
│   ├── windows/launcher.c           # source of SheepFox-Setup-<ver>.exe
│   └── macos/                       # "Install SheepFox.command" + README.txt
│
├── extensions/floating-urlbar/      # the optional Floating URL Bar WebExtension
│   ├── manifest.json                # MV3, Gecko id floating-urlbar@sheepfox
│   ├── core.js                      # URL interpretation + ranking (pure, node-tested)
│   ├── background.js                # shortcut, query pipeline, surface selection
│   ├── ui.js / styles.js            # shared renderer (ARIA combobox pattern)
│   ├── content.js / window.js       # in-page overlay / popup-window surface
│   └── search.html, icons/bar.svg
│
├── scripts/                         # install.py, install-unix.sh, install-windows.{bat,ps1}
├── tests/test_repo.py               # 96 tests, stdlib only (node for the extension)
├── tests/extension/core.test.js     # 17 node tests: URL parsing and ranking
├── tests/extension/ui.test.js       # 12 jsdom tests: rows, keyboard, cleanup, no HTML injection
└── .github/workflows/               # validate-configs.yml, release-installers.yml,
                                     #   build-sheepfox.yml (fork compile, manual)
```

---

## Quick start — Mode 1: drop-in on stock Firefox

Backups of any existing `user.js` are written first (`user.js.sheepfox-backup-<timestamp>`).

### Linux

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run      # preview every path first

./scripts/install-unix.sh                # user.js + SheepShields policy
                                         #   (asks for sudo once: the policy lives next to the
                                         #    Firefox binary, and that is what preinstalls
                                         #    uBlock Origin + Decentraleyes)
sudo ./scripts/install-unix.sh --system  # same, plus the AutoConfig files
./scripts/install-unix.sh --no-extensions  # policy without the extension preinstall
```

Flatpak (`~/.var/app/org.mozilla.firefox/...`) and Snap (`~/snap/firefox/common/...`) profiles
are detected automatically; system dirs for both are probed for `--system`.

### macOS

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run
./scripts/install-unix.sh            # profiles + policy (macOS asks for the admin password once)
sudo ./scripts/install-unix.sh --system   # + AutoConfig in /Applications/Firefox.app/Contents/Resources
```

### Windows

Double-click or run the `.bat` launcher — it bypasses `ExecutionPolicy` for you, so you will
never see *"…install-windows.ps1 is not digitally signed"*:

```powershell
.\scripts\install-windows.bat                  # user.js + CSS + policy (asks for UAC once)
.\scripts\install-windows.bat -ProfileOnly     # profile only: no policy, no admin needed
.\scripts\install-windows.bat -Strict          # same, plus strict anti-fingerprinting
.\scripts\install-windows.bat -NoExtensions    # policy, but preinstall no extensions
.\scripts\install-windows.bat -Uninstall       # remove everything again
```

> **Windows notes**
> * Always prefix the path with `.\` in PowerShell. Without it, a missing file is interpreted as
>   the module-qualified command `scripts\install-windows.bat` and you get the confusing
>   *"The module 'scripts' could not be loaded"* error instead of "file not found".
> * Comments must be `#` in PowerShell. The `::` form in older examples is a **cmd.exe-only**
>   comment; in PowerShell it is parsed as arguments and produces
>   *"The term 'uBlock' is not recognized…"*. Copy the commands only, never the annotation.
> * Verify you have the current files: `Get-ChildItem .\scripts` must list
>   `install-windows.bat`. If it does not, run `git pull` — the `.bat` launcher was added in
>   commit `a0642a6`.

The launcher calls
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" %*`.
The PowerShell installer unblocks downloaded files, parses
`%APPDATA%\Mozilla\Firefox\profiles.ini` (`[Install*] Default=` first), auto-elevates through UAC
for `-System`, and writes every file as **BOM-free UTF-8** via
`New-Object System.Text.UTF8Encoding($false)`.

Cross-platform alternative:

```powershell
python scripts\install.py --dry-run
python scripts\install.py --strict
python scripts\install.py --no-extensions
python scripts\install.py --system --uninstall
```

### The two extensions: uBlock Origin + Decentraleyes

Both are preinstalled for you, in every mode, with no trip to addons.mozilla.org. They arrive
through **SheepShields**, the Enterprise Policy file (`distribution/policies.json`) that the
installer writes next to the Firefox binary:

| Extension | ID | Why it is here |
| :--- | :--- | :--- |
| uBlock Origin | `uBlock0@raymondhill.net` | Blocks ads/trackers with the curated list set in `3rdparty`; the single biggest speed and privacy win |
| Decentraleyes | `jid1-BoFifL9Vbdl2zQ@jetpack` | Serves the common CDN libraries locally, so Google/Facebook-style CDN requests never leave the browser |

Both use `"installation_mode": "normal_installed"`: Firefox installs them on the next start, and
**you can still disable or remove them** in `about:addons`. Nothing is force-locked — that keeps
the "reversible" promise and keeps a broken extension from being unremovable.

Because the policy file lives beside the Firefox binary (`/etc/firefox/policies`,
`Firefox.app/Contents/Resources`, `C:\Program Files\Mozilla Firefox`), installing it needs
administrator rights once: `sudo` on Linux/macOS, UAC on Windows — the installer asks by itself,
you never have to remember `-System`. If you would rather not, `--no-extensions` /
`-NoExtensions` writes the same policy without the two extension entries, and `--profile` /
`-ProfileOnly` keeps everything inside the profile.

Verify in Firefox: `about:policies` shows *ExtensionSettings* as **Active**, and `about:addons`
lists uBlock Origin and Decentraleyes within a few seconds of the first start. If the machine is
offline at that moment, Firefox downloads them on the first start where AMO is reachable.

### UI: stock Firefox, deliberately untouched

SheepFox does not style the browser interface. Releases up to **1.2** also wrote
`chrome/userChrome.css` + `chrome/userContent.css` into the profile (a floating Zen/Arc-style
search pill on `Ctrl+T` / `Ctrl+L`); that theme is **removed**. A profile now receives a `user.js`
and nothing else, so the toolbar, the New Tab page, the tab strip and every menu are exactly what
Mozilla ships. `toolkit.legacyUserProfileCustomizations.stylesheets` is no longer set either, so
Firefox never even looks for profile CSS.

It was the wrong shape of feature for this suite: browser-UI CSS is the one part that breaks on
every Firefox redesign, needs a per-version selector matrix to stay alive, and is the first thing
to go wrong for someone who only wanted the speed and privacy prefs.

Upgrading from 1.2 or older? The installer deletes the leftover `chrome/userChrome.css`,
`chrome/userContent.css` and `chrome/sheepfox-probe.css` from every profile it touches, and
`--uninstall` removes them too — `--doctor` prints them if they are still there.

If you still want a floating bar, there is one that is *allowed* to exist:
[**the Floating URL Bar WebExtension**](#floating-url-bar-optional-extension) below — its own
overlay on `Ctrl+Shift+Space`, installable and removable like any add-on.

```bash
./scripts/install-unix.sh                  # user.js + SheepShields policy (no UI files)
./scripts/install-unix.sh --low-memory     # minimal-RAM override (see below)
```

```powershell
.\scripts\install-windows.bat
.\scripts\install-windows.bat -LowMemory
```

### Reverting

```bash
python3 scripts/install.py --system --uninstall     # removes what SheepFox installed (incl. the policy)
```

On Windows: `.\scripts\install-windows.bat -Uninstall -System`

Timestamped backups are always left in place; restore the newest
`user.js.sheepfox-backup-*` to get your old profile config back.

---

## Installers: `SheepFox-Setup-<version>.exe` and `SheepFox-<version>.dmg`

Both installers are thin wrappers around the *same* `scripts/` the git checkout
runs. Nothing is re-implemented inside them, so a fix to `config/` — a preference,
a policy, an override — reaches the installers the next time they are built,
and every switch below behaves identically whatever way you install SheepFox.

| Artifact | Platform | What double-clicking it does |
| --- | --- | --- |
| `SheepFox-Setup-<version>.exe` | Windows 10/11, x86-64 | Unpacks the payload to `%TEMP%\sheepfox-setup`, then runs `scripts\install-windows.ps1` with your switches |
| `SheepFox-<version>.dmg` | macOS 11+, Intel & Apple silicon | Mounts a volume holding the payload and **Install SheepFox.command**; runs `scripts/install-unix.sh` |
| `SheepFox-<version>.iso` | any (fallback) | Same volume as ISO9660/Joliet, for hosts that will not mount the UDIF image |

The executables are built by CI for every `v*` tag and attached to the release:
<https://github.com/ineednotitle/SheepFox/releases/latest>.

### Using them

**Windows.** Double-click `SheepFox-Setup-<version>.exe`. A console window shows
the progress and stays readable, so nothing fails silently.

```bat
:: run it from a terminal and forward any installer switch
SheepFox-Setup-1.0.0.exe -System -LowMemory
SheepFox-Setup-1.0.0.exe /?
```

`/?` prints the switch list (`-ProfileOnly`, `-NoExtensions`, `-System`,
`-Strict`, `-LowMemory`, `-Doctor`, `-Report`, `-Uninstall`, `-DryRun`). A plain double-click installs the policy too, so UAC
prompts once — that is what preinstalls uBlock Origin and Decentraleyes. There
is no separate "run as administrator" step, and no PowerShell ExecutionPolicy
error because the launcher always passes `-ExecutionPolicy Bypass -NoProfile`.

**macOS.** Open the `.dmg` and double-click **Install SheepFox.command**. macOS
attaches an unsigned build with a quarantine flag, so the first launch may need
Control-click → **Open**, or *System Settings → Privacy & Security → Open Anyway*.
If the mount is read-only and the execute bit did not survive, the image's
`README.txt` tells you to run:

```bash
sh "/Volumes/SheepFox/Install SheepFox.command" --doctor
```

**Neither installer** writes a registry key, installs a service, starts a
background process or downloads anything. They copy the same `user.js`,
`policies.json` and AutoConfig files as Mode 1, back up whatever
they replace, and exit. `-Uninstall` / `--uninstall` removes everything again.

### Building them yourself

```bash
pip install ziglang pycdlib        # Zig cross-compiler + ISO writer
make installers                    # or: python3 mozbuild/scripts/build-installers.py

# one platform at a time
python3 mozbuild/scripts/build-installers.py --windows   # -> dist/SheepFox-Setup-<ver>.exe
python3 mozbuild/scripts/build-installers.py --macos     # -> dist/SheepFox-<ver>.dmg + .iso
```

`installer/version.txt` is the single source of the version in the file names.
The `.exe` is a real PE32+ executable compiled from `installer/windows/launcher.c`
with `zig cc -target x86_64-windows-gnu -Wall -Wextra -Werror`; the payload zip is
linked in as a byte array, so no runtime toolchain is needed on the target machine.
On macOS the build uses `hdiutil` for a native HFS+ compressed image; everywhere
else it writes the ISO9660/Joliet volume with `pycdlib` and wraps it in a UDIF
container, shipping the `.iso` alongside it.

---

## Quick start — Mode 2: build (SheepFox) Firefox from source

```bash
# 0. build dependencies once
./mach bootstrap --application-choice browser      # inside the fetched tree

# 1. download + SHA-512 verify the pinned Firefox 159.0 source tarball
make fetch-source

# 2. compile configs, inject branding/policies, apply patches/series
make patch-source

# 3. configure → build → package → inject AutoConfig (add SHEEPFOX_PGO=1 for 2-stage PGO)
make build-browser TARGET=linux-x86_64
```

Supported `TARGET` values:

| Target | Optimisation | Typical host |
| :--- | :--- | :--- |
| `linux-x86_64` | `-march=x86-64-v3` (AVX2/FMA), LLD, `--enable-lto=cross`, optional PGO | Linux x86_64 |
| `linux-aarch64` | ARMv8-A + NEON, LLD, `--enable-lto=full` | ARM64 Linux |
| `windows-x86_64` | clang-cl, `x86-64-v3`, LLD, `--enable-lto=cross` | Windows + MozillaBuild |
| `macos-universal` | two slices (`aarch64` + `x86_64`) lipo-merged | macOS + Xcode CLT |

Artifacts land in `mozbuild/firefox-src/obj-*/dist/`, with `sheepfox.cfg`,
`defaults/pref/local-settings.js` and `distribution/policies.json` injected into `dist/bin` by
`build-browser.sh`, so the packaged browser behaves exactly like a Mode 1 install.

**Build notes (verified against the pinned tag, not guessed):**

* `--enable-jxl` is **not** a Firefox 159 configure switch; JPEG-XL ships compiled in and gated by
  `image.jxl.enabled` (already `true` upstream). Passing an unknown switch aborts configure.
* `gfx.webrender.all` is *not* forced in the patch series: Firefox picks WebRender per GPU/driver,
  and forcing it on unsupported hardware is the classic GPU-process crash. SheepFox sets it in
  `01-speedfox.js` where a user can revert it, and never disables `layers.gpu-process.enabled`.
* `x86-64-v3` requires Haswell (2013+) or Excavator/Zen (2015+). For older CPUs build with
  `linux-aarch64`-style generic flags instead of `linux-x86_64`.
* The patch series is generated against `FIREFOX_159_0_RELEASE` and every patch passes
  `git apply --check` against that exact tag. Bumping `mozbuild/firefox-version.json` requires
  re-verifying the series.

---

## Floating URL Bar (optional extension)

`extensions/floating-urlbar/` is a WebExtension that brings the Arc/Zen floating search back —
*without* profile CSS. Press **`Ctrl+Shift+Space`** (`Command+Shift+Space`) on any page and a pill
appears, styled like the 1.2 theme, searching your **open tabs, bookmarks, history and the web** in
one list while a typed URL is the first row.

**Why an extension is not a `userChrome.css` replacement:** a WebExtension cannot touch the browser
chrome — `#urlbar` is off-limits to add-ons, so no extension can float Mozilla's own bar. This one
ships its own surface instead: an in-page overlay inside a closed shadow root on normal pages, and a
small popup window on `about:` pages, `addons.mozilla.org` or the PDF viewer, where injection is
impossible. The shortcut never silently does nothing.

| | |
| :--- | :--- |
| **Shortcut** | `Ctrl+Shift+Space` (remappable in `about:addons` → gear → *Manage Extension Shortcuts*) |
| **Permissions** | `activeTab`, `scripting`, `tabs`, `history`, `bookmarks`, `search` — no host permissions, no `content_scripts` |
| **Network** | none: no telemetry, no analytics, no search suggestions, no remote code |
| **Surfaces** | in-page overlay (closed shadow root, removed on close/navigate) + popup window fallback |

Release Firefox refuses **unsigned** extensions, so the extension is *not* bundled into the
installers — that would only produce a disabled add-on and a mystery. Two honest ways to run it:

```bash
# try it now, no signing (lasts until Firefox restarts):
#   about:debugging#/runtime/this-firefox -> Load Temporary Add-on -> pick the .xpi

make extension          # -> dist/SheepFox-Floating-URL-Bar-<version>.xpi
make extension-check    # validate the manifest and sources only (CI gate)

# keep it: sign with your own free AMO account, then install normally
npx web-ext sign --channel unlisted --api-key "$AMO_JWT_ISSUER" \
  --api-secret "$AMO_JWT_SECRET" --source-dir extensions/floating-urlbar
```

The extension's own tests need node; the DOM ones also need the optional jsdom harness:

```bash
npm install --prefix tests/extension   # once; without it the DOM tests skip cleanly
node tests/extension/core.test.js      # 17 tests: URL parsing, ranking, row cap
node tests/extension/ui.test.js        # 12 tests: rendering, keyboard, ARIA, cleanup
```

Full details, the permission rationale and the design notes are in
[`extensions/floating-urlbar/README.md`](extensions/floating-urlbar/README.md).

---

## Verification

```bash
make build-configs     # regenerate user.js + sheepfox.cfg from config/modules/*.js
make check             # fail if either generated file is stale
make test              # 96 tests (stdlib unittest + node/jsdom for the extension)
make extension-check   # validate the extension manifest and sources
make verify            # check + extension-check + test
```

What the suite enforces:

1. `config/modules/*.js` ↔ `config/user.js` ↔ `config/autoconfig/sheepfox.cfg` stay in sync.
2. `sheepfox.cfg` line 1 is a comment, contains no `user_pref(`, and uses `lockPref()` **only**
   for `// @lock` lines (everything else is `defaultPref()`, so it stays editable in Settings).
3. Core speed/privacy invariants: dFPI `cookieBehavior = 5`, GPC, query stripping, HTTPS-Only,
   CRLite (`OCSP.enabled = 0`, `crlite_mode = 2`), Quad9 DoH (`trr.mode = 2`), WebRTC
   `default_address_only`, 128 MB canvas cache, 20 MB Skia cache, 256 MB RAM cache, HTTP/3,
   1800 connections, `nglayout.initialpaint.delay = 0`, and no dead `sessionhistory` knob.
4. Zero-breakage invariants: `resistFingerprinting = false` and **not locked**,
   `fingerprintingProtection = true`, `layers.gpu-process.enabled = true`.
5. Telemetry/PPA/studies/Pocket/sponsored/ML preferences are `false` **and** locked.
6. `policies.json` provisions uBlock Origin (`uBlock0@raymondhill.net`, `normal_installed`) with the
   curated filter lists, and never disables application updates.
7. Branding SVGs parse as XML, are vector-only (no `<script>`, no raster `<image>`).
8. Every patch matches its own diffstat, every hunk's line counts match its `@@` header, and
   `patches/series` lists exactly the `.patch` files present.
9. Windows `.bat`/`.ps1` are BOM-free, CRLF, contain the `ExecutionPolicy Bypass` invocation,
   `Unblock-File`, UAC re-launch and `UTF8Encoding($false)` writes.
10. A mock profile exercises install → backup → `--system` → `--strict` → `--low-memory` →
    `--uninstall`, and `--dry-run` is proven to write nothing.
11. Resource-footprint prefs stay below Firefox's defaults, and the low-memory override never
    leaks into the default profile.

---

## Troubleshooting: a change did not apply

Run the built-in doctor first — it reports the exact profile in use and whether each piece landed:

```powershell
.\scripts\install-windows.bat -Doctor
```

```bash
python3 scripts/install.py --doctor
```

It checks that `user.js` is present and how many `user_pref` lines it carries, the system files
(`sheepfox.cfg`, `local-settings.js`, `policies.json`), the extension preinstall, and whether your
SheepFox files ended up in a **different profile than the one Firefox launches** — the single most
common cause. It also lists leftovers from the retired 1.2 search-bar theme.

Still stuck? Write a full report and paste it:

```powershell
.\scripts\install-windows.bat -Report      # -> sheepfox-report.txt
```

```bash
python3 scripts/install.py --report report.txt
```

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Doctor says the files are missing | installers write to the **active** profile only | `.\scripts\install-windows.bat -ProfilePath "%APPDATA%\Mozilla\Firefox\Profiles\<yours>"` |
| Doctor passes, nothing changes | Firefox still running (config is read at startup) | quit fully — Task Manager must show no `firefox.exe` — then relaunch |
| Profile still has `chrome/userChrome.css` | installed over SheepFox 1.2 or older | re-run the installer (it deletes the retired theme files), or `--uninstall` |
| Windows Store Firefox | profile lives under `%LOCALAPPDATA%\Packages\Mozilla.Firefox_*` | handled automatically now; `-Doctor` prints the profile it uses (override with `-ProfilePath`) |
| Prefs look inert | a later `user.js` writer (another hardening tool) overwrote yours | re-run the installer last, or merge the two files |

Prove *where* your profile is:

```powershell
Get-ChildItem "$env:APPDATA\Mozilla\Firefox\Profiles" -Directory |
  ForEach-Object { "$($_.Name)  user.js=$(Test-Path (Join-Path $_.FullName 'user.js'))" }
```

## RAM & CPU footprint

Firefox defaults are tuned for marketing benchmarks, not for idle cost. On top of stripping
telemetry/ML/Pocket workers, SheepFox ships these measured knobs in `config/modules/01-speedfox.js`:

| Pref | Firefox | SheepFox | Effect |
| :--- | :--- | :--- | :--- |
| `dom.ipc.processCount` | 8 | **6** | each content process carries a fixed baseline RSS; fewer processes = less idle RAM, site isolation kept |
| `media.cache_size` | 512000 KiB (~500 MB) | **131072 KiB (128 MB)** | long video sessions stop pinning hundreds of MB of watched segments |
| `browser.sessionstore.interval` | 15 s | **60 s** | fewer background disk writes and wakeups; crash recovery unchanged |
| `browser.tabs.unloadOnLowMemory` | true | **true** | idle tabs are discarded instead of swapping/crashing |
| `browser.ml.enable` | true | **false** | no inference worker process at all |
| `browser.cache.disk.enable` | true | **false** | no disk cache; hot assets come from the 256 MB RAM cache |
| `gfx.canvas.accelerated.cache-size` | 256 MB | **128 MB** | canvas surfaces stay resident without a second browser's worth of VRAM |
| `nglayout.initialpaint.delay` | 0 ms | **0 ms** | (was 5 ms here — that *delayed* first paint for no benefit) |

### Need even less? `--low-memory`

For 4 GB machines, VMs, or 50-tab sessions:

```bash
python3 scripts/install.py --low-memory
```

```powershell
.\scripts\install-windows.bat -LowMemory
```

This appends `config/overrides/low-memory.override.js`: one content process
(`dom.ipc.processCount = 2`), **`fission.autostart = false`**, 64 MB memory cache, 32 MB media
cache, single bfcache entry, and aggressive idle-tab unloading. That is where the big saving comes
from — and it is exactly why it is opt-in: disabling Fission means a compromised renderer can share
a process with other sites. Use it for memory pressure, not by default.

## How `// @lock` works

Only data-transmitting preferences are locked:

```js
user_pref("toolkit.telemetry.enabled", false); // @lock   ->  lockPref(...)   in sheepfox.cfg
user_pref("gfx.webrender.all", true);                     ->  defaultPref(...) in sheepfox.cfg
```

`lockPref()` cannot be overridden from `about:preferences`; `defaultPref()` sets a hardened
default the user may still change. That is the difference between "private by default" and
"a fork that fights you".

---

## Known trade-offs (read before filing a bug)

* **Disk cache is off** (`browser.cache.disk.enable = false`) in favour of a 256 MB RAM cache.
  On machines with less than ~4 GB RAM, re-enable it via
  `config/overrides/user-overrides.example.js`.
* **Captive-portal detection is off** (`network.captive-portal-service.enabled = false`) because it
  is a background phone-home. Hotel/airport Wi-Fi portals therefore need one manual visit to the
  portal URL.
* **DoH mode 2** prefers Quad9 but still falls back to system DNS, so LAN-only devices and captive
  portals keep working. `--strict` switches to mode 3 (no fallback).
* **A few legacy preferences are pinned defensively.** `toolkit.telemetry.*`, `toolkit.coverage.*`,
  `dom.private-attribution.submission.enabled` and `extensions.pocket.enabled` are kept in the
  profiles even where a given Firefox release no longer reads them: they cover older releases and
  ESR, and they keep a future reintroduction switched off. Every *speed* preference shipped here
  exists in Firefox 159's `StaticPrefList.yaml` / `all.js` / `firefox.js`.
* **No benchmark claims.** Numbers vary by machine, network and page. The defaults here are the
  documented Gecko/WebRender/Necko knobs that move first-paint latency and scroll smoothness, not
  invented measurements.

---

## Contributing & security

* [`CONTRIBUTING.md`](CONTRIBUTING.md) — pref/patch workflow and the three invariants.
* [`SECURITY.md`](SECURITY.md) — threat model and how to report a regression.
* LICENSE: **[MPL-2.0](LICENSE)**.

## Acknowledgements

Inspired by **LibreFox/LibreWolf** (privacy vision), **Betterfox** (zero-breakage tuning),
**Brave Shields** (out-of-the-box blocking) and **Mercury** (compiler optimisation). Built entirely
on Mozilla Firefox source, and not affiliated with or endorsed by Mozilla. Firefox is a trademark
of the Mozilla Foundation.
