#!/usr/bin/env bash
# ============================================================================
# (SheepFox) Firefox — Linux & macOS Quick Installer Wrapper
# Usage:
#   ./scripts/install-unix.sh              # Install user.js into default profile
#   sudo ./scripts/install-unix.sh --system # Also install SheepShields policies & AutoConfig
# ============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "${REPO_ROOT}/scripts/install.py" "$@"
