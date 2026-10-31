# (SheepFox) Zen browser

<p align="center">
  <img src="branding/sheepfox/content/sheepfox-logo.svg" alt="(SheepFox) Zen browser logo" width="132" height="132" />
</p>

<p align="center">
  <strong>Brave-class page-load speed · LibreFox-grade privacy · upstream Zen / Gecko stability · zero site breakage</strong>
</p>

<p align="center">
  <code>MPL-2.0</code> · <code>Zen Browser + Gecko 159.0</code> · <code>137 prefs</code> · <code>4 verified upstream patches</code>
</p>

---

## What SheepFox is

> **(SheepFox) Zen browser — Make Zen browser as fast as Brave without losing stability, with
> LibreFox-grade privacy and zero site breakage.**

**(SheepFox) Zen browser** — repo slug `SheepFox` — is a hybrid **Zen Browser & Gecko** engineering
project that fixes the trade-off every hardening guide forces on you:

* **Out-of-the-box Zen Browser (and stock Firefox)** leaves live OCSP domain lookups enabled,
  conservative Gecko RAM/network ceilings in place, background ML/LLM workers & PPA active, and
  ships **no built-in ad or tracker blocker** — so pages still download every ad byte and load
  measurably slower than in Brave.
* **Ultra-strict hardened templates** turn on `privacy.resistFingerprinting`, which **destroys Zen
  Browser's signature UX**: capping 120Hz/144Hz/240Hz panels at 60 Hz, breaking dark mode and
  Windows Mica / macOS vibrancy backdrops, spoofing your timezone to UTC, and adding Canvas noise
  that breaks real web apps.

SheepFox gives you both halves, in one repository, in two independent modes:

| | What it gives you | Works on |
| :--- | :--- | :--- |
| **Mode 1 — Drop-in suite** | Modular prefs → `user.js`, a system AutoConfig (`sheepfox.cfg`), Zen-isolated CSS, and **SheepShields** enterprise policy that preinstalls **uBlock Origin + Decentraleyes** | **Zen Browser** (native, per-user, AUR/tarball, Flatpak `app.zen_browser.zen`) **and stock Mozilla Firefox** across Windows, Linux, macOS |
| **Mode 2 — Fork scaffold** | Branding, mozconfigs, a verified patch series and CI to compile a standalone **(SheepFox) Zen browser** binary from pinned Gecko 159.0 source with cross-language LTO, `x86-64-v3`, LLD and optional PGO | Build host: Linux / Windows (MozillaBuild) / macOS |

Mode 1 takes about ten seconds. Mode 2 takes about an hour of CPU and 40 GB of disk.

---

## Why it feels like Brave without inheriting Brave's problems

