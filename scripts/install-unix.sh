#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Zen browser — Linux & macOS Quick Installer Wrapper
# Usage:
#   ./scripts/install-unix.sh             # user.js + chrome CSS + SheepShields policy
#                                         #   (targets Zen Browser + Firefox; asks for sudo
#                                         #    once to preinstall uBlock Origin + Decentraleyes)
#   sudo ./scripts/install-unix.sh --system    # also install AutoConfig (sheepfox.cfg)
#   ./scripts/install-unix.sh --browser zen    # target Zen Browser only
#   ./scripts/install-unix.sh --no-extensions  # policy without the extension preinstall
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${REPO_ROOT}/scripts/install.py" "$@"
