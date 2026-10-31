#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Firefox — Linux & macOS Quick Installer Wrapper
# Usage:
#   ./scripts/install-unix.sh             # user.js + floating UI + SheepShields policy
#                                         #   (the policy preinstalls uBlock Origin and
#                                         #    Decentraleyes; it asks for sudo once)
#   sudo ./scripts/install-unix.sh --system    # also the AutoConfig files
#   ./scripts/install-unix.sh --no-extensions  # policy without the extension preinstall
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${REPO_ROOT}/scripts/install.py" "$@"
