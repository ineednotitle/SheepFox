# (SheepFox) Firefox

<p align="center">
  <img src="branding/sheepfox/content/sheepfox-logo.svg" alt="(SheepFox) Firefox Logo" width="136" height="136" />
</p>

<p align="center">
  <strong>Brave-Class Speed · LibreFox-Grade Privacy · Upstream Gecko Stability · Zero Site Breakage</strong>
</p>

---

## Overview

**(SheepFox) Firefox** (`SheepFox`) is a hybrid Firefox engineering project built to solve a frustrating trade-off in modern browsers:

- **Stock Firefox** ships with telemetry pings, sponsored tiles, Pocket, Privacy-Preserving Attribution (PPA), background ML/AI processes, conservative network limits, and no built-in ad/tracker blocker—making page loads noticeably slower than **Brave**.
- **Ultra-strict hardened forks** often enable aggressive `resistFingerprinting` (RFP) or disable WebGL/caches/JIT—locking monitors to 60Hz, forcing light mode, spoofing timezones, breaking Canvas apps, and *hurting* real-world performance.

**SheepFox bridges both worlds.** It delivers **Brave-level page-load responsiveness** and **LibreFox-inspired privacy hardening** without sacrificing Gecko stability, hardware acceleration, 120Hz+ smoothness, or everyday website compatibility.

Because SheepFox uses a **Hybrid Architecture**, you can use it in two ways:
1. **Drop-In Config & Policy Suite (10-Second Setup on Stock Firefox):** Apply `user.js`, AutoConfig (`sheepfox.cfg`), and **SheepShields** (`policies.json` + automatic uBlock Origin provisioning) directly to your existing Firefox installation on Windows, Linux, or macOS.
2. **Custom Browser Fork Build Scaffold (Compile from Source):** Build a standalone branded **SheepFox** binary from upstream Mozilla source with Cross-Language LTO (`--enable-lto=cross`), `x86-64-v3` (AVX2/FMA) / Apple Silicon / ARM64 optimizations, PGO, and compile-time telemetry stripping.

---

## Why SheepFox Feels Like Brave (Without Losing Stability)

| Pillar | Stock Firefox | Strict Hardened Configs | **(SheepFox) Firefox** |
| :--- | :--- | :--- | :--- |
| **Out-of-Box Ad & Tracker Blocking** | None (loads 100% of ad/tracker bloat) | Manual setup required | **SheepShields (`policies.json`)** auto-installs uBlock Origin + curated privacy/spyware lists |
| **GPU & Rendering Pipeline** | Conservative defaults | Often disables WebGL / Canvas acceleration | **Full WebRender + Shader Pre-cache + 512 MB Accelerated Canvas + 20 MB Skia Font Cache** |
| **Caching Strategy** | Disk I/O heavy | Often disables all caches (slow reloads) | **RAM-First 256 MB Cache + 4-Page 0ms Back/Forward Cache (`bfcache`)** |
| **Network Transport** | Throttled request pacing, 6 conn/host | Speculative & HTTP/3 sometimes restricted | **HTTP/3 (QUIC) + Unpaced Burst Requests + 1800 Max Conn / 10 Persistent per Host** |
| **Certificate Revocation** | Live OCSP queries (slow + leaks domains) | Hard-fail OCSP (breaks sites when OCSP lags) | **Mozilla CRLite Local Binary Filters** (0ms latency, zero domain leakage) |
| **Anti-Fingerprinting** | Minimal | Strict RFP (locks 60Hz, breaks Canvas/dark mode) | **Granular Fingerprinting Protection (`FPP`) + Total Cookie Protection (dFPI) + GPC** |
| **Telemetry, PPA & AI Bloat** | Active by default | Stripped | **100% Stripped & Locked (`@lock`)** — Zero Telemetry, Studies, Pocket, PPA, or background LLM workers |
| **High-Refresh Displays** | Standard | Capped at 60Hz under RFP | **Full 120Hz / 144Hz / 240Hz MSD Spring Physics (`04-smoothfox.js`)** |

---

## Repository Architecture

