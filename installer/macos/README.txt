(SheepFox) Firefox — macOS
==========================

1. Double-click "Install SheepFox.command".
   If macOS blocks it: Control-click it → Open, or open Terminal and run
     sh "/Volumes/SheepFox/Install SheepFox.command"

2. Quit Firefox completely (Cmd+Q; check that no firefox process is left in
   Activity Monitor), then start it again.

3. Press Cmd+T. You should get the floating search pill; Cmd+L floats it over
   any page you are already on.

What gets installed
-------------------
  ~/Library/Application Support/Firefox/Profiles/<your profile>/user.js
  ~/Library/Application Support/Firefox/Profiles/<your profile>/chrome/userChrome.css
  ~/Library/Application Support/Firefox/Profiles/<your profile>/chrome/userContent.css
  /Applications/Firefox.app/Contents/Resources/distribution/policies.json

The policy file is what preinstalls uBlock Origin and Decentraleyes, so macOS
asks for your admin password once. Say no and the theme and preferences still
install; only the extensions wait. Every profile found is updated, so it works
whatever profile Firefox actually opens.

Useful switches
---------------
  sh "Install SheepFox.command" --doctor        diagnose an install
  sh "Install SheepFox.command" --probe         red toolbar = the CSS is loading
  sh "Install SheepFox.command" --no-extensions policy without uBlock/Decentraleyes
  sh "Install SheepFox.command" --report r.txt  write a full report
  sh "Install SheepFox.command" --low-memory    minimal RAM (turns Fission off)
  sh "Install SheepFox.command" --no-ui         everything except the UI theme
  sh "Install SheepFox.command" --strict        strict anti-fingerprinting
  sh "Install SheepFox.command" --uninstall     remove everything

Reverting
---------
  --uninstall removes user.js and the two CSS files. Backups written by the
  installer are left next to them as <file>.sheepfox-backup-<timestamp>.

Notes
-----
  * The disk image is unsigned. Control-click → Open the first time.
  * If the .command has no execute permission on the mounted volume, run it
    through sh as shown above — the image is read-only, so chmod will not stick.
  * Full documentation: https://github.com/ineednotitle/SheepFox
