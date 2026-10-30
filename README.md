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
| **Mode 1 — Drop-in suite** | Modular prefs → `user.js`, a system AutoConfig (`sheepfox.cfg`), and **SheepShields** enterprise policy that auto-installs uBlock Origin with curated filter lists | Any stock Firefox on Windows, Linux, macOS (standard, Flatpak, Snap) |
| **Mode 2 — Fork scaffold** | Branding, mozconfigs, a verified patch series and CI to compile a standalone **SheepFox** binary from pinned Mozilla source with cross-language LTO, `x86-64-v3`, LLD and optional PGO | Build host: Linux / Windows (MozillaBuild) / macOS |

Mode 1 takes about ten seconds. Mode 2 takes about an hour of CPU and 40 GB of disk.

---

## Why it feels like Brave without inheriting Brave's problems

| Pillar | Stock Firefox | Strict hardening | **(SheepFox) Firefox** |
| :--- | :--- | :--- | :--- |
| **Ad & tracker blocking** | none — every ad byte is downloaded | manual | **SheepShields `policies.json`** auto-installs uBlock Origin + `easylist`, `easyprivacy`, `ublock-badware`, `ublock-privacy`, `urlhaus-1` |
| **GPU / rendering** | conservative defaults | often disables WebGL and Canvas accel | **WebRender + shader precache + 512 MB accelerated Canvas + 20 MB Skia font cache** |
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
│   ├── chrome/                      # UI theme: floating Zen/Arc-style search pill
│   │   ├── userChrome.css           #   centred pill on blank tabs (toolbar untouched)
│   │   └── userContent.css          #   clears the New Tab wordmark, lifts the shortcuts
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
│       └── build-browser.sh         # mach configure → build → package → inject config
│
├── patches/                         # verified against FIREFOX_159_0_RELEASE
│   ├── series
│   └── 0001…0004-*.patch
├── scripts/                         # install.py, install-unix.sh, install-windows.{bat,ps1}
├── tests/test_repo.py               # 41 tests, stdlib only
└── .github/workflows/               # validate-configs.yml, build-sheepfox.yml
```

---

## Quick start — Mode 1: drop-in on stock Firefox

Backups of any existing `user.js` are written first (`user.js.sheepfox-backup-<timestamp>`).

### Linux

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run      # preview every path first

./scripts/install-unix.sh                # profile only: speed + privacy user.js
sudo ./scripts/install-unix.sh --system  # + AutoConfig + SheepShields (uBlock Origin)
```

Flatpak (`~/.var/app/org.mozilla.firefox/...`) and Snap (`~/snap/firefox/common/...`) profiles
are detected automatically; system dirs for both are probed for `--system`.

### macOS

```bash
git clone https://github.com/ineednotitle/SheepFox.git && cd SheepFox
./scripts/install-unix.sh --dry-run
./scripts/install-unix.sh                            # ~/Library/Application Support/Firefox
sudo ./scripts/install-unix.sh --system              # + /Applications/Firefox.app/Contents/Resources
```

### Windows

Double-click or run the `.bat` launcher — it bypasses `ExecutionPolicy` for you, so you will
never see *"…install-windows.ps1 is not digitally signed"*:

```powershell
.\scripts\install-windows.bat                       # profile only: speed + privacy
.\scripts\install-windows.bat -System -Strict        # + AutoConfig/uBlock (UAC) and strict RFP
.\scripts\install-windows.bat -Uninstall -System     # remove everything again
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
python scripts\install.py --system --uninstall
```

### UI: floating new-tab search (Zen / Arc style)

Open a new tab (`Ctrl+T`) and the address + search bar detaches from the toolbar and floats **in the
middle of the page** as a compact rounded pill (56 px, `top: 42%`), with the New Tab wordmark
removed and the shortcut grid sitting below it — Zen's empty canvas with Arc's command bar.

Firefox focuses the address bar on a new tab and auto-opens its suggestions dropdown; that dropdown
is collapsed while the field is empty, so a blank tab really is a pill and not a form. Start
typing, or load a page, and the bar docks straight back into the stock toolbar with the normal
autocomplete. Want the suggestions to stay under the floating pill while you type (Arc mode)?
Uncomment the marked block at the end of `config/chrome/userChrome.css`.

It ships as **profile CSS**, not a patch, so it is instantly reversible:

```bash
./scripts/install-unix.sh            # installs config/chrome/*.css into <profile>/chrome/
./scripts/install-unix.sh --no-ui    # everything except the UI theme
./scripts/install-unix.sh --low-memory   # minimal-RAM override (see below)
```

```powershell
.\scripts\install-windows.bat
.\scripts\install-windows.bat -NoUI
.\scripts\install-windows.bat -LowMemory
```

