#!/bin/bash
# ============================================================================
# (SheepFox) Zen Browser — macOS installer
#
# Double-click this file. It runs the same SheepFox installer a git checkout
# would run, against the Zen profiles in ~/Library/Application Support/zen.
#
# Two differences from the Firefox installer, both deliberate:
#   * the floating pill is NOT installed by default - Zen already has its own
#     floating omnibox. Add --ui to install SheepFox's pill as well.
#   * if your Zen came with a policies.json of its own (DisableAppUpdate, ...),
#     those entries are kept instead of being overwritten.
#
# If macOS refuses to run it ("cannot be opened because it is from an
# unidentified developer", or the file has no execute bit on a mounted image):
#   Control-click → Open,  or run:  sh "Install SheepFox for Zen.command"
#
# macOS will ask for your password once: the SheepShields policy file that
# preinstalls uBlock Origin + Decentraleyes lives inside Zen.app.
#
# Switches are forwarded, so you can also do:
#   sh "Install SheepFox for Zen.command" --ui
#   sh "Install SheepFox for Zen.command" --doctor
#   sh "Install SheepFox for Zen.command" --uninstall
# ============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD="${HERE}/SheepFox"

pause() {
  if [ -t 0 ]; then
    read -r -p "Press Return to close..." _ || true
  fi
}

echo ""
echo "  (SheepFox) Zen Browser"
echo "  ----------------------"
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

ZEN_RUNNING="$(pgrep -x zen || true)"
if [ -n "${ZEN_RUNNING}" ]; then
  echo "  Zen is running. Quit it completely before the change takes effect"
  echo "  (user.js and the policy are only read at startup)."
  echo ""
fi

cd "${PAYLOAD}"

echo "  Running: sh scripts/install-zen.sh $*"
echo ""
# Called through sh on purpose: a mounted image can lose the execute bit.
if sh ./scripts/install-zen.sh "$@"; then
  echo ""
  echo "  Done. Start Zen again: the speed and privacy prefs are active."
  echo "  uBlock Origin + Decentraleyes install on that first start."
  echo "  (The floating pill stays out of the way - Zen has its own omnibox."
  echo "   Add --ui if you want SheepFox's pill as well.)"
else
  status=$?
  echo ""
  echo "  The installer exited with code ${status}."
  echo "  Run it with --doctor and paste the output to get help:"
  echo "    sh \"Install SheepFox for Zen.command\" --doctor"
fi

echo ""
pause
