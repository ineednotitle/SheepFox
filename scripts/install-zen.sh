#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Zen Browser — Linux & macOS Quick Installer Wrapper
#
# The same installer, aimed at Zen Browser: it reads Zen's own profile folders
# (~/.zen, $XDG_CONFIG_HOME/zen, the Flatpak sandbox, %APPDATA%\zen) and writes
# the SheepShields policy into Zen's installation folder.
#
# Two differences from a Firefox run, both deliberate:
#   * the floating pill is NOT installed by default - Zen already has its own
#     floating omnibox and its own chrome. Add --ui to get ours as well.
#   * a packaged Zen ships its own policies.json (DisableAppUpdate, ...); those
#     entries are preserved instead of being overwritten.
#
# Usage:
#   ./scripts/install-zen.sh                 # user.js + SheepShields policy
#   ./scripts/install-zen.sh --ui            # ... and the floating pill too
#   sudo ./scripts/install-zen.sh --system   # also the AutoConfig files
#   ./scripts/install-zen.sh --doctor        # diagnose an install
#   ./scripts/install-zen.sh --uninstall     # remove everything
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${REPO_ROOT}/scripts/install.py" --browser zen "$@"