Why it cannot break browsing: the pill requires **both** `#urlbar[pageproxystate="invalid"]`
(not showing a loaded page's address) **and** an empty field (`#urlbar-input:placeholder-shown`).
That deliberately does *not* depend on the address bar being unfocused — Firefox autofocuses it on
a new tab, which would otherwise hide the pill — while typing in the address bar of a real page,
opening bookmarks, or navigating never matches. It also honours
`prefers-color-scheme` and `prefers-reduced-motion`, and Firefox only reads these files because
`toolkit.legacyUserProfileCustomizations.stylesheets = true` is already set in
`config/modules/03-cleanfox.js`.

Tuning or removing it:

| Want | Do |
| :--- | :--- |
| Move the pill / resize it | edit `--sheepfox-pill-top` (default `42%`; use `50%` for dead-centre), `--sheepfox-pill-width`, `--sheepfox-pill-height` in your profile's `chrome/userChrome.css` |
| Keep it floating while typing (Arc mode) | uncomment the "Arc mode" block at the bottom of `config/chrome/userChrome.css`, then reinstall |
| Shrink it back to a normal bar | delete `<profile>/chrome/userChrome.css` |
| Keep the pill, restore the New Tab logo | delete `<profile>/chrome/userContent.css` |
| Uninstall everything | `python3 scripts/install.py --uninstall` (removes both files) |

Edits survive reinstalls until you re-run the installer, which rewrites the files from
`config/chrome/` (backing up the previous copy first). To make a UI change permanent, edit
`config/chrome/*.css` in the repo and reinstall — the same rule as the prefs.

### Reverting

```bash
python3 scripts/install.py --system --uninstall     # removes what SheepFox installed
```

On Windows: `.\scripts\install-windows.bat -Uninstall -System`

Timestamped backups are always left in place; restore the newest
`user.js.sheepfox-backup-*` to get your old profile config back.

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

## Verification

```bash
make build-configs     # regenerate user.js + sheepfox.cfg from config/modules/*.js
make check             # fail if either generated file is stale
make test              # 41 tests (stdlib unittest, no dependencies)
make verify            # check + test
```

What the suite enforces:

1. `config/modules/*.js` ↔ `config/user.js` ↔ `config/autoconfig/sheepfox.cfg` stay in sync.
2. `sheepfox.cfg` line 1 is a comment, contains no `user_pref(`, and uses `lockPref()` **only**
   for `// @lock` lines (everything else is `defaultPref()`, so it stays editable in Settings).
3. Core speed/privacy invariants: dFPI `cookieBehavior = 5`, GPC, query stripping, HTTPS-Only,
   CRLite (`OCSP.enabled = 0`, `crlite_mode = 2`), Quad9 DoH (`trr.mode = 2`), WebRTC
   `default_address_only`, 512 MB canvas cache, 20 MB Skia cache, 256 MB RAM cache, HTTP/3,
   1800 connections, 4-page bfcache.
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

## Troubleshooting: the UI (or any change) did not apply

Run the built-in doctor first — it reports the exact profile in use and whether each piece landed:

```powershell
.\scripts\install-windows.bat -Doctor
```

```bash
python3 scripts/install.py --doctor
```

It checks `user.js`, `chrome/userChrome.css`, `chrome/userContent.css`, whether
`toolkit.legacyUserProfileCustomizations.stylesheets` is *saved* as `true` in `prefs.js`, and the
system files (`sheepfox.cfg`, `local-settings.js`, `policies.json`).

| Symptom | Cause | Fix |
| :--- | :--- | :--- |
| Doctor says the files are missing | installers write to the **active** profile only | `.\scripts\install-windows.bat -ProfilePath "%APPDATA%\Mozilla\Firefox\Profiles\<yours>"` |
| Doctor passes, nothing changes | Firefox still running (config is read at startup) | quit fully — Task Manager must show no `firefox.exe` — then relaunch |
| Doctor passes, CSS still ignored | pref saved as `false` by another hardening tool | `about:config` → `toolkit.legacyUserProfileCustomizations.stylesheets` → `true`, restart |
| New Tab logo changed but no pill | older Firefox without `:has()` support (< 121) | upgrade, or use the `.default`-profile rules only |
| Windows Store Firefox | profile lives under `%LOCALAPPDATA%\Packages\Mozilla.Firefox_*` | pass `-ProfilePath` explicitly |
| Everything looks right | need proof CSS loads at all | append `#nav-bar { background: #cc0000 !important; }` to `<profile>\chrome\userChrome.css`; toolbar turns red ⇒ CSS loads, remove the line and report the selector |

Prove *where* your profile is:

```powershell
Get-ChildItem "$env:APPDATA\Mozilla\Firefox\Profiles" -Directory |
  ForEach-Object { "$($_.Name)  chrome=$(Test-Path (Join-Path $_.FullName 'chrome\userChrome.css'))  user.js=$(Test-Path (Join-Path $_.FullName 'user.js'))" }
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