| Pillar | Stock Zen / Firefox | Strict RFP hardening | **(SheepFox) Zen browser** |
| :--- | :--- | :--- | :--- |
| **Ad & tracker blocking** | none — every ad byte is downloaded | manual | **SheepShields `policies.json`** auto-installs uBlock Origin + Decentraleyes + `easylist`, `easyprivacy`, `ublock-badware`, `ublock-privacy`, `urlhaus-1` |
| **GPU / rendering** | conservative defaults | often disables WebGL and Canvas accel | **WebRender + shader precache + 512 MB accelerated Canvas + 20 MB Skia font cache** |
| **Caching** | disk-I/O heavy | often disables caches | **256 MB RAM cache (disk cache off) + 4-page bfcache** |
| **Network transport** | paced requests, 6 conns/host | speculative fetches disabled by default | **HTTP/3 QUIC, unpaced bursts, 1800 max conns, 10 persistent per host** |
| **Certificate revocation** | live OCSP (slow, leaks every domain) | hard-fail OCSP (breaks sites) | **local Mozilla CRLite filters — 0 ms, zero domain leakage** (`security.OCSP.enabled = 0`, `crlite_mode = 2`) |
| **Anti-fingerprinting** | minimal | **RFP**: 60 Hz cap, forced light mode, UTC spoofing, Canvas noise | **granular `privacy.fingerprintingProtection`** — protects against fingerprinting *categories*, leaves 120Hz+, Zen Mica/vibrancy, dark mode, timezone and WebGL intact |
| **Telemetry, PPA, AI** | PPA / ML workers active unless stripped | stripped | **stripped and `lockPref`-locked** (`toolkit.telemetry.*`, `dom.private-attribution.*`, `zen.urlbar.show-sponsored = false`, `browser.ml.enable = false`) |
| **Zen Workspaces & 120Hz+ UI** | standard | broken by RFP / container blocks | **Container-backed Workspaces enabled + 120/144/240 Hz mass-spring-damper scroll + APZ physics** |

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
│   │   ├── 03-cleanfox.js           # Pocket, sponsored tiles/URLBar, QuickSuggest, browser.ml.*
│   │   └── 04-smoothfox.js          # 120Hz+ MSD scroll & APZ physics
│   ├── user.js                      # generated — `make build-configs`
│   ├── autoconfig/
│   │   ├── defaults/pref/local-settings.js   # general.config.* bootstrap
│   │   └── sheepfox.cfg                      # generated AutoConfig (line 1 is a comment)
│   ├── chrome/                      # Zen-safe UI stylesheets (:not(:has(#zen-main-app-wrapper)))
│   │   ├── userChrome.css           #   preserves Zen native UI; adds Zen floating pill on Firefox
│   │   └── userContent.css          #   clears Mozilla New Tab wordmark, lifts the shortcuts
│   ├── distribution/policies.json   # SheepShields: telemetry off + uBlock Origin + Decentraleyes
│   └── overrides/                   # user-overrides.example.js, strict-paranoia.override.js,
│                                    #   low-memory.override.js
│
├── branding/sheepfox/               # MODE 2 — (SheepFox) Zen browser brand assets
│   ├── configure.sh                 # MOZ_APP_NAME=sheepfox, telemetry env cleared
│   ├── branding.nsi                 # Windows installer strings ("(SheepFox) Zen browser")
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
├── patches/                         # verified against FIREFOX_159_0_RELEASE (Zen's Gecko base)
│   ├── series
│   └── 0001…0004-*.patch
├── installer/                       # MODE 1 — the double-click installers
│   ├── version.txt                  # the version stamped into the artifact names
│   ├── windows/launcher.c           # source of SheepFox-Setup-<ver>.exe
│   └── macos/                       # "Install SheepFox.command" + README.txt
│
├── scripts/                         # install.py, install-unix.sh, install-windows.{bat,ps1}
├── tests/test_repo.py               # automated verification suite, stdlib only
└── .github/workflows/               # validate-configs.yml, release-installers.yml,
                                     #   build-sheepfox.yml (fork compile, manual)
```

---

## Quick start — Mode 1: drop-in on Zen Browser (and stock Firefox)

The installer discovers **Zen Browser first** across every platform and install format, and also
supports stock Mozilla Firefox out of the box (pass `--browser zen` or `-Browser zen` to target Zen
Browser exclusively). Backups of any existing `user.js` are written first
(`user.js.sheepfox-backup-<timestamp>`).

| Platform | Zen Browser profile roots probed | Zen Browser install dirs probed (`policies.json` + AutoConfig) |
| :--- | :--- | :--- |
| **Windows** | `%APPDATA%\zen`, `%APPDATA%\Zen Browser`, portable `Zen Browser\profile` | `C:\Program Files\Zen Browser`, `%LOCALAPPDATA%\Zen Browser`, `Zen Twilight`, `App Paths\zen.exe` |
| **macOS** | `~/Library/Application Support/zen` | `/Applications/Zen.app/Contents/Resources`, `/Applications/Zen Browser.app/Contents/Resources`, `~/Applications/Zen.app/...` |
| **Linux** | `~/.zen`, `$XDG_CONFIG_HOME/zen` (`~/.config/zen`), Flatpak `~/.var/app/app.zen_browser.zen/.zen` | `/opt/zen-browser`, `/opt/zen`, `/usr/lib/zen-browser`, Flatpak `app.zen_browser.zen` |

*(Stock Firefox roots — `%APPDATA%\Mozilla\Firefox`, MSIX Store, `~/Library/Application Support/Firefox`, `~/.mozilla/firefox`, Flatpak `org.mozilla.firefox`, Snap `firefox` — are also auto-detected automatically.)*

### Linux

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run      # preview every Zen Browser / Firefox path first

./scripts/install-unix.sh                # user.js + CSS + SheepShields policy
                                         #   (asks for sudo once if /opt/zen-browser needs root:
                                         #    that policy preinstalls uBlock Origin + Decentraleyes)
./scripts/install-unix.sh --browser zen  # target Zen Browser exclusively
sudo ./scripts/install-unix.sh --system  # same, plus the AutoConfig files (sheepfox.cfg)
./scripts/install-unix.sh --no-extensions  # policy without the extension preinstall
```

