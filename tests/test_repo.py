#!/usr/bin/env python3
"""
Automated Verification Suite for (SheepFox) Firefox Repository.
Validates:
  - Config compilation sync (`user.js` & `sheepfox.cfg`)
  - AutoConfig first-line comment invariant & lockPref/defaultPref rules
  - Speed + Zero-Breakage + LibreFox-Privacy core preference invariants
  - `policies.json` structure & uBlock Origin ("SheepShields") provisioning
  - SVG branding XML validity
  - Unified diff patch hunk integrity
  - End-to-end installer behavior (profile detection, --system, --strict, --uninstall)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


class TestSheepFoxRepo(unittest.TestCase):
    def test_compiled_configs_in_sync(self) -> None:
        res = subprocess.run(
            [sys.executable, str(REPO_ROOT / "build/scripts/build-configs.py"), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)

    def test_autoconfig_header_and_bootstrap(self) -> None:
        cfg_path = REPO_ROOT / "config/autoconfig/sheepfox.cfg"
        lines = cfg_path.read_text(encoding="utf-8").splitlines()
        self.assertTrue(
            lines[0].startswith("//"),
            "Firefox AutoConfig requires line 1 of sheepfox.cfg to be a '//' comment!",
        )
        bootstrap = (REPO_ROOT / "config/autoconfig/defaults/pref/local-settings.js").read_text(
            encoding="utf-8"
        )
        self.assertIn('pref("general.config.obscure_value", 0);', bootstrap)
        self.assertIn('pref("general.config.filename", "sheepfox.cfg");', bootstrap)

    def test_core_speed_privacy_and_stability_invariants(self) -> None:
        user_js = (REPO_ROOT / "config/user.js").read_text(encoding="utf-8")
        prefs: dict[str, object] = {}
        for match in re.finditer(r'user_pref\("([^"]+)",\s*(.+)\);', user_js):
            prefs[match.group(1)] = json.loads(match.group(2))

        # Speed invariants (Brave-class responsiveness)
        self.assertIs(prefs.get("gfx.webrender.all"), True)
        self.assertIs(prefs.get("gfx.webrender.precache-shaders"), True)
        self.assertIs(prefs.get("network.http.http3.enable"), True)
        self.assertEqual(prefs.get("network.http.max-connections"), 1800)
        self.assertIs(prefs.get("browser.cache.memory.enable"), True)

        # Stability & zero-breakage invariants (120Hz+, WebGL, isolated GPU process)
        self.assertIs(prefs.get("privacy.resistFingerprinting"), False)
        self.assertIs(prefs.get("privacy.fingerprintingProtection"), True)
        self.assertIs(prefs.get("layers.gpu-process.enabled"), True)

        # LibreFox-grade privacy & anti-telemetry invariants
        self.assertEqual(prefs.get("network.cookie.cookieBehavior"), 5)
        self.assertIs(prefs.get("dom.security.https_only_mode"), True)
        self.assertIs(prefs.get("privacy.globalprivacycontrol.enabled"), True)
        self.assertIs(prefs.get("privacy.query_stripping.enabled"), True)
        self.assertIs(prefs.get("toolkit.telemetry.enabled"), False)
        self.assertIs(prefs.get("datareporting.policy.dataSubmissionEnabled"), False)
        self.assertIs(prefs.get("dom.private-attribution.submission.enabled"), False)
        self.assertIs(prefs.get("browser.ml.enable"), False)
        self.assertIs(prefs.get("extensions.pocket.enabled"), False)

    def test_policies_json_sheepshields(self) -> None:
        policies_path = REPO_ROOT / "config/distribution/policies.json"
        data = json.loads(policies_path.read_text(encoding="utf-8"))
        policies = data["policies"]
        self.assertIs(policies["DisableTelemetry"], True)
        self.assertIs(policies["DisableFirefoxStudies"], True)
        self.assertIs(policies["DisablePocket"], True)
        ext = policies["ExtensionSettings"]["uBlock0@raymondhill.net"]
        self.assertIn(ext["installation_mode"], {"normal_installed", "force_installed"})
        self.assertTrue(ext["install_url"].endswith(".xpi"))

    def test_svg_branding_assets_valid_xml(self) -> None:
        for svg_name in ["sheepfox-logo.svg", "about-wordmark.svg"]:
            svg_path = REPO_ROOT / "branding/sheepfox/content" / svg_name
            tree = ET.parse(svg_path)
            self.assertTrue(tree.getroot().tag.endswith("svg"))

    def test_patches_series_and_hunk_line_counts(self) -> None:
        series_path = REPO_ROOT / "patches/series"
        patch_names = [
            ln.split("#")[0].strip()
            for ln in series_path.read_text(encoding="utf-8").splitlines()
            if ln.split("#")[0].strip()
        ]
        self.assertGreaterEqual(len(patch_names), 4)

        hunk_re = re.compile(r"^@@ -(\d+),(\d+) \+(\d+),(\d+) @@")
        for name in patch_names:
            pfile = REPO_ROOT / "patches" / name
            self.assertTrue(pfile.exists(), f"Missing patch listed in series: {name}")
            lines = pfile.read_text(encoding="utf-8").splitlines()
            idx = 0
            found_hunk = False
            while idx < len(lines):
                m = hunk_re.match(lines[idx])
                if not m:
                    idx += 1
                    continue
                found_hunk = True
                old_expected = int(m.group(2))
                new_expected = int(m.group(4))
                old_actual = 0
                new_actual = 0
                idx += 1
                while idx < len(lines) and not lines[idx].startswith(("@@ ", "diff --git ", "-- ")):
                    hline = lines[idx]
                    if hline.startswith("-"):
                        old_actual += 1
                    elif hline.startswith("+"):
                        new_actual += 1
                    elif hline.startswith(" "):
                        old_actual += 1
                        new_actual += 1
                    idx += 1
                self.assertEqual(old_actual, old_expected, f"Old hunk count mismatch in {name}")
                self.assertEqual(new_actual, new_expected, f"New hunk count mismatch in {name}")
            self.assertTrue(found_hunk, f"No diff hunks found in {name}")

    def test_installer_end_to_end_mock_profile_and_system(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            prof_dir = tmp_path / "profile.default-release"
            ff_dir = tmp_path / "firefox-bin"
            prof_dir.mkdir()
            ff_dir.mkdir()

            # Pre-seed an existing user.js to verify backup creation
            (prof_dir / "user.js").write_text('// old user.js\n', encoding="utf-8")

            res = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/install.py"),
                    "--profile",
                    str(prof_dir),
                    "--firefox-dir",
                    str(ff_dir),
                    "--system",
                    "--strict",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr or res.stdout)

            installed_user_js = (prof_dir / "user.js").read_text(encoding="utf-8")
            self.assertIn('user_pref("gfx.webrender.all", true);', installed_user_js)
            self.assertIn('user_pref("privacy.resistFingerprinting", true);', installed_user_js)
            backups = list(prof_dir.glob("user.js.sheepfox-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertTrue((ff_dir / "sheepfox.cfg").exists())
            self.assertTrue((ff_dir / "defaults/pref/local-settings.js").exists())
            self.assertTrue((ff_dir / "distribution/policies.json").exists())

            # Test clean uninstall
            res_un = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts/install.py"),
                    "--profile",
                    str(prof_dir),
                    "--firefox-dir",
                    str(ff_dir),
                    "--system",
                    "--uninstall",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res_un.returncode, 0, msg=res_un.stderr or res_un.stdout)
            self.assertFalse((prof_dir / "user.js").exists())
            self.assertFalse((ff_dir / "sheepfox.cfg").exists())


if __name__ == "__main__":
    unittest.main()