```text
SheepFox/
├── config/                              # PART 1: Drop-In Config, AutoConfig & SheepShields Suite
│   ├── modules/                         # Modular source preferences (edit here!)
│   │   ├── 01-speedfox.js               # WebRender, Skia, RAM cache, HTTP/3 & connection concurrency
│   │   ├── 02-shieldfox.js              # LibreFox privacy: dFPI, FPP, CRLite, DoH, GPC, Telemetry/PPA lock
│   │   ├── 03-cleanfox.js               # Removes Pocket, Sponsored Ads, QuickSuggest & background ML/AI
│   │   └── 04-smoothfox.js              # 120Hz+ Mass-Spring-Damper scroll & APZ input physics
│   ├── user.js                          # Compiled unified profile drop-in file
│   ├── autoconfig/                      # LibreFox-style system-wide AutoConfig
│   │   ├── sheepfox.cfg                 # Uses lockPref() for telemetry/ads & defaultPref() for user freedom
│   │   └── defaults/pref/local-settings.js
│   ├── distribution/
│   │   └── policies.json                # SheepShields: Enterprise policy auto-installing uBlock Origin
│   └── overrides/
│       ├── user-overrides.example.js    # Template for personal preferences
│       └── strict-paranoia.override.js  # Opt-in strict RFP override (--strict)
│
├── branding/sheepfox/                   # PART 2: Custom (SheepFox) Firefox Branding Assets
│   ├── configure.sh                     # App metadata & compile-time telemetry guards
│   ├── locales/en-US/                   # Fluent (brand.ftl), DTD, and properties strings
│   └── content/                         # Vector shield/fox/sheep logo & wordmark SVGs
│
├── build/                               # PART 3: Custom Browser Fork Build System
│   ├── firefox-version.json             # Pinned upstream Mozilla Firefox release manifest
│   ├── mozconfig.common                 # Shared hardening, Rust SIMD, JPEG-XL & telemetry removal
│   ├── mozconfig.linux-x86_64           # AVX2 (x86-64-v3) + LLD + Cross-LTO + optional PGO
│   ├── mozconfig.linux-aarch64          # ARM64 NEON + LLD + LTO
│   ├── mozconfig.windows-x86_64         # Windows clang-cl + Cross-LTO + AVX2
│   ├── mozconfig.macos-universal        # macOS Apple Silicon / Universal2 Cross-LTO
│   └── scripts/                         # Config compiler, source fetcher, patcher & mach builder
│
├── patches/                             # Upstream Gecko Unified Diff Patch Series
├── scripts/                             # Cross-platform installers (Python, Bash, PowerShell)
├── tests/                               # Automated verification suite (prefs, policies, SVGs, patches)
└── .github/workflows/                   # CI config validation & Linux release build pipelines
```

---

## Quick Start: Mode 1 — Drop-In Install on Stock Firefox (Recommended)

Apply SheepFox directly to your existing Firefox installation in seconds. Automatic backups of any existing `user.js` are created before changes are written.

### Linux & macOS

```bash
# 1. Apply Speed + Privacy user.js to your active Firefox profile (Standard, Flatpak, or Snap):
./scripts/install-unix.sh

# 2. (Recommended) Also install SheepShields (auto-installs uBlock Origin) + System AutoConfig:
sudo ./scripts/install-unix.sh --system
```

### Windows (PowerShell)

```powershell
# 1. Profile-level Speed + Privacy user.js:
.\scripts\install-windows.ps1

# 2. Full installation including SheepShields (uBlock Origin policy) & AutoConfig (Run as Administrator):
.\scripts\install-windows.ps1 -System
```

### Optional Modes & Uninstall

```bash
# Preview what will be installed without modifying files:
python3 scripts/install.py --dry-run

# Enable optional "Strict Paranoia" mode (enables strict ResistFingerprinting):
python3 scripts/install.py --strict

# Cleanly uninstall SheepFox files:
python3 scripts/install.py --system --uninstall
```

---

## Quick Start: Mode 2 — Build Custom Branded SheepFox from Source

For maintainers and power users building standalone **(SheepFox) Firefox** binaries:

```bash
# 1. Download & verify pinned upstream Firefox source archive (SHA-512 checked):
make fetch-source

# 2. Compile configs, inject SheepFox branding, and apply Gecko patches:
make patch-source

# 3. Build optimized SheepFox release package (set SHEEPFOX_PGO=1 for 2-stage PGO):
SHEEPFOX_PGO=1 make build-browser
```

---

## Development & Verification

Never edit `config/user.js` or `config/autoconfig/sheepfox.cfg` by hand—edit the modular files inside `config/modules/` and recompile:

```bash
# Compile modular configs into user.js and sheepfox.cfg:
make build-configs

# Verify sync & run all 7 automated validation test suites:
make check
make test
```

### How `@lock` Annotations Work (LibreFox Evolution)

Classic LibreFox locked nearly all preferences, preventing users from changing settings in `about:preferences`. SheepFox uses smart selective locking in `config/modules/*.js`:
- Lines tagged with `// @lock` compile to `lockPref(...)` in `sheepfox.cfg` (**strictly reserved** for telemetry, Normandy studies, sponsored ads, Pocket, and PPA).
- All other lines compile to `defaultPref(...)` in `sheepfox.cfg`, giving you hardened, ultra-fast defaults while allowing effortless customization in Firefox's Settings UI.

---

## Push This Repository to GitHub / Codeberg / GitLab

```bash
git remote add origin https://github.com/<your-username>/SheepFox.git
git push -u origin main
```

---

## Acknowledgements & Lineage

- Inspired by the privacy vision of **LibreFox** / **LibreWolf**, the zero-breakage engineering of **Betterfox**, the out-of-the-box shield experience of **Brave**, and the compiler optimizations of **Mercury**.
- Licensed under the **[Mozilla Public License 2.0 (MPL-2.0)](LICENSE)**.