### macOS

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run
./scripts/install-unix.sh                  # Zen Browser + Firefox profiles + policy
./scripts/install-unix.sh --browser zen    # Zen Browser only
sudo ./scripts/install-unix.sh --system    # + AutoConfig inside Zen.app/Contents/Resources
```

### Windows

Double-click or run the `.bat` launcher — it bypasses `ExecutionPolicy` for you, so you will
never see *"…install-windows.ps1 is not digitally signed"*:

```powershell
.\scripts\install-windows.bat                  # Zen Browser (+ Firefox) user.js + CSS + policy
.\scripts\install-windows.bat -Browser zen     # target Zen Browser exclusively
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

The launcher calls
`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" %*`.
The PowerShell installer unblocks downloaded files, parses `%APPDATA%\zen\profiles.ini` (and
`%APPDATA%\Mozilla\Firefox\profiles.ini`, `[Install*] Default=` first, recognizing Zen's
`*.Default (release)` and `*.Default Profile` naming), auto-elevates through UAC for `-System`, and
writes every file as **BOM-free UTF-8** via `New-Object System.Text.UTF8Encoding($false)`.

Cross-platform alternative:

```powershell
python scripts\install.py --dry-run
python scripts\install.py --browser zen
python scripts\install.py --strict
python scripts\install.py --no-extensions
python scripts\install.py --system --uninstall
```

### The two extensions: uBlock Origin + Decentraleyes

Both are preinstalled for you, in every mode, with no trip to addons.mozilla.org. They arrive
through **SheepShields**, the Enterprise Policy file (`distribution/policies.json`) that the
installer writes next to the Zen Browser (or Firefox) binary:

| Extension | ID | Why it is here |
| :--- | :--- | :--- |
| uBlock Origin | `uBlock0@raymondhill.net` | Blocks ads/trackers with the curated list set in `3rdparty`; the single biggest speed and privacy win |
| Decentraleyes | `jid1-BoFifL9Vbdl2zQ@jetpack` | Serves the common CDN libraries locally, so Google/Facebook-style CDN requests never leave the browser |

Both use `"installation_mode": "normal_installed"`: Zen Browser / Firefox installs them on the next
start, and **you can still disable or remove them** in `about:addons`. Nothing is force-locked —
that keeps the "reversible" promise and keeps a broken extension from being unremovable.

Verify in Zen Browser (or Firefox): `about:policies` shows *ExtensionSettings* as **Active**, and
`about:addons` lists uBlock Origin and Decentraleyes within a few seconds of the first start.

### UI: Zen Browser native preservation + stock Firefox floating search pill

* **Inside Zen Browser (`#zen-main-app-wrapper` detected):** Zen Browser already ships its own
  native floating URL bar (`zen.urlbar.replace-newtab = true`), vertical sidebar tabs, Compact Mode
  slide animations, Workspaces, Split View and Glance. `config/chrome/userChrome.css` gates every
  floating-pill replacement rule behind `:root:not(:has(#zen-main-app-wrapper))`, so Zen's native
  chrome and `#navigator-toolbox` transforms are **100% untouched** while keeping the non-intrusive
  `"SheepFox UI"` proof-of-load badge and `--probe` diagnostic support.
