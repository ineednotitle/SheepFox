#!/bin/bash
# ============================================================================
# (SheepFox) Firefox — macOS installer
#
# Double-click this file. It runs the same SheepFox installer a git checkout
# would run, against the Firefox profile(s) in ~/Library/Application Support.
#
# If macOS refuses to run it ("cannot be opened because it is from an
# unidentified developer", or the file has no execute bit on a mounted image):
#   Control-click → Open,  or run:  sh "Install SheepFox.command"
#
# macOS will ask for your password once: the SheepShields policy file that
# preinstalls uBlock Origin + Decentraleyes lives inside Firefox.app.
#
# Switches are forwarded, so you can also do:
#   sh "Install SheepFox.command" --no-extensions
#   sh "Install SheepFox.command" --system --low-memory
#   sh "Install SheepFox.command" --doctor
#   sh "Install SheepFox.command" --uninstall
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="${HERE}/SheepFox"

# Never block when the script is run from a shell with no terminal attached.
pause() {
  if [ -t 0 ]; then
    read -r -p "Press Return to close..." _ || true
  fi
}

echo ""
echo "  (SheepFox) Firefox"
echo "  ------------------"
echo ""

if [ ! -d "${PAYLOAD}" ]; then
  echo "[error] The SheepFox folder is missing next to this installer."
  echo "        Mount the disk image again and copy both items to your Desktop."
  echo ""
  pause
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "[error] python3 is required."
  echo "        Install the Xcode command line tools:  xcode-select --install"
  echo ""
  pause
  exit 1
fi

FIREFOX_RUNNING="$(pgrep -x firefox || true)"
if [ -n "${FIREFOX_RUNNING}" ]; then
  echo "  Firefox is running. Quit it completely before the change takes effect"
  echo "  (config and userChrome.css are only read at startup)."
  echo ""
fi

cd "${PAYLOAD}"

echo "  Running: sh scripts/install-unix.sh $*"
echo ""
# Called through sh on purpose: a mounted image can lose the execute bit.
if sh ./scripts/install-unix.sh "$@"; then
  echo ""
  echo "  Done. Start Firefox, then press Cmd+T."
  echo "  Floating search pill, privacy prefs and speed prefs are active."
  echo "  uBlock Origin + Decentraleyes install on that first start."
else
  status=$?
  echo ""
  echo "  The installer exited with code ${status}."
  echo "  Run it with --doctor and paste the output to get help:"
  echo "    sh \"Install SheepFox.command\" --doctor"
fi

echo ""
pause
