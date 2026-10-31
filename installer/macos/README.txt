(SheepFox) Firefox — macOS
==========================

1. Double-click "Install SheepFox.command".
   If macOS blocks it: Control-click it → Open, or open Terminal and run
     sh "/Volumes/SheepFox/Install SheepFox.command"

2. Quit Firefox completely (Cmd+Q; check that no firefox process is left in
   Activity Monitor), then start it again.

3. Press Cmd+T. The New Tab page is Mozilla's own; SheepFox changes prefs and
   the policy, not the interface.

What gets installed
-------------------
  ~/Library/Application Support/Firefox/Profiles/<your profile>/user.js
  /Applications/Firefox.app/Contents/Resources/distribution/policies.json

The policy file is what preinstalls uBlock Origin and Decentraleyes, so macOS
asks for your admin password once. Say no and the preferences still install;
only the extensions wait. Every profile found is updated, so it works whatever
profile Firefox actually opens.

Useful switches
---------------
  sh "Install SheepFox.command" --doctor        diagnose an install
  sh "Install SheepFox.command" --no-extensions policy without uBlock/Decentraleyes
  sh "Install SheepFox.command" --report r.txt  write a full report
  sh "Install SheepFox.command" --low-memory    minimal RAM (turns Fission off)
  sh "Install SheepFox.command" --strict        strict anti-fingerprinting
  sh "Install SheepFox.command" --uninstall     remove everything

Reverting
---------
  --uninstall removes user.js (and any files left by the retired search-bar
  theme in SheepFox 1.2 and older). Backups written by the installer are left
  next to them as <file>.sheepfox-backup-<timestamp>.

Notes
-----
  * The disk image is unsigned. Control-click → Open the first time.
  * If the .command has no execute permission on the mounted volume, run it
    through sh as shown above — the image is read-only, so chmod will not stick.
  * Full documentation: https://github.com/ineednotitle/SheepFox