* **Inside stock Mozilla Firefox (no `#zen-main-app-wrapper`):** Open a new tab (`Ctrl+T`), or focus
  the address bar on any page (`Ctrl+L` / clicking it), and the bar detaches from the toolbar and
  floats in the middle of the page as a compact Zen/Arc-style rounded pill (52 px, max 620 px wide,
  centred at `42vh`), docking cleanly back into the toolbar on normal pages.

It ships as **profile CSS**, not a patch, so it is instantly reversible:

```bash
./scripts/install-unix.sh                # installs config/chrome/*.css into <profile>/chrome/
./scripts/install-unix.sh --no-ui        # everything except the UI stylesheets
./scripts/install-unix.sh --low-memory   # minimal-RAM override (see below)
```

```powershell
.\scripts\install-windows.bat
.\scripts\install-windows.bat -NoUI
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
a policy, `userChrome.css` — reaches the installers the next time they are built,
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
SheepFox-Setup-1.0.0.exe -Browser zen -System
SheepFox-Setup-1.0.0.exe /?
```

**macOS.** Open the `.dmg` and double-click **Install SheepFox.command** (or run
`sh "/Volumes/SheepFox/Install SheepFox.command" --doctor`).

### Building them yourself

```bash
pip install ziglang pycdlib        # Zig cross-compiler + ISO writer
make installers                    # or: python3 mozbuild/scripts/build-installers.py

# one platform at a time
python3 mozbuild/scripts/build-installers.py --windows   # -> dist/SheepFox-Setup-<ver>.exe
python3 mozbuild/scripts/build-installers.py --macos     # -> dist/SheepFox-<ver>.dmg + .iso
```

---

## Quick start — Mode 2: build (SheepFox) Zen browser from source

