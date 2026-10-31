# (SheepFox) Firefox

<p align="center">
  <img src="branding/sheepfox/content/sheepfox-logo.svg" alt="(SheepFox) Firefox logo" width="132" height="132" />
</p>

<p align="center">
  <strong>Brave-class page-load speed · LibreFox-grade privacy · upstream Gecko stability · zero site breakage</strong>
</p>

<p align="center">
  <code>MPL-2.0</code> · <code>Firefox 159.0</code> pin · <code>132 prefs</code> · <code>4 verified upstream patches</code>
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
| **Mode 1 — Drop-in suite** | Modular prefs → `user.js`, a system AutoConfig (`sheepfox.cfg`), and **SheepShields** enterprise policy that preinstalls **uBlock Origin + Decentraleyes** | Any stock Firefox on Windows, Linux, macOS (standard, Flatpak, Snap) — **and Zen Browser**, see [below](#zen-browser--the-same-suite-aimed-at-zen) |
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
│       ├── build-browser.sh         # mach configure → build → package → inject config
│       └── build-installers.py      # dist/SheepFox-Setup-*.exe, SheepFox-*.dmg, *.iso
│
├── patches/                         # verified against FIREFOX_159_0_RELEASE
│   ├── series
│   └── 0001…0004-*.patch
├── installer/                       # MODE 1 — the double-click installers
│   ├── version.txt                  # the version stamped into the artifact names
│   ├── windows/launcher.c           # source of SheepFox-Setup-<ver>.exe
│   └── macos/                       # "Install SheepFox.command", "Install SheepFox for Zen.command"
│
├── extensions/floating-urlbar/      # the optional Floating URL Bar WebExtension
│   ├── manifest.json                # MV3, Gecko id floating-urlbar@sheepfox
│   ├── core.js                      # URL parsing, ranking, bookmark tiles (pure, node-tested)
│   ├── background.js                # shortcut, query + toolbar pipeline, surface selection
│   ├── ui.js / styles.js            # shared renderer: bookmark shelf + results (ARIA)
│   ├── content.js / window.js       # in-page overlay / popup-window surface
│   └── search.html, icons/bar.svg
│
├── scripts/                         # install.py, install{-unix.sh,-zen.sh,-windows.{bat,ps1},-zen.bat}
├── tests/test_repo.py               # 122 tests, stdlib only (node/jsdom for the extension)
├── tests/extension/core.test.js     # 26 node tests: URL parsing, ranking, bookmark tiles
├── tests/extension/background.test.js  # 7 node tests: toolbar tree, message routing
├── tests/extension/ui.test.js       # 19 jsdom tests: shelf, folders, rows, keyboard, cleanup
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

./scripts/install-unix.sh                # user.js + floating CSS + SheepShields policy
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

### UI: floating new-tab search (Zen / Arc style)

> This is the *real* address bar floating — profile CSS, on by default, `--no-ui` / `-NoUI` turns it
> off. If you cannot use profile CSS at all, the optional
> [Floating URL Bar extension](#floating-url-bar-optional-extension) gives you a floating bar of its
> own on `Ctrl+Shift+Space`.

Open a new tab (`Ctrl+T`), or just focus the address bar on any page (`Ctrl+L` / clicking it), and
the bar detaches from the toolbar and floats **in the middle of the page** as a compact rounded pill
(52 px, max 620 px wide, centred at `42vh`). On a new tab the wordmark is removed and the shortcut
grid sits below it — Zen's empty canvas with Arc's command bar. Blur it and it docks straight back.

Firefox focuses the address bar on a new tab and auto-opens its suggestions dropdown; that dropdown
is collapsed while the field is empty, so a blank tab really is a pill and not a form. As soon as
you type, the list opens **underneath** the pill (Arc/Zen behaviour) and the pill grows downwards;
load the page and it docks back into the stock toolbar with normal autocomplete.

The implementation follows Zen Browser's own `floating-urlbar` theme: `position: fixed` with
`!important` on the properties Firefox otherwise sets itself (`top`, `left`, `width`). Centring is
done with `left: 0` + `right: 0` + `margin-inline: auto`, which centres inside whatever box the fixed
bar lands in — `left: 50%` + `translate: -50%` assumed the containing block was the window and
drifted half a pill width to the left whenever an ancestor claimed it.

**No `@namespace`.** Almost every floating-urlbar snippet on the internet opens with
`@namespace url("...there.is.only.xul")`. That sets the *default* namespace, which applies to type
selectors **and the universal selector** — and `#urlbar` is `*#urlbar`. Firefox built the bar as
`<hbox id="urlbar">` (XUL) until ~135, but since 140 it is a plain HTML element
(`<html:div id="urlbar">`, `<html:moz-urlbar id="urlbar">` since 152). With that boilerplate in
place, every `#urlbar` rule silently matches nothing, with no console error — while `#nav-bar`
snips keep working because the toolbar is still XUL. That is why SheepFox's earlier builds looked
"installed but dead". Every selector here is id/attribute/class based, so no namespace is declared.

The open state is detected four ways so one file covers every Firefox: `[pageproxystate="invalid"]`
(blank tab, all versions), `[breakout][breakout-extend]` (the megabar breakout, ~72–151),
`[expanded]` (what `SmartbarInput.mjs` sets on 152+) and `[open]` (results view open over a page).

Geometry is deliberately in **viewport units** (`42vh`, `50vw`), and every ancestor
(`#main-window` → `#urlbar-container`) has its `transform`/`contain`/`will-change` neutralised: any
of those would make the toolbar — not the window — the containing block for a `position: fixed` bar,
which put the pill at a negative offset (a sliver at the very top of the window) instead of the
middle of the page.

Every visual rule is **scoped to a floating state**. Earlier builds styled `#urlbar-input` and
`.urlbar-input-container` unconditionally, which inflated and re-centred the *toolbar* bar on every
normal page — a full-width, 56 px, centre-aligned address bar on YouTube and everywhere else. Only
the pill states get the treatment now; normal browsing is untouched.

A small **"SheepFox UI" badge** appears in the corner **while the pill is out** — it is drawn by
this stylesheet, so if you can read it, `userChrome.css` is parsed and applied and anything still
wrong is a selector rather than an install. It is gated to the floating state on purpose: a label
pinned to the corner of every page forever is exactly the clutter this theme exists to remove.
Delete the `PROOF-OF-LOAD BADGE` block if you do not want it at all.

Typing happens on the **left**, not in the middle. The placeholder is centred; the value is not.
Centring the value made every keystroke shift the text, and a long URL overflowed *both* ends while
the caret walked out of the pill — the one place in this theme where "prettier" was also
"unusable".

The suggestions panel is part of the same card: stock Firefox paints its own background, border and
shadow around the results, which showed up as a second frame inside the pill (both are neutralised
here). Its height is `min(52vh, 100vh − 42vh − 90px)`, so the list scrolls inside the card instead
of painting past the bottom of the window — the old flat `62vh` cap started at `42vh` and therefore
overflowed by 4vh. On windows shorter than 700 px the pill itself moves up to `34vh` to leave room.

Nothing sets `will-change`. The file used to end with `#urlbar { will-change: transform }`, which
promoted the address bar to its own compositing layer on **every** page for an animation that does
not exist — the pill only animates `box-shadow`. The docked bar now composites exactly like stock
Firefox.

The installer now writes to **every Firefox profile on the machine** (standard, Microsoft Store and
portable roots, read from `installs.ini` first) — landing in the wrong profile is the classic reason
a `userChrome` theme does nothing. Use `--profile` / `-ProfilePath` to target exactly one.

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

Why it cannot break browsing: the pill has exactly **one** trigger — the
`#urlbar[pageproxystate="invalid"]` attribute Firefox sets whenever the bar is not showing a loaded
page. That is a new tab, or an address you are editing; a loaded page never matches, so navigation,
bookmarks, downloads and autocomplete behave exactly like stock Firefox. (Earlier builds also
required `#urlbar-input:placeholder-shown`; on a freshly opened tab the placeholder is not always
painted yet, so that extra condition silently stopped the whole theme from applying. It is now used
only to decide whether to collapse the empty suggestion list.) The sheet honours
`prefers-color-scheme` and `prefers-reduced-motion`, and Firefox only reads it because
`toolkit.legacyUserProfileCustomizations.stylesheets = true` is already set in
`config/modules/03-cleanfox.js`.

Tuning or removing it:

| Want | Do |
| :--- | :--- |
| Move the pill / resize it | edit `--sheepfox-pill-top` (default `42vh`; use `50vh` for dead-centre), `--sheepfox-pill-width`, `--sheepfox-pill-height` in your profile's `chrome/userChrome.css` |
| Dock it the moment you type instead of expanding | uncomment the "dock while typing" block at the bottom of `config/chrome/userChrome.css`, then reinstall |
| Shrink it back to a normal bar | delete `<profile>/chrome/userChrome.css` |
| Keep the pill, restore the New Tab logo | delete `<profile>/chrome/userContent.css` |
| Uninstall everything | `python3 scripts/install.py --uninstall` (removes both files) |

Edits survive reinstalls until you re-run the installer, which rewrites the files from
`config/chrome/` (backing up the previous copy first). To make a UI change permanent, edit
`config/chrome/*.css` in the repo and reinstall — the same rule as the prefs.

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
| `SheepFox-Zen-Setup-<version>.exe` | Windows 10/11, x86-64 | The same launcher with `-Zen` baked in: configures Zen Browser instead of Firefox |
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
`-Strict`, `-LowMemory`, `-NoUI`, `-Doctor`, `-Probe`, `-Unprobe`, `-Report`,
`-Uninstall`, `-DryRun`). A plain double-click installs the policy too, so UAC
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
`chrome/*.css`, `policies.json` and AutoConfig files as Mode 1, back up whatever
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

## Zen Browser — the same suite, aimed at Zen

Zen is Firefox underneath: same engine, same `prefs.js`, same `user.js` parser,
same enterprise policy engine. So it takes **exactly the same configuration** —
only three things differ, and the installer knows all three.

```bash
./scripts/install-zen.sh              # Linux / macOS: prefs + policy, every Zen profile
python3 scripts/install.py --browser zen
make install-zen

.\scripts\install-zen.bat             # Windows (bypasses ExecutionPolicy for you)
.\scripts\install-windows.bat -Zen -UI
SheepFox-Zen-Setup-<version>.exe      # or double-click this
```

| | Firefox | Zen Browser |
| :--- | :--- | :--- |
| Profile folder | `%APPDATA%\Mozilla\Firefox`, `~/.mozilla/firefox`, `~/Library/Application Support/Firefox` | `%APPDATA%\zen`, `~/.zen` **or** `$XDG_CONFIG_HOME/zen` (Zen ≥ 1.18.6b), and the Flatpak sandbox |
| Installation folder | `C:\Program Files\Mozilla Firefox`, `/usr/lib/firefox`, `Firefox.app` | `%LOCALAPPDATA%\Programs\zen` (the per-user installer), `/opt/zen-browser-bin`, `/usr/lib/zen-browser`, `Zen.app` — **not** `/opt/zen-browser`, which no package owns and Zen never reads |
| The floating pill | **on by default** | **opt-in** (`--ui` / `-UI`) — Zen already ships its own floating omnibox |
| `policies.json` | written, packaging policies preserved | written, packaging policies preserved; on Linux `--policy-dir /etc/zen/policies` survives package upgrades |

**Everything else is identical**: the same 132 prefs, the same SheepShields policy,
the same uBlock Origin + Decentraleyes preinstall, the same `--strict`,
`--low-memory`, `--doctor`, `--probe`, `--report` and `--uninstall` behaviour.

Two Zen-specific details that would otherwise bite you:

* **Policies are merged, not replaced.** A packaged Zen ships its own
  `distribution/policies.json` (`DisableAppUpdate`, `DefaultSerialGuardSetting`).
  Taking that file over would let the browser update itself behind the package
  manager, so SheepFox keeps every entry it does not set, and `--uninstall`
  removes only its own — the packager's entries stay.
* **`/etc/zen/policies` wins on Linux.** Zen reads
  `/etc/zen/policies/policies.json` *instead of* the file in its installation
  folder when it exists, and a package upgrade rewrites the latter. If you want
  the policy to survive `pacman -Syu`, use
  `sudo ./scripts/install-zen.sh --system --policy-dir /etc/zen/policies`.

`--browser auto` (the default) installs into **every** browser it finds — Firefox
and Zen both, if both are there. Pin one with `--browser firefox` / `--browser zen`.

> Verified end to end on disk (profile discovery incl. the XDG and Flatpak roots,
> policy merge, `--ui`, doctor, uninstall) by the test suite. The *visual* result
> of the pill in Zen is not asserted here: Zen styles its own `#urlbar`, which is
> why the pill is opt-in rather than a default.

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

The floating address bar described above is **profile CSS** — it is the real `#urlbar`, detached
from the toolbar, and it is what makes the bar behave like Zen/Arc's. No WebExtension can do that:
add-ons get no access to the browser chrome, so `userChrome.css` is the only mechanism that can
float *Mozilla's own* bar.

`extensions/floating-urlbar/` is the add-on for the case where profile CSS is not available or not
wanted. Press **`Ctrl+Shift+Space`** (`Command+Shift+Space`) and a pill appears.

Before you type it is a **bookmark shelf**: your toolbar's bookmarks as tiles, folders opening in
place with a `← Back` row, titles wrapping to two lines, chip colours hashed from the host so they
never change between reloads. Type, and it becomes one list — **open tabs, bookmarks, history and
the web**, a typed URL first. Clicking outside it hides it, and `Esc` steps out of a folder before
it closes.

It ships its own surface instead of touching the chrome: an in-page overlay inside a closed shadow
root on normal pages, and a small popup window on `about:` pages, `addons.mozilla.org` or the PDF
viewer, where injection is impossible. The shortcut never silently does nothing. Tiles are letters
rather than favicons on purpose: Firefox exposes no favicon API for bookmarks, and asking a favicon
service would leak your bookmark list to it.

| | |
| :--- | :--- |
| **Empty state** | bookmark-toolbar shelf: tiles, folders in place, `← Back`, click-outside to hide |
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
node tests/extension/core.test.js      # 26 tests: URL parsing, ranking, row cap, bookmark tiles
node tests/extension/background.test.js # 7 tests: toolbar tree, query pipeline, routing
node tests/extension/ui.test.js        # 19 tests: shelf, folders, rendering, keyboard, ARIA
```

Full details, the permission rationale and the design notes are in
[`extensions/floating-urlbar/README.md`](extensions/floating-urlbar/README.md).

---

## Verification

```bash
make build-configs     # regenerate user.js + sheepfox.cfg from config/modules/*.js
make check             # fail if either generated file is stale
make test              # 122 tests (stdlib unittest + node/jsdom for the extension)
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

## Troubleshooting: the UI (or any change) did not apply

Run the built-in doctor first — it reports the exact profile in use and whether each piece landed:

```powershell
.\scripts\install-windows.bat -Doctor
```

```bash
python3 scripts/install.py --doctor
```

It checks `user.js`, `chrome/userChrome.css`, `chrome/userContent.css`, whether those copies are
**byte-identical to this repo** (a stale file from an older version is a silent no-op), whether
`toolkit.legacyUserProfileCustomizations.stylesheets` is *saved* as `true` in `prefs.js`, the system
files (`sheepfox.cfg`, `local-settings.js`, `policies.json`), and whether your SheepFox files ended
up in a **different profile than the one Firefox launches** — the single most common cause.

Then prove the stylesheet is actually being read. `-Probe` writes
`chrome/sheepfox-probe.css`, which `userChrome.css` already imports; it paints the toolbar **red**
and gives the pill a green outline:

```powershell
.\scripts\install-windows.bat -Probe     # then quit Firefox fully and start it
.\scripts\install-windows.bat -Unprobe   # remove the probe
```

```bash
python3 scripts/install.py --probe
python3 scripts/install.py --unprobe
```

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
| Doctor passes, CSS still ignored | pref saved as `false` by another hardening tool | `about:config` → `toolkit.legacyUserProfileCustomizations.stylesheets` → `true`, restart |
| New Tab logo changed but no pill | older Firefox without `:has()` support (< 121) | upgrade, or use the `.default`-profile rules only |
| Windows Store Firefox | profile lives under `%LOCALAPPDATA%\Packages\Mozilla.Firefox_*` | handled automatically now; `-Doctor` prints the profile it uses (override with `-ProfilePath`) |
| Doctor flags "stale" | profile has an older copy of the CSS | re-run the installer, then restart Firefox |
| Need proof CSS loads at all | `userChrome.css` may not be read | focus the bar (`Ctrl+L`) or open a new tab and look for the **"SheepFox UI"** badge in the corner, or run `.\scripts\install-windows.bat -Probe` → the whole top strip of the window turns red ⇒ CSS loads. Remove with `-Unprobe` |
| Installed into Zen, nothing changed | Zen's pill is opt-in (`--ui`); the prefs and policy apply regardless — check `about:policies` and `about:config` |
| Zen policy "installed" but `about:policies` is empty | on Linux, `/etc/zen/policies/policies.json` replaces the one in the install folder — install with `--policy-dir /etc/zen/policies` |
| Copied a floating-urlbar snippet, nothing happens | a default `@namespace ...xul` kills every `#urlbar` rule (the bar is HTML since Firefox 140) | delete the `@namespace` line — SheepFox's own sheet has none |

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

* **The floating pill is not installed into Zen by default.** Zen already ships its own floating
  omnibox and styles `#urlbar` itself; stacking SheepFox's pill on top is a choice, not a default.
  `--ui` / `-UI` installs it. Everything else — prefs, policy, extensions — is identical.

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