```bash
# 0. build dependencies once
./mach bootstrap --application-choice browser      # inside the fetched tree

# 1. download + SHA-512 verify the pinned Gecko / Firefox 159.0 source tarball
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

* `--enable-jxl` is **not** a Gecko 159 configure switch; JPEG-XL ships compiled in and gated by
  `image.jxl.enabled` (already `true` upstream). Passing an unknown switch aborts configure.
* `gfx.webrender.all` is *not* forced in the patch series: Gecko picks WebRender per GPU/driver,
  and forcing it on unsupported hardware is the classic GPU-process crash. SheepFox sets it in
  `01-speedfox.js` where a user can revert it, and never disables `layers.gpu-process.enabled`.
* `x86-64-v3` requires Haswell (2013+) or Excavator/Zen (2015+).
* The patch series is generated against `FIREFOX_159_0_RELEASE` (the upstream Gecko release Zen
  Browser 1.24b builds on) and every patch passes `git apply --check`.

---

## Verification

```bash
make build-configs     # regenerate user.js + sheepfox.cfg from config/modules/*.js
make check             # fail if either generated file is stale
make test              # stdlib unittest verification suite (zero external dependencies)
make verify            # check + test
```

What the suite enforces:

1. `config/modules/*.js` ↔ `config/user.js` ↔ `config/autoconfig/sheepfox.cfg` stay in sync.
2. `sheepfox.cfg` line 1 is a comment, contains no `user_pref(`, and uses `lockPref()` **only**
   for `// @lock` lines (everything else is `defaultPref()`, so it stays editable in Settings).
3. Core speed/privacy invariants: dFPI `cookieBehavior = 5`, GPC, query stripping, HTTPS-Only,
   CRLite (`OCSP.enabled = 0`, `crlite_mode = 2`), Quad9 DoH (`trr.mode = 2`), WebRTC
   `default_address_only`, Contextual Identities (`privacy.userContext.enabled = true` for Zen
   Workspaces), 512 MB canvas cache, 20 MB Skia cache, 256 MB RAM cache, HTTP/3, 1800 connections,
   4-page bfcache.
4. Zero-breakage invariants: `resistFingerprinting = false` and **not locked**,
   `fingerprintingProtection = true`, `layers.gpu-process.enabled = true`, and Zen Browser native UI
   isolation (`:root:not(:has(#zen-main-app-wrapper))`).
5. Telemetry/PPA/studies/Pocket/sponsored/ML preferences (including `zen.urlbar.show-sponsored`)
   are `false` **and** locked.
6. `policies.json` provisions uBlock Origin (`uBlock0@raymondhill.net`, `normal_installed`) +
   Decentraleyes (`jid1-BoFifL9Vbdl2zQ@jetpack`) with curated filter lists, and never disables
   application updates.
7. Branding SVGs parse as XML, are vector-only (no `<script>`, no raster `<image>`), and carry
   `(SheepFox) Zen browser` branding.
8. Every patch matches its own diffstat, every hunk's line counts match its `@@` header, and
   `patches/series` lists exactly the `.patch` files present.
9. Windows `.bat`/`.ps1` are BOM-free, CRLF, pass PowerShell syntax checks, and contain
   `ExecutionPolicy Bypass`, `Unblock-File`, UAC re-launch, Zen Browser discovery, and
   `UTF8Encoding($false)` writes.
10. Mock Zen Browser (`~/.zen`, `$XDG_CONFIG_HOME/zen`, Flatpak `app.zen_browser.zen`) and Firefox
    profiles exercise install → backup → `--system` → `--strict` → `--low-memory` → `--uninstall`,
    and `--dry-run` is proven to write nothing.

---

## Troubleshooting

Run the built-in doctor first — it reports the exact Zen Browser / Firefox profile in use and
whether each piece landed:

```powershell
.\scripts\install-windows.bat -Doctor
```

```bash
python3 scripts/install.py --doctor
```

Prove `userChrome.css` is loaded (`-Probe` paints `#nav-bar` red and outlines `#urlbar` in green):

```powershell
.\scripts\install-windows.bat -Probe     # quit Zen Browser / Firefox fully, then relaunch
.\scripts\install-windows.bat -Unprobe   # remove the probe
```

```bash
python3 scripts/install.py --probe
python3 scripts/install.py --unprobe
```

---

## RAM & CPU footprint

| Pref | Upstream default | SheepFox | Effect |
| :--- | :--- | :--- | :--- |
| `dom.ipc.processCount` | 8 | **6** | each content process carries a fixed baseline RSS; fewer processes = less idle RAM, site isolation kept |
| `media.cache_size` | 512000 KiB (~500 MB) | **131072 KiB (128 MB)** | long video sessions stop pinning hundreds of MB of watched segments |
| `browser.sessionstore.interval` | 15 s | **60 s** | fewer background disk writes and wakeups; crash recovery unchanged |
| `browser.tabs.unloadOnLowMemory` | true | **true** | idle tabs are discarded instead of swapping/crashing |
| `browser.ml.enable` | true | **false** | no local LLM inference worker process at all |
| `browser.cache.disk.enable` | true | **false** | no disk cache; hot assets come from the 256 MB RAM cache |

For 4 GB machines, VMs, or 50-tab sessions, append `--low-memory` / `-LowMemory`
(`config/overrides/low-memory.override.js`).

## How `// @lock` works

Only data-transmitting preferences are locked:

```js
user_pref("toolkit.telemetry.enabled", false); // @lock   ->  lockPref(...)   in sheepfox.cfg
user_pref("gfx.webrender.all", true);                     ->  defaultPref(...) in sheepfox.cfg
```

---

## Contributing & security

* [`CONTRIBUTING.md`](CONTRIBUTING.md) — pref/patch workflow and the three invariants.
* [`SECURITY.md`](SECURITY.md) — threat model and how to report a regression.
* LICENSE: **[MPL-2.0](LICENSE)**.

## Acknowledgements

Inspired by **Zen Browser** (modern Gecko UX), **LibreFox/LibreWolf** (privacy vision),
**Betterfox** (zero-breakage tuning), **Brave Shields** (out-of-the-box blocking) and **Mercury**
(compiler optimisation). Independent open-source project; not affiliated with or endorsed by the
Zen Team or Mozilla. Firefox is a trademark of the Mozilla Foundation.
