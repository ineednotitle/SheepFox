#!/usr/bin/env python3
"""
Automated verification suite for the (SheepFox) Zen browser repository.

Every guarantee the README makes is enforced here, so CI can never publish a
build whose docs and behaviour disagree:

  * config/modules/*.js  <->  config/user.js  <->  config/autoconfig/sheepfox.cfg
  * AutoConfig first-line comment rule and lockPref()/defaultPref() semantics
  * speed, privacy and zero-breakage preference invariants
  * SheepShields policies.json (uBlock Origin + curated filter lists)
  * branding XML validity and brand strings
  * unified-diff hunk arithmetic and diffstat consistency for patches/series
  * Windows launcher correctness (no BOM, CRLF, ExecutionPolicy bypass)
  * installer install/uninstall/dry-run behaviour against a mock profile
  * mozconfig correctness for the custom fork build
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MODULES_DIR = REPO_ROOT / "config" / "modules"
USER_JS = REPO_ROOT / "config" / "user.js"
CFG = REPO_ROOT / "config" / "autoconfig" / "sheepfox.cfg"
LOCAL_SETTINGS = REPO_ROOT / "config" / "autoconfig" / "defaults" / "pref" / "local-settings.js"
POLICIES = REPO_ROOT / "config" / "distribution" / "policies.json"
BUILD_CONFIGS = REPO_ROOT / "mozbuild" / "scripts" / "build-configs.py"

PREF_LINE_RE = re.compile(r'^(?P<fn>user_pref|defaultPref|lockPref)\("(?P<name>[^"]+)",\s*(?P<value>.+?)\);')
LOCK_ANNOTATION_RE = re.compile(r"//\s*@lock\b")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_compiler():
    """Import mozbuild/scripts/build-configs.py as a module."""
    spec = importlib.util.spec_from_file_location("sheepfox_build_configs", BUILD_CONFIGS)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve the module's namespace.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def parse_prefs(text: str, functions: tuple[str, ...]) -> dict[str, tuple[object, str]]:
    """Parse pref assignments into {name: (value, function)}."""
    prefs: dict[str, tuple[object, str]] = {}
    for line in text.splitlines():
        match = PREF_LINE_RE.match(line.strip())
        if not match or match.group("fn") not in functions:
            continue
        name = match.group("name")
        if name in prefs:
            raise AssertionError(f"duplicate preference in generated output: {name}")
        prefs[name] = (json.loads(match.group("value")), match.group("fn"))
    return prefs


class TestGeneratedConfigs(unittest.TestCase):
    """config/modules/*.js must be the single source of truth."""

    def test_generated_configs_are_in_sync(self) -> None:
        result = subprocess.run(
            [sys.executable, str(BUILD_CONFIGS), "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)

    def test_compiler_rejects_duplicates_and_bad_values(self) -> None:
        compiler = load_compiler()
        with tempfile.TemporaryDirectory() as tmp:
            module_path = Path(tmp) / "99-broken.js"
            module_path.write_text(
                'user_pref("a.b", 1);\nuser_pref("A.B", 2);\n', encoding="utf-8"
            )
            parsed = compiler.parse_module(module_path)
            self.assertEqual(len(parsed.prefs), 2)

            # Case-insensitive duplicates across modules are a hard error.
            original = compiler.MODULES_DIR
            compiler.MODULES_DIR = Path(tmp)
            try:
                with self.assertRaises(compiler.ConfigError):
                    compiler.load_modules()
            finally:
                compiler.MODULES_DIR = original

            bad = Path(tmp) / "98-bad.js"
            bad.write_text('user_pref("bad.float", 1.5);\n', encoding="utf-8")
            with self.assertRaises(compiler.ConfigError):
                compiler.parse_module(bad)

            syntax = Path(tmp) / "97-syntax.js"
            syntax.write_text('pref("nope", true);\n', encoding="utf-8")
            with self.assertRaises(compiler.ConfigError):
                compiler.parse_module(syntax)

    def test_every_pref_value_is_a_valid_json_literal(self) -> None:
        for module in sorted(MODULES_DIR.glob("*.js")):
            for lineno, line in enumerate(read(module).splitlines(), start=1):
                match = PREF_LINE_RE.match(line.strip())
                if not match:
                    continue
                try:
                    value = json.loads(match.group("value"))
                except json.JSONDecodeError as exc:  # pragma: no cover - failure path
                    self.fail(f"{module.name}:{lineno}: invalid literal: {exc}")
                self.assertIn(
                    type(value),
                    (bool, int, str),
                    msg=f"{module.name}:{lineno}: unsupported pref type {type(value).__name__}",
                )


class TestAutoConfig(unittest.TestCase):
    """sheepfox.cfg must satisfy Firefox's AutoConfig loader contract."""

    def test_first_line_is_a_comment(self) -> None:
        lines = read(CFG).splitlines()
        self.assertTrue(
            lines[0].startswith("//"),
            "line 1 of sheepfox.cfg must be a // comment; Firefox skips it",
        )

    def test_lockpref_only_for_annotated_prefs(self) -> None:
        annotated: set[str] = set()
        for module in sorted(MODULES_DIR.glob("*.js")):
            for line in read(module).splitlines():
                match = PREF_LINE_RE.match(line.strip())
                if match and LOCK_ANNOTATION_RE.search(line):
                    annotated.add(match.group("name"))

        cfg_prefs = parse_prefs(read(CFG), ("lockPref", "defaultPref"))
        locked = {name for name, (_, fn) in cfg_prefs.items() if fn == "lockPref"}
        defaulted = {name for name, (_, fn) in cfg_prefs.items() if fn == "defaultPref"}

        self.assertEqual(locked, annotated, "lockPref() set must match `// @lock` lines exactly")
        self.assertFalse(locked & defaulted)
        self.assertGreater(len(locked), 10, "telemetry/ads/ML locks are expected")
        self.assertNotIn("user_pref(", read(CFG))

    def test_bootstrap_local_settings(self) -> None:
        bootstrap = read(LOCAL_SETTINGS)
        self.assertIn('pref("general.config.obscure_value", 0);', bootstrap)
        self.assertIn('pref("general.config.filename", "sheepfox.cfg");', bootstrap)
        self.assertIn('pref("general.config.sandbox_enabled", true);', bootstrap)

    def test_cfg_and_userjs_cover_the_same_preferences(self) -> None:
        cfg_prefs = parse_prefs(read(CFG), ("lockPref", "defaultPref"))
        user_prefs = parse_prefs(read(USER_JS), ("user_pref",))
        self.assertEqual(set(cfg_prefs), set(user_prefs))
        for name, (cfg_value, _) in cfg_prefs.items():
            self.assertEqual(cfg_value, user_prefs[name][0], msg=f"value drift for {name}")


class TestPreferenceInvariants(unittest.TestCase):
    """The speed / privacy / stability promise, asserted against generated files."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.cfg = parse_prefs(read(CFG), ("lockPref", "defaultPref"))
        cls.user = parse_prefs(read(USER_JS), ("user_pref",))

    def value(self, name: str) -> object:
        self.assertIn(name, self.user, msg=f"missing required preference: {name}")
        return self.user[name][0]

    def test_speed_defaults(self) -> None:
        self.assertIs(self.value("gfx.webrender.all"), True)
        self.assertIs(self.value("gfx.webrender.precache-shaders"), True)
        self.assertIs(self.value("gfx.canvas.accelerated"), True)
        self.assertEqual(self.value("gfx.canvas.accelerated.cache-size"), 512)
        self.assertEqual(self.value("gfx.content.skia-font-cache-size"), 20)
        self.assertEqual(self.value("browser.cache.memory.capacity"), 262144)
        self.assertIs(self.value("browser.cache.disk.enable"), False)
        self.assertEqual(self.value("browser.sessionhistory.max_total_viewers"), 4)
        self.assertIs(self.value("network.http.http3.enable"), True)
        self.assertIs(self.value("network.http.pacing.requests.enabled"), False)
        self.assertEqual(self.value("network.http.max-connections"), 1800)
        self.assertEqual(self.value("network.http.max-persistent-connections-per-server"), 10)

    def test_privacy_defaults(self) -> None:
        self.assertEqual(self.value("network.cookie.cookieBehavior"), 5)
        self.assertIs(self.value("privacy.partition.network_state"), True)
        self.assertIs(self.value("privacy.globalprivacycontrol.enabled"), True)
        self.assertIs(self.value("privacy.query_stripping.enabled"), True)
        self.assertIs(self.value("dom.security.https_only_mode"), True)
        self.assertEqual(self.value("security.OCSP.enabled"), 0)
        self.assertEqual(self.value("security.pki.crlite_mode"), 2)
        self.assertIs(self.value("media.peerconnection.ice.default_address_only"), True)
        self.assertEqual(self.value("network.trr.mode"), 2)
        self.assertEqual(self.value("network.trr.uri"), "https://dns.quad9.net/dns-query")

    def test_zero_breakage_rules(self) -> None:
        # RFP must never be the default: it caps 120Hz+ displays at 60Hz.
        self.assertIs(self.value("privacy.resistFingerprinting"), False)
        self.assertIs(self.value("privacy.fingerprintingProtection"), True)
        # GPU crash isolation must stay on.
        self.assertIs(self.value("layers.gpu-process.enabled"), True)
        # Nothing may disable WebGL, JIT or the GPU process outright.
        self.assertIsNot(self.value("webgl.disabled") if "webgl.disabled" in self.user else False, True)
        # RFP must not be locked, so users can opt in via --strict instead.
        self.assertNotEqual(self.cfg["privacy.resistFingerprinting"][1], "lockPref")

    def test_telemetry_ads_and_ml_are_off_and_locked(self) -> None:
        for name in (
            "datareporting.policy.dataSubmissionEnabled",
            "datareporting.healthreport.uploadEnabled",
            "toolkit.telemetry.unified",
            "toolkit.telemetry.enabled",
            "app.normandy.enabled",
            "app.shield.optoutstudies.enabled",
            "dom.private-attribution.submission.enabled",
            "extensions.pocket.enabled",
            "browser.newtabpage.activity-stream.showSponsored",
            "browser.urlbar.suggest.quicksuggest.sponsored",
            "browser.ml.enable",
        ):
            self.assertIn(name, self.cfg, msg=f"{name} must be present")
            self.assertIs(self.cfg[name][0], False, msg=f"{name} must be false")
            self.assertEqual(self.cfg[name][1], "lockPref", msg=f"{name} must be locked")

        self.assertIs(self.value("extensions.ml.enabled"), False)

    def test_resource_footprint_prefs(self) -> None:
        # Deliberately below Firefox defaults: fewer processes, smaller media
        # cache, lazier session writes.
        self.assertLess(self.value("dom.ipc.processCount"), 8)
        self.assertEqual(self.value("dom.ipc.processCount"), 6)
        self.assertLess(self.value("media.cache_size"), 512000)
        self.assertGreaterEqual(self.value("browser.sessionstore.interval"), 60000)
        self.assertIs(self.value("browser.tabs.unloadOnLowMemory"), True)

    def test_low_memory_override_is_opt_in(self) -> None:
        override = read(REPO_ROOT / "config" / "overrides" / "low-memory.override.js")
        self.assertIn('user_pref("fission.autostart", false);', override)
        self.assertIn("TRADE-OFF", override)
        # Never applied by default.
        self.assertNotIn("fission.autostart", read(USER_JS))
        self.assertNotIn("fission.autostart", read(CFG))

    def test_fullscreen_and_scroll_physics(self) -> None:
        self.assertEqual(self.value("full-screen-api.transition-duration.enter"), "0 0")
        self.assertEqual(self.value("full-screen-api.transition-duration.leave"), "0 0")
        self.assertIs(self.value("general.smoothScroll.msdPhysics.enabled"), True)
        self.assertGreaterEqual(self.value("general.smoothScroll.msdPhysics.regularSpringConstant"), 600)

    def test_strict_override_is_opt_in_only(self) -> None:
        strict = read(REPO_ROOT / "config" / "overrides" / "strict-paranoia.override.js")
        self.assertIn('user_pref("privacy.resistFingerprinting", true);', strict)
        self.assertNotIn("privacy.resistFingerprinting\", true", read(USER_JS))
        example = REPO_ROOT / "config" / "overrides" / "user-overrides.example.js"
        self.assertTrue(example.is_file())


class TestFloatingSearchUI(unittest.TestCase):
    """The Zen/Arc-style floating new-tab search pill."""

    CHROME = REPO_ROOT / "config" / "chrome" / "userChrome.css"
    CONTENT = REPO_ROOT / "config" / "chrome" / "userContent.css"

    def test_assets_exist_and_are_balanced(self) -> None:
        for path in (self.CHROME, self.CONTENT):
            self.assertTrue(path.is_file(), msg=f"missing {path.name}")
            text = read(path)
            self.assertEqual(
                text.count("{"), text.count("}"), msg=f"{path.name}: unbalanced braces"
            )
            self.assertTrue(text.lstrip().startswith("/*"), msg=f"{path.name}: needs a header")
        # A default @namespace makes `*#urlbar` match only that namespace, and
        # #urlbar has been an HTML element since Firefox 140 - so declaring one
        # silently disables the whole theme. See the header of userChrome.css.
        self.assertNotRegex(
            read(self.CHROME), r"(?m)^\s*@namespace", msg="a default @namespace breaks #urlbar"
        )
        self.assertIn("@-moz-document", read(self.CONTENT), msg="userContent.css needs a scope")

    def test_style_legacy_sheets_is_enabled(self) -> None:
        # userChrome.css is only honoured when this pref is true at startup.
        user_js = parse_prefs(read(USER_JS), ("user_pref",))
        self.assertIn("toolkit.legacyUserProfileCustomizations.stylesheets", user_js)
        self.assertIs(user_js["toolkit.legacyUserProfileCustomizations.stylesheets"][0], True)

    #: Every attribute that puts the bar into its floating state.
    STATES = (
        '[pageproxystate="invalid"]',
        '[focused="true"]',
        '[breakout][breakout-extend]',
        '[expanded]',
        '[open]',
    )

    @property
    def shell(self) -> str:
        """The pill's main rule: everything between the two markers below."""
        css = read(self.CHROME)
        begin = css.index("1. THE PILL SHELL")
        return css[begin : css.index("With suggestions open", begin)]

    def test_pill_is_scoped_to_the_floating_states(self) -> None:
        css = read(self.CHROME)
        shell = self.shell
        self.assertIn("#urlbar:is(", shell, msg="states must be listed in one :is() list")
        for state in self.STATES:
            self.assertIn(state, shell, msg=f"missing floating state {state}")
        # [focused="true"] is what makes Ctrl+L / clicking the bar float it over
        # the page you are already on, instead of only working on a blank tab.
        self.assertIn('[focused="true"]', shell)
        self.assertIn("position: fixed", shell, msg="the pill must leave the toolbar")
        # Firefox sets top/left/width on the breakout state, so those need
        # !important or the bar snaps back into the toolbar.
        for prop in ("top:", "left:", "width:", "position:"):
            self.assertIn(prop, shell)
        self.assertIn("!important", shell)
        # Centre with auto inline margins. left:%+translate assumed the window
        # was the containing block; when an ancestor claims the fixed bar it
        # lands half a pill width to the left. left:0 + right:0 + margin:auto is
        # correct either way.
        self.assertIn("left: 0 !important", shell)
        self.assertIn("right: 0 !important", shell)
        self.assertIn("margin-inline: auto", shell)
        self.assertNotIn("translate: -50%", shell, msg="translate centring drifts off-centre")
        # A `margin` shorthand after margin-inline:auto resets it to 0 and the
        # pill silently loses its centring.
        self.assertNotIn("margin: 0", shell, msg="margin shorthand would un-centre the pill")
        self.assertIn("margin-block: 0", shell)
        self.assertIn("outline: none", shell, msg="the pill replaces Firefox's focus ring")
        self.assertIn("visibility: visible", shell)
        self.assertIn("opacity: 1", shell)
        self.assertNotRegex(shell, r"(?m)^\s*transform:", msg="never transform the pill into place")
        self.assertIn("border-radius: var(--sheepfox-pill-radius)", shell)
        self.assertIn("box-shadow", shell)
        self.assertIn("clamp(", css, msg="pill width must be responsive")
        # Never hide or disable the address bar itself.
        self.assertNotRegex(css, r"#urlbar\s*\{[^}]*display:\s*none")

    def test_inner_layout_is_scoped_to_the_pill(self) -> None:
        """Regression: unscoped rules inflated the toolbar bar on every page.

        Styling `#urlbar #urlbar-input` / `#urlbar .urlbar-input-container`
        without a state matched normal browsing too, so YouTube and every other
        site got a full-width, 56px, centre-aligned address bar.
        """
        css = read(self.CHROME)
        self.assertNotIn("#urlbar #urlbar-input {", css)
        self.assertNotIn("#urlbar .urlbar-input-container {", css)
        self.assertNotRegex(css, r"(?m)^#urlbar #urlbar-background")
        # Every rule that alters the field's text alignment must be state-gated.
        for match in re.finditer(r"(?m)^([^\n{}]+)\{[^}]*text-align:\s*center", css):
            selector = match.group(1)
            self.assertIn(":is(", selector, msg=f"unscoped centring: {selector.strip()}")
        # Same for the input container's height.
        for match in re.finditer(r"(?m)^([^\n{}]+)\{[^}]*height: var\(--sheepfox-pill-height\)", css):
            self.assertIn(":is(", match.group(1), msg=f"unscoped pill height: {match.group(1).strip()}")

    def test_pill_is_vertically_centred_and_compact(self) -> None:
        css = read(self.CHROME)
        # Zen/Arc look: centred in the page, not pinned to the toolbar row.
        # Viewport units: a percentage would resolve against the (collapsed)
        # toolbar container instead of the window.
        self.assertIn("--sheepfox-pill-top: 42vh", css)
        self.assertIn("--sheepfox-pill-height: 52px", css)
        self.assertIn(
            "top: calc(var(--sheepfox-pill-top) - var(--sheepfox-pill-height) / 2)",
            css,
            msg="pill vertical anchor must stay centred but top-anchored",
        )
        # Collapsed state is locked so the auto-opened dropdown cannot balloon
        # it; the open state may grow again, capped.
        self.assertIn("max-height: var(--sheepfox-pill-height)", css)
        grown = css[css.index("With suggestions open") :]
        self.assertIn("max-height: 62vh", grown)
        # No ancestor may become the containing block of the fixed bar.
        self.assertIn("will-change: auto", css)
        self.assertIn("translate: none", css, msg="ancestor translate creates a containing block")
        self.assertIn("container-type: normal", css)

    def test_empty_new_tab_collapses_the_suggestions_panel(self) -> None:
        # Firefox opens the awesomebar results view on the new-tab autofocus;
        # an empty tab must stay a pill, so that view is collapsed while the
        # field is empty.
        css = read(self.CHROME)
        hidden = css.split("#urlbar:has(#urlbar-input:placeholder-shown) #urlbar-results", 1)[1].split("}", 1)[0]
        self.assertIn("display: none", hidden)
        # The dock-while-typing opt-out ships commented out, so the default stays
        # the Zen/Arc behaviour.
        self.assertIn("/*\n#urlbar:is([breakout][breakout-extend], [expanded], [open]) {", css)
        self.assertIn("position: relative !important;", css)
        # Zen's dimming backdrop ships commented out too.
        self.assertIn("#urlbar[open]::after", css)  # Zen backdrop, commented out
        self.assertIn("backdrop-filter: blur(5px)", css)

    def test_proof_of_load_badge(self) -> None:
        """A visible marker drawn by userChrome.css itself."""
        css = read(self.CHROME)
        self.assertIn('#nav-bar::after', css)
        self.assertIn('content: "SheepFox UI"', css)
        self.assertIn("pointer-events: none", css)
        # It must not steal clicks or sit above the pill.
        badge = css.split("#nav-bar::after", 1)[1].split("}", 1)[0]
        self.assertIn("position: fixed", badge)

    def test_stylesheet_imports_the_probe(self) -> None:
        css = read(self.CHROME)
        self.assertIn('@import url("sheepfox-probe.css");', css)
        # @import must come before any rule other than @charset/@layer.
        body = css[css.index("*/") :]  # skip the header comment
        self.assertLess(body.index("@import"), body.index(":root {"))

    def test_installers_can_write_and_remove_the_probe(self) -> None:
        installer = read(REPO_ROOT / "scripts" / "install.py")
        for token in ("--probe", "--unprobe", "sheepfox-probe.css", "#cc0000"):
            self.assertIn(token, installer)
        ps1 = (REPO_ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8")
        for token in ("[switch]$Probe", "[switch]$Unprobe", "sheepfox-probe.css", "#cc0000"):
            self.assertIn(token, ps1)

    def test_dark_mode_and_reduced_motion(self) -> None:
        css = read(self.CHROME)
        self.assertIn("prefers-color-scheme: light", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn("prefers-reduced-motion: reduce", css)

    def test_new_tab_page_makes_room_for_the_pill(self) -> None:
        css = read(self.CONTENT)
        self.assertIn('@-moz-document url("about:newtab"), url("about:home")', css)
        self.assertIn(".logo-and-wordmark", css, msg="wordmark must be cleared")
        self.assertIn("padding-top", css, msg="shortcuts must be pushed below the pill")

    def test_installers_ship_the_ui(self) -> None:
        installer = read(REPO_ROOT / "scripts" / "install.py")
        self.assertIn('UI_FILES = ("userChrome.css", "userContent.css")', installer)
        self.assertIn('"chrome"', installer)
        self.assertIn("--no-ui", installer)

        ps1 = (REPO_ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("$NoUI", ps1)
        self.assertIn("userChrome.css", ps1)
        self.assertIn('Join-Path $profile "chrome\\$name"', ps1)
        self.assertIn("foreach ($profile in $Profiles)", ps1, msg="must install into every profile")


class TestPolicies(unittest.TestCase):
    """SheepShields must provision uBlock Origin without breaking the browser."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(read(POLICIES))["policies"]

    def test_core_policies(self) -> None:
        self.assertIs(self.data["DisableTelemetry"], True)
        self.assertIs(self.data["DisableFirefoxStudies"], True)
        self.assertIs(self.data["DisablePocket"], True)
        self.assertIs(self.data["DisableFirefoxSuggest"], True)
        self.assertEqual(self.data["HttpsOnlyMode"], "enabled")
        self.assertIs(self.data["EnableTrackingProtection"]["Value"], True)
        # Security updates must never be disabled by a privacy config.
        self.assertNotIn("DisableAppUpdate", self.data)
        self.assertNotEqual(self.data.get("DisableAppUpdate"), True)

    def test_ublock_origin_extension(self) -> None:
        settings = self.data["ExtensionSettings"]
        self.assertEqual(settings["*"]["installation_mode"], "allowed")
        ublock = settings["uBlock0@raymondhill.net"]
        self.assertEqual(ublock["installation_mode"], "normal_installed")
        self.assertTrue(ublock["install_url"].startswith("https://addons.mozilla.org/"))
        self.assertTrue(ublock["install_url"].endswith(".xpi"))

    def test_decentraleyes_extension(self) -> None:
        settings = self.data["ExtensionSettings"]
        decentraleyes = settings["jid1-BoFifL9Vbdl2zQ@jetpack"]
        self.assertEqual(decentraleyes["installation_mode"], "normal_installed")
        self.assertEqual(
            decentraleyes["install_url"],
            "https://addons.mozilla.org/firefox/downloads/latest/decentraleyes/latest.xpi",
        )
        self.assertIs(decentraleyes["private_browsing"], True)
        # Both extensions stay removable: a policy must never trap the user.
        for extension_id in ("uBlock0@raymondhill.net", "jid1-BoFifL9Vbdl2zQ@jetpack"):
            self.assertEqual(settings[extension_id]["installation_mode"], "normal_installed")

    def test_curated_filter_lists(self) -> None:
        lists = self.data["3rdparty"]["Extensions"]["uBlock0@raymondhill.net"]["toOverwrite"][
            "filterLists"
        ]
        for required in ("easylist", "easyprivacy", "ublock-badware", "ublock-privacy", "urlhaus-1"):
            self.assertIn(required, lists)


class TestExtensionPreinstall(unittest.TestCase):
    """uBlock Origin + Decentraleyes must arrive without the user hunting for them."""

    INSTALLER = REPO_ROOT / "scripts" / "install.py"

    @staticmethod
    def _module():
        spec = importlib.util.spec_from_file_location("sheepfox_install", TestExtensionPreinstall.INSTALLER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_render_policies_keeps_both_extensions(self) -> None:
        policy = json.loads(self._module().render_policies(True))["policies"]
        settings = policy["ExtensionSettings"]
        self.assertIn("uBlock0@raymondhill.net", settings)
        self.assertIn("jid1-BoFifL9Vbdl2zQ@jetpack", settings)

    def test_render_policies_can_skip_the_extensions(self) -> None:
        policy = json.loads(self._module().render_policies(False))["policies"]
        settings = policy["ExtensionSettings"]
        self.assertEqual(set(settings), {"*"}, msg="only the wildcard should remain")
        self.assertNotIn("uBlock0@raymondhill.net", policy.get("3rdparty", {}).get("Extensions", {}))
        # Everything else still applies: this is an opt-out, not a cancel.
        self.assertIs(policy["DisableTelemetry"], True)
        self.assertEqual(policy["HttpsOnlyMode"], "enabled")

    def test_system_install_writes_the_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.INSTALLER),
                    "--profile",
                    str(profile),
                    "--system",
                    "--firefox-dir",
                    str(firefox_dir),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            written = json.loads((firefox_dir / "distribution" / "policies.json").read_text(encoding="utf-8"))
            self.assertIn("jid1-BoFifL9Vbdl2zQ@jetpack", written["policies"]["ExtensionSettings"])
            self.assertIn("uBlock Origin + Decentraleyes", result.stdout)

    def test_no_extensions_flag_keeps_the_rest_of_the_policy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    str(self.INSTALLER),
                    "--profile",
                    str(profile),
                    "--system",
                    "--firefox-dir",
                    str(firefox_dir),
                    "--no-extensions",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            written = json.loads((firefox_dir / "distribution" / "policies.json").read_text(encoding="utf-8"))
            self.assertEqual(set(written["policies"]["ExtensionSettings"]), {"*"})
            self.assertIs(written["policies"]["DisableTelemetry"], True)

    def test_a_plain_run_installs_the_policy_too(self) -> None:
        """No --profile: the extensions ride along without any extra switch."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            profile = home / ".mozilla" / "firefox" / "abc123.default-release"
            profile.mkdir(parents=True)
            (home / ".mozilla" / "firefox" / "profiles.ini").write_text(
                "[Profile0]\nName=default-release\nIsRelative=1\nPath=abc123.default-release\nDefault=1\n",
                encoding="utf-8",
            )
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            environment = dict(os.environ, HOME=str(home))
            result = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--firefox-dir", str(firefox_dir)],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            written = firefox_dir / "distribution" / "policies.json"
            self.assertTrue(written.is_file(), msg=result.stdout)
            policy = json.loads(written.read_text(encoding="utf-8"))["policies"]
            self.assertIn("uBlock0@raymondhill.net", policy["ExtensionSettings"])
            self.assertIn("jid1-BoFifL9Vbdl2zQ@jetpack", policy["ExtensionSettings"])
            # The CSS still landed in the detected profile.
            self.assertTrue((profile / "chrome" / "userChrome.css").is_file())

    def test_doctor_reports_the_extension_preinstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            subprocess.run(
                [sys.executable, str(self.INSTALLER), "--profile", str(profile), "--system", "--firefox-dir", str(firefox_dir)],
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--profile", str(profile), "--firefox-dir", str(firefox_dir), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("[OK  ] extension preinstall (uBlock Origin + Decentraleyes)", result.stdout)

    def test_doctor_stays_green_when_extensions_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            subprocess.run(
                [
                    sys.executable,
                    str(self.INSTALLER),
                    "--profile",
                    str(profile),
                    "--system",
                    "--firefox-dir",
                    str(firefox_dir),
                    "--no-extensions",
                ],
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--profile", str(profile), "--firefox-dir", str(firefox_dir), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("extension preinstall skipped for: uBlock Origin, Decentraleyes", result.stdout)
            self.assertNotIn("[FAIL]", result.stdout)

    def test_plain_uninstall_removes_the_policy(self) -> None:
        """Whatever a plain run installs, a plain --uninstall has to remove."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            profile = home / ".mozilla" / "firefox" / "abc.default-release"
            profile.mkdir(parents=True)
            (home / ".mozilla" / "firefox" / "profiles.ini").write_text(
                "[Profile0]\nName=default-release\nIsRelative=1\nPath=abc.default-release\nDefault=1\n",
                encoding="utf-8",
            )
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            environment = dict(os.environ, HOME=str(home))
            subprocess.run(
                [sys.executable, str(self.INSTALLER), "--firefox-dir", str(firefox_dir)],
                capture_output=True,
                check=True,
                env=environment,
            )
            policy = firefox_dir / "distribution" / "policies.json"
            self.assertTrue(policy.is_file())
            result = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--firefox-dir", str(firefox_dir), "--uninstall"],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertFalse(policy.exists(), msg="the policy survived --uninstall")
            self.assertFalse((profile / "user.js").exists())

    def test_windows_installer_defaults_to_the_policy(self) -> None:
        ps1 = read(REPO_ROOT / "scripts" / "install-windows.ps1")
        self.assertIn("[switch]$ProfileOnly", ps1)
        self.assertIn("[switch]$NoExtensions", ps1)
        self.assertIn("$System = $true", ps1, msg="-System must default on for real installs")
        self.assertIn("-ProfileOnly", ps1)
        self.assertIn("uBlock Origin + Decentraleyes", ps1)
        self.assertIn("jid1-BoFifL9Vbdl2zQ@jetpack", ps1)
        launcher = read(REPO_ROOT / "installer" / "windows" / "launcher.c")
        self.assertIn("-ProfileOnly", launcher)
        self.assertIn("-NoExtensions", launcher)


class TestBranding(unittest.TestCase):
    def test_svgs_are_valid_xml_vectors(self) -> None:
        for name in ("sheepfox-logo.svg", "about-wordmark.svg"):
            path = REPO_ROOT / "branding" / "sheepfox" / "content" / name
            root = ET.parse(path).getroot()
            self.assertTrue(root.tag.endswith("svg"), msg=f"{name} root must be <svg>")
            self.assertIsNotNone(root.get("viewBox"))
            raw = read(path)
            self.assertIn('xmlns="http://www.w3.org/2000/svg"', raw)
            self.assertNotIn("<script", raw.lower())
            self.assertNotIn("javascript:", raw.lower())
            # Vector-only: no raster payloads smuggled in.
            self.assertNotIn("<image", raw)

    def test_brand_strings(self) -> None:
        ftl = read(REPO_ROOT / "branding" / "sheepfox" / "locales" / "en-US" / "brand.ftl")
        dtd = read(REPO_ROOT / "branding" / "sheepfox" / "locales" / "en-US" / "brand.dtd")
        props = read(REPO_ROOT / "branding" / "sheepfox" / "locales" / "en-US" / "brand.properties")
        for blob in (ftl, dtd, props):
            self.assertIn("SheepFox", blob)
            self.assertIn("(SheepFox) Zen browser", blob)
        self.assertIn("-brand-full-name = (SheepFox) Zen browser", ftl)

    def test_configure_sh_sets_identity_and_clears_telemetry(self) -> None:
        configure = read(REPO_ROOT / "branding" / "sheepfox" / "configure.sh")
        self.assertIn("MOZ_APP_NAME=sheepfox", configure)
        self.assertIn('MOZ_APP_DISPLAYNAME="SheepFox"', configure)
        for cleared in ("MOZ_TELEMETRY_REPORTING=", "MOZ_DATA_REPORTING=", "MOZ_CRASHREPORTER="):
            self.assertIn(cleared, configure)

    def test_nsis_installer_branding(self) -> None:
        nsi = read(REPO_ROOT / "branding" / "sheepfox" / "branding.nsi")
        self.assertIn('!define BrandShortName           "SheepFox"', nsi)
        self.assertIn('!define BrandFullName            "(SheepFox) Zen browser"', nsi)


class TestPatchSeries(unittest.TestCase):
    """Unified diffs must be arithmetically consistent and internally coherent."""

    HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

    def series(self) -> list[str]:
        names = []
        for line in read(REPO_ROOT / "patches" / "series").splitlines():
            entry = line.split("#", 1)[0].strip()
            if entry:
                names.append(entry)
        return names

    def test_series_is_ordered_and_complete(self) -> None:
        names = self.series()
        self.assertGreaterEqual(len(names), 4)
        self.assertEqual(names, sorted(names), "patch series must be applied in filename order")
        for index, name in enumerate(names, start=1):
            self.assertTrue(name.startswith(f"{index:04d}-"), msg=f"bad prefix: {name}")
            self.assertTrue((REPO_ROOT / "patches" / name).is_file(), msg=f"missing {name}")
        on_disk = {p.name for p in (REPO_ROOT / "patches").glob("*.patch")}
        self.assertEqual(on_disk, set(names), "stray .patch files not listed in series")

    def test_hunks_and_diffstat_match(self) -> None:
        for name in self.series():
            text = read(REPO_ROOT / "patches" / name)
            self.assertNotIn("\r", text, msg=f"{name}: patches must use LF endings")
            self.assertTrue(text.endswith("\n"), msg=f"{name}: missing trailing newline")

            lines = text.splitlines()
            files_changed = 0
            insertions = 0
            deletions = 0
            stat_files: dict[str, tuple[int, int]] = {}
            idx = 0
            saw_hunk = False

            while idx < len(lines):
                line = lines[idx]

                # --- diff --git header
                if line.startswith("diff --git "):
                    match = re.match(r"^diff --git a/(\S+) b/(\S+)$", line)
                    self.assertIsNotNone(match, msg=f"{name}: malformed diff --git header")
                    files_changed += 1
                    idx += 1
                    continue

                # --- per-file diffstat line (before the first diff --git)
                stat = re.match(r"^ (\S+) \| \d+ ([+\-]+)$", line)
                if stat and not saw_hunk:
                    stat_files[stat.group(1)] = (
                        stat.group(2).count("+"),
                        stat.group(2).count("-"),
                    )
                    idx += 1
                    continue

                if line.startswith("--- ") and not saw_hunk:
                    self.assertTrue(line.startswith("--- a/"), msg=f"{name}: bad --- header")
                    idx += 1
                    continue
                if line.startswith("+++ ") and not saw_hunk:
                    self.assertTrue(line.startswith("+++ b/"), msg=f"{name}: bad +++ header")
                    idx += 1
                    continue

                match = self.HUNK_RE.match(line)
                if not match:
                    idx += 1
                    continue

                saw_hunk = True
                old_expected = int(match.group(2)) if match.group(2) is not None else 1
                new_expected = int(match.group(4)) if match.group(4) is not None else 1
                old_actual = 0
                new_actual = 0
                idx += 1
                while idx < len(lines) and not lines[idx].startswith(("@@ ", "diff --git ")):
                    body = lines[idx]
                    if body.startswith(("--- ", "+++ ")):
                        idx += 1
                        continue
                    if body.startswith("-"):
                        old_actual += 1
                        deletions += 1
                    elif body.startswith("+"):
                        new_actual += 1
                        insertions += 1
                    elif body.startswith(" ") or body == "":
                        old_actual += 1
                        new_actual += 1
                    idx += 1
                self.assertEqual(old_actual, old_expected, msg=f"{name}: old hunk count mismatch")
                self.assertEqual(new_actual, new_expected, msg=f"{name}: new hunk count mismatch")

            self.assertTrue(saw_hunk, msg=f"{name}: no hunks")
            self.assertGreater(files_changed, 0, msg=f"{name}: no files")

            summary = re.search(
                r"^ (\d+) files? changed(?:, (\d+) insertions?\(\+\))?"
                r"(?:, (\d+) deletions?\(-\))?$",
                text,
                re.MULTILINE,
            )
            self.assertIsNotNone(summary, msg=f"{name}: missing diffstat summary")
            assert summary is not None
            self.assertEqual(int(summary.group(1)), files_changed, msg=f"{name}: file count drift")
            self.assertEqual(int(summary.group(2) or 0), insertions, msg=f"{name}: insertion drift")
            self.assertEqual(int(summary.group(3) or 0), deletions, msg=f"{name}: deletion drift")

            for path, (plus, minus) in stat_files.items():
                self.assertGreater(plus + minus, 0, msg=f"{name}: empty diffstat row for {path}")

    def test_patches_have_metadata(self) -> None:
        for name in self.series():
            text = read(REPO_ROOT / "patches" / name)
            self.assertRegex(text, r"(?m)^From [0-9a-f]{40} Mon Sep 17 00:00:00 2001$")
            self.assertIn("Subject: [PATCH]", text)
            self.assertIn("\n---\n", text, msg=f"{name}: missing diffstat separator")


class TestWindowsLaunchers(unittest.TestCase):
    """Windows users must never hit BOM or ExecutionPolicy failures."""

    BAT = REPO_ROOT / "scripts" / "install-windows.bat"
    PS1 = REPO_ROOT / "scripts" / "install-windows.ps1"

    def test_launcher_bypasses_execution_policy(self) -> None:
        raw = self.BAT.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "install-windows.bat must not have a BOM")
        text = raw.decode("utf-8")
        self.assertIn(
            'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-windows.ps1" %*',
            text,
        )
        self.assertIn("\r\n", text, "launchers must use CRLF so cmd.exe parses them correctly")

    def test_powershell_is_bom_free_utf8(self) -> None:
        raw = self.PS1.read_bytes()
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"), "install-windows.ps1 must not have a BOM")
        self.assertNotIn(b"\x00", raw, "install-windows.ps1 must be UTF-8, not UTF-16")
        text = raw.decode("utf-8")
        self.assertIn("New-Object System.Text.UTF8Encoding($false)", text)
        self.assertIn("[System.IO.File]::WriteAllText", text)
        self.assertNotIn("Set-Content -Encoding UTF8", text, "Set-Content UTF8 writes a BOM on PS 5.1")

    def test_powershell_handles_profiles_ini_uac_and_unblock(self) -> None:
        text = self.PS1.read_text(encoding="utf-8")
        self.assertIn("Unblock-File", text)
        self.assertIn("Start-Process", text)
        self.assertIn("-Verb RunAs", text)
        self.assertIn('profiles.ini', text)
        self.assertIn('"Install*"', text)
        self.assertIn("sheepfox-backup-", text)
        for switch in ("$System", "$Strict", "$Uninstall", "$DryRun", "$ProfilePath", "$FirefoxDir"):
            self.assertIn(switch, text)

    def test_stray_arguments_get_actionable_guidance(self) -> None:
        # A '::' comment copied from cmd.exe docs must not produce a cryptic
        # "positional parameter cannot be found" binding error.
        text = self.PS1.read_text(encoding="utf-8")
        self.assertIn("ValueFromRemainingArguments", text)
        self.assertIn("Unexpected arguments", text)
        self.assertIn("cmd.exe-only", text)
        self.assertIn("exit 2", text)

    def test_launcher_argument_passthrough(self) -> None:
        text = self.BAT.read_text(encoding="utf-8")
        self.assertIn("%*", text)
        self.assertIn("exit /b", text.lower())


class TestPowerShellSyntax(unittest.TestCase):
    """install-windows.ps1 must be valid PowerShell before it ever runs.

    A single backslash-escaped quote (`\"`) inside a double-quoted string is a
    hard parser error in PowerShell ("The '<' operator is reserved for future
    use") and it takes the whole script down, so the installer never runs at all.
    PowerShell escapes with a backtick, never a backslash.
    """

    PS1 = REPO_ROOT / "scripts" / "install-windows.ps1"

    @staticmethod
    def _backslash_quotes(text: str) -> list[tuple[int, str]]:
        return [
            (number, line.strip())
            for number, line in enumerate(text.splitlines(), start=1)
            if '\\"' in line
        ]

    def test_no_backslash_escaped_quotes(self) -> None:
        self.assertEqual(
            self._backslash_quotes(self.PS1.read_text(encoding="utf-8")),
            [],
            msg="PowerShell escapes quotes with a backtick; backslash-escaped quotes are a parse error",
        )

    def test_detector_catches_the_reported_bug(self) -> None:
        # The exact line that broke the installer on Windows.
        historical = (
            '    Write-SheepFox "    .\\scripts\\install-windows.bat '
            '-ProfilePath \\"<that path>\\""'
        )
        self.assertEqual(len(self._backslash_quotes(historical)), 1)
        self.assertEqual(self._backslash_quotes(self.PS1.read_text(encoding="utf-8")), [])

    def test_quotes_balance_on_every_line(self) -> None:
        for number, problem in self._scan(self.PS1.read_text(encoding="utf-8")):
            self.fail(f"line {number}: {problem}")

    @staticmethod
    def _scan(text: str) -> list[tuple[int, str]]:
        """Tiny PowerShell lexer: unterminated strings, comments, here-strings."""
        problems: list[tuple[int, str]] = []
        here_terminator: str | None = None
        in_block_comment = False
        for number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if here_terminator is not None:
                if stripped == here_terminator:
                    here_terminator = None
                continue
            if in_block_comment:
                if "#>" in stripped:
                    in_block_comment = False
                continue
            if stripped.startswith("<#"):  # comment-based help
                if "#>" not in stripped[2:]:
                    in_block_comment = True
                continue
            if stripped.endswith('@"') or stripped.endswith("@'"):
                here_terminator = '"@' if stripped.endswith('@"') else "'@"
                continue

            state = None  # None | "squote" | "dquote"
            index = 0
            while index < len(line):
                char = line[index]
                if state is None:
                    if char == "#":
                        break
                    if char == "`":
                        index += 2
                        continue
                    if char == "'":
                        state = "squote"
                    elif char == '"':
                        state = "dquote"
                elif state == "squote":
                    if char == "'":
                        if line[index : index + 2] == "''":
                            index += 2
                            continue
                        state = None
                else:
                    if char == "`":
                        index += 2
                        continue
                    if char == '"':
                        state = None
                index += 1
            if state is not None:
                problems.append((number, f"unterminated {state} string: {line.strip()}"))
        return problems

    def test_parses_with_tree_sitter_when_available(self) -> None:
        """A real parse, when the optional grammar is installed."""
        try:
            from tree_sitter import Language, Parser
            import tree_sitter_powershell
        except ImportError:  # pragma: no cover - optional dev dependency
            self.skipTest("tree-sitter-powershell not installed (pip install -r requirements-dev.txt)")

        parser = Parser(Language(tree_sitter_powershell.language()))
        source = self.PS1.read_bytes()
        tree = parser.parse(source)
        failures = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            if node.type == "ERROR" or node.is_missing:
                snippet = source[node.start_byte : node.end_byte][:60]
                failures.append(
                    f"line {node.start_point.row + 1}, col {node.start_point.column + 1}: {snippet!r}"
                )
            stack.extend(node.children)
        self.assertEqual(failures, [], msg="install-windows.ps1 does not parse: " + "; ".join(failures))


class TestInstallers(unittest.TestCase):
    def test_install_strict_system_and_uninstall(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            profile = tmp_path / "profile.default-release"
            firefox = tmp_path / "firefox"
            profile.mkdir()
            firefox.mkdir()
            (profile / "user.js").write_text("// previous config\n", encoding="utf-8")

            install = subprocess.run(
                [
                    sys.executable,
                    str(installer),
                    "--profile",
                    str(profile),
                    "--firefox-dir",
                    str(firefox),
                    "--system",
                    "--strict",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, msg=install.stderr or install.stdout)

            user_js = (profile / "user.js").read_text(encoding="utf-8")
            self.assertIn('user_pref("gfx.webrender.all", true);', user_js)
            self.assertIn('user_pref("privacy.resistFingerprinting", true);', user_js)
            self.assertIn('user_pref("browser.ml.enable", false);', user_js)

            backups = list(profile.glob("user.js.sheepfox-backup-*"))
            self.assertEqual(len(backups), 1, "existing user.js must be backed up exactly once")
            self.assertIn("previous config", backups[0].read_text(encoding="utf-8"))

            ui = profile / "chrome" / "userChrome.css"
            self.assertTrue(ui.is_file(), msg="floating search UI was not installed")
            self.assertIn('#urlbar[pageproxystate="invalid"]', ui.read_text(encoding="utf-8"))
            self.assertTrue((profile / "chrome" / "userContent.css").is_file())
            self.assertFalse(ui.read_bytes().startswith(b"\xef\xbb\xbf"))

            cfg = (firefox / "sheepfox.cfg").read_text(encoding="utf-8")
            self.assertTrue(cfg.startswith("//"))
            self.assertIn("lockPref(", cfg)
            self.assertIn("defaultPref(", cfg)
            self.assertTrue((firefox / "defaults" / "pref" / "local-settings.js").is_file())
            self.assertTrue((firefox / "distribution" / "policies.json").is_file())

            for path in (profile / "user.js", firefox / "sheepfox.cfg"):
                self.assertFalse(
                    path.read_bytes().startswith(b"\xef\xbb\xbf"), msg=f"BOM written to {path}"
                )

            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(installer),
                    "--profile",
                    str(profile),
                    "--firefox-dir",
                    str(firefox),
                    "--system",
                    "--uninstall",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(uninstall.returncode, 0, msg=uninstall.stderr or uninstall.stdout)
            self.assertFalse((profile / "user.js").exists())
            self.assertFalse((profile / "chrome" / "userChrome.css").exists())
            self.assertFalse((profile / "chrome" / "userContent.css").exists())
            self.assertFalse((firefox / "sheepfox.cfg").exists())
            self.assertFalse((firefox / "distribution" / "policies.json").exists())
            self.assertEqual(len(list(profile.glob("user.js.sheepfox-backup-*"))), 1)

    def test_dry_run_never_writes(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            profile = tmp_path / "profile"
            firefox = tmp_path / "firefox"
            profile.mkdir()
            firefox.mkdir()

            result = subprocess.run(
                [
                    sys.executable,
                    str(installer),
                    "--profile",
                    str(profile),
                    "--firefox-dir",
                    str(firefox),
                    "--system",
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertFalse((profile / "user.js").exists())
            self.assertFalse((profile / "chrome" / "userChrome.css").exists())
            self.assertFalse((profile / "chrome" / "userContent.css").exists())
            self.assertFalse((firefox / "sheepfox.cfg").exists())
            self.assertEqual(list(profile.iterdir()), [])

    def test_low_memory_flag_appends_override(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--low-memory"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            user_js = (profile / "user.js").read_text(encoding="utf-8")
            self.assertIn('user_pref("fission.autostart", false);', user_js)
            self.assertIn('user_pref("dom.ipc.processCount", 2);', user_js)

        ps1 = (REPO_ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$LowMemory", ps1)
        self.assertIn("low-memory.override.js", ps1)

    def test_no_ui_flag_skips_chrome_css(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--no-ui"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue((profile / "user.js").is_file())
            self.assertFalse((profile / "chrome").exists())

    def test_doctor_passes_on_a_good_install(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile)],
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertIn("doctor", result.stdout)
            self.assertIn("[OK  ] chrome/userChrome.css", result.stdout)
            self.assertNotIn("FAIL", result.stdout)

    def test_doctor_does_not_fail_on_a_profile_only_install(self) -> None:
        """A stock Firefox folder has no sheepfox.cfg/policies.json - not a problem."""
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            firefox_dir = Path(tmp) / "firefox"
            firefox_dir.mkdir()
            subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile)],
                capture_output=True,
                check=True,
            )
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--firefox-dir", str(firefox_dir), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertNotIn("[FAIL]", result.stdout)
            self.assertIn("no system install here", result.stdout)

    def test_doctor_fails_on_a_bare_profile(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout)
            self.assertIn("[FAIL] user.js present", result.stdout)
            self.assertIn("[FAIL] chrome/userChrome.css", result.stdout)

    def test_windows_doctor_switch_is_wired(self) -> None:
        text = (REPO_ROOT / "scripts" / "install-windows.ps1").read_text(encoding="utf-8")
        self.assertIn("[switch]$Doctor", text)
        self.assertIn("Report-Check", text)
        self.assertIn("prefs.js", text)

    def test_installer_writes_to_every_profile(self) -> None:
        """No --profile: every profile on the machine gets the theme.

        Installing into only the detected profile is the classic reason a
        userChrome theme appears to do nothing (Store build, second profile).
        """
        installer = REPO_ROOT / "scripts" / "install.py"
        if sys.platform == "win32":  # pragma: no cover - profile roots differ
            self.skipTest("profile root probing is POSIX-specific here")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            firefox = home / ".mozilla" / "firefox"
            for name in ("aaa.default-release", "bbb.work"):
                (firefox / "Profiles" / name).mkdir(parents=True)
            (firefox / "profiles.ini").write_text(
                "[Profile1]\nName=default-release\nIsRelative=1\n"
                "Path=Profiles/aaa.default-release\nDefault=1\n\n"
                "[Profile0]\nName=work\nIsRelative=1\nPath=Profiles/bbb.work\n",
                encoding="utf-8",
            )
            (firefox / "installs.ini").write_text(
                "[Install4F96D1932A9F858E]\nDefault=Profiles/bbb.work\nLocked=1\n",
                encoding="utf-8",
            )
            env = dict(os.environ, HOME=str(home))
            result = subprocess.run(
                [sys.executable, str(installer)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            for name in ("aaa.default-release", "bbb.work"):
                profile = firefox / "Profiles" / name
                self.assertTrue((profile / "user.js").is_file(), msg=f"no user.js in {name}")
                self.assertTrue(
                    (profile / "chrome" / "userChrome.css").is_file(),
                    msg=f"floating UI skipped for {name}",
                )
            # installs.ini wins: the profile Firefox actually opens goes first.
            self.assertLess(
                result.stdout.index("bbb.work"),
                result.stdout.index("aaa.default-release"),
                msg="installs.ini order must win: that is the profile Firefox opens",
            )

    def test_report_writes_a_file(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile)],
                capture_output=True,
                check=True,
            )
            report = Path(tmp) / "report.txt"
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--report", str(report)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertTrue(report.is_file(), msg=result.stdout + result.stderr)
            text = report.read_text(encoding="utf-8")
            self.assertIn("doctor", text)
            self.assertIn("profiles found", text)
            self.assertIn("exit_code=", text)

    def test_probe_round_trip(self) -> None:
        """--probe must produce a file the stylesheet imports, and --unprobe clears it."""
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile)],
                capture_output=True,
                check=True,
            )
            probe = profile / "chrome" / "sheepfox-probe.css"
            self.assertFalse(probe.exists(), "the probe must not ship by default")

            add = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--probe"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(add.returncode, 0, msg=add.stderr)
            self.assertTrue(probe.is_file())
            text = probe.read_text(encoding="utf-8")
            self.assertIn("#cc0000", text)
            self.assertFalse(probe.read_bytes().startswith(b"\xef\xbb\xbf"))

            remove = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--unprobe"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(remove.returncode, 0, msg=remove.stderr)
            self.assertFalse(probe.exists())

    def test_doctor_flags_a_stale_stylesheet(self) -> None:
        installer = REPO_ROOT / "scripts" / "install.py"
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "profile"
            profile.mkdir()
            subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile)],
                capture_output=True,
                check=True,
            )
            (profile / "chrome" / "userChrome.css").write_text(
                "/* an old copy */\n#urlbar[pageproxystate=\"invalid\"] { position: fixed; }\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(installer), "--profile", str(profile), "--doctor"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1, msg=result.stdout)
            self.assertIn("stale", result.stdout)

    def test_unix_wrapper_delegates_to_python(self) -> None:
        wrapper = read(REPO_ROOT / "scripts" / "install-unix.sh")
        self.assertIn("install.py", wrapper)
        self.assertIn("set -euo pipefail", wrapper)


class TestForkBuildScaffold(unittest.TestCase):
    def test_version_manifest(self) -> None:
        manifest = json.loads(read(REPO_ROOT / "mozbuild" / "firefox-version.json"))
        self.assertRegex(manifest["version"], r"^\d+\.\d+$")
        self.assertEqual(
            manifest["tag"],
            "FIREFOX_" + manifest["version"].replace(".", "_") + "_RELEASE",
        )
        for key in ("source_url_template", "sha512sums_url_template"):
            self.assertIn("{version}", manifest[key])
            self.assertIn("archive.mozilla.org", manifest[key])
        self.assertTrue(manifest["source_url_template"].endswith(".source.tar.xz"))
        self.assertGreaterEqual(manifest["min_free_disk_gb"], 20)
        self.assertIn("source_sha512", manifest)

    def test_mozconfigs_are_consistent_and_valid(self) -> None:
        common = read(REPO_ROOT / "mozbuild" / "mozconfig.common")
        for flag in (
            "--enable-release",
            "--enable-hardening",
            "--enable-rust-simd",
            "--disable-crashreporter",
            "--disable-updater",
            "--disable-default-browser-agent",
        ):
            self.assertIn(flag, common, msg=f"mozconfig.common must set {flag}")
        self.assertIn("MOZ_TELEMETRY_REPORTING=0", common)
        self.assertIn("--with-branding=browser/branding/sheepfox", common)

        platform_flags = {
            "mozconfig.linux-x86_64": ["x86-64-v3", "--enable-lto=cross", "--enable-linker=lld"],
            "mozconfig.linux-aarch64": ["--enable-lto=full", "--enable-linker=lld"],
            "mozconfig.windows-x86_64": ["x86-64-v3", "--enable-lto=cross"],
            "mozconfig.macos-universal": ["--target=", "--enable-lto=full"],
        }
        for name, flags in platform_flags.items():
            text = read(REPO_ROOT / "mozbuild" / name)
            self.assertIn("mozconfig.common", text, msg=f"{name} must source the shared config")
            for flag in flags:
                self.assertIn(flag, text, msg=f"{name} must contain {flag}")
            self.assertIn("SHEEPFOX_PGO", text, msg=f"{name} must support optional PGO")

        # Firefox 159 has no --enable-jxl switch; passing it aborts configure.
        for path in (REPO_ROOT / "mozbuild").glob("mozconfig.*"):
            self.assertNotIn("--enable-jxl", read(path))

    def test_build_scripts_exist_and_are_executable(self) -> None:
        for name in ("fetch-source.sh", "apply-patches.sh", "build-browser.sh"):
            path = REPO_ROOT / "mozbuild" / "scripts" / name
            self.assertTrue(path.is_file(), msg=f"missing {name}")
            self.assertTrue(os.access(path, os.X_OK), msg=f"{name} must be executable")
        fetch = read(REPO_ROOT / "mozbuild" / "scripts" / "fetch-source.sh")
        self.assertIn("sha512", fetch.lower())
        self.assertIn("SHA512SUMS", fetch)
        apply_script = read(REPO_ROOT / "mozbuild" / "scripts" / "apply-patches.sh")
        self.assertIn("build-configs.py", apply_script)
        self.assertIn("branding/sheepfox", apply_script)
        build_script = read(REPO_ROOT / "mozbuild" / "scripts" / "build-browser.sh")
        for step_name in ("./mach", "configure", "build", "package"):
            self.assertIn(step_name, build_script)

    def test_shell_scripts_are_syntactically_valid(self) -> None:
        bash = shutil.which("bash")
        if bash is None:  # pragma: no cover - Windows CI
            self.skipTest("bash not available")
        scripts = sorted(REPO_ROOT.glob("scripts/*.sh")) + sorted(
            REPO_ROOT.glob("mozbuild/scripts/*.sh")
        )
        self.assertGreaterEqual(len(scripts), 4)
        for script in scripts:
            result = subprocess.run(
                [bash, "-n", str(script)], capture_output=True, text=True, check=False
            )
            self.assertEqual(result.returncode, 0, msg=f"{script.name}: {result.stderr}")


class TestRepositoryHygiene(unittest.TestCase):
    def test_license_is_mpl_2_0(self) -> None:
        license_text = read(REPO_ROOT / "LICENSE")
        self.assertIn("Mozilla Public License Version 2.0", license_text)
        self.assertIn("Exhibit A - Source Code Form License Notice", license_text)
        self.assertIn("Exhibit B - \"Incompatible With Secondary Licenses\" Notice", license_text)

    def test_required_top_level_files(self) -> None:
        for name in (
            "README.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "LICENSE",
            "Makefile",
            ".editorconfig",
            ".gitignore",
        ):
            self.assertTrue((REPO_ROOT / name).is_file(), msg=f"missing {name}")

    def test_makefile_targets(self) -> None:
        makefile = read(REPO_ROOT / "Makefile")
        for target in (
            "build-configs:",
            "check:",
            "test:",
            "install:",
            "fetch-source:",
            "patch-source:",
            "build-browser:",
        ):
            self.assertIn(target, makefile, msg=f"missing make target {target}")
        self.assertNotRegex(
            makefile, r"(?<!moz)build/scripts", "Makefile must reference mozbuild/, never build/"
        )
        self.assertIn("mozbuild/scripts/build-configs.py", makefile)

    def test_readme_documents_both_modes_and_targets(self) -> None:
        readme = read(REPO_ROOT / "README.md")
        self.assertIn("(SheepFox) Zen browser", readme)
        self.assertIn("mozbuild/", readme)
        self.assertNotIn("├── build/", readme)
        for section in ("Windows", "Linux", "macOS", "MPL-2.0"):
            self.assertIn(section, readme)
        for target in ("linux-x86_64", "linux-aarch64", "windows-x86_64", "macos-universal"):
            self.assertIn(target, readme)

    def test_workflows(self) -> None:
        workflows = REPO_ROOT / ".github" / "workflows"
        validate = workflows / "validate-configs.yml"
        build = workflows / "build-sheepfox.yml"
        self.assertTrue(validate.is_file())
        self.assertTrue(build.is_file())

        validate_text = read(validate)
        self.assertIn("build-configs.py --check", validate_text)
        self.assertIn("bash -n", validate_text)
        self.assertIn("unittest", validate_text)

        build_text = read(build)
        self.assertIn("upload-artifact", build_text)
        self.assertIn("build-configs.py", build_text)
        self.assertIn("ubuntu", build_text)

    def test_generated_artifacts_are_ignored(self) -> None:
        ignore = read(REPO_ROOT / ".gitignore")
        for pattern in ("__pycache__/", "mozbuild/firefox-src/", "mozbuild/staging/", "*.py[cod]"):
            self.assertIn(pattern, ignore, msg=f".gitignore must ignore {pattern}")

        git = shutil.which("git")
        if git is None:  # pragma: no cover - no git in some sandboxes
            self.skipTest("git not available")
        tracked = subprocess.run(
            [git, "-C", str(REPO_ROOT), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
        if tracked.returncode != 0:  # pragma: no cover
            self.skipTest("not a git checkout")
        for name in tracked.stdout.splitlines():
            self.assertFalse(name.endswith((".pyc", ".profraw")), msg=f"artifact tracked: {name}")
            self.assertNotIn("firefox-src/", name)
            self.assertNotIn("__pycache__", name)


class TestDistributableInstallerArtifacts(unittest.TestCase):
    """The .exe / .dmg pipeline: one source of config, two packaging formats."""

    INSTALLER_DIR = REPO_ROOT / "installer"
    BUILD_SCRIPT = REPO_ROOT / "mozbuild" / "scripts" / "build-installers.py"
    DIST_DIR = REPO_ROOT / "dist"

    def test_version_manifest(self) -> None:
        version = (self.INSTALLER_DIR / "version.txt").read_text(encoding="utf-8").strip()
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")

    def test_build_script_contract(self) -> None:
        self.assertTrue(self.BUILD_SCRIPT.is_file())
        text = read(self.BUILD_SCRIPT)
        for switch in ("--windows", "--macos", "--zig"):
            self.assertIn(switch, text)
        # The payload must come from the repository, never from a copy.
        self.assertIn("PAYLOAD_FILES", text)
        self.assertIn('"config/user.js"', text)
        self.assertIn('"config/chrome/userChrome.css"', text)
        self.assertNotIn("shutil.copytree(REPO_ROOT / \"config\"", text)

    def test_every_config_file_is_in_the_payload(self) -> None:
        text = read(self.BUILD_SCRIPT)
        listed = set(re.findall(r'"(config/[^"]+)"', text))
        on_disk = {
            path.relative_to(REPO_ROOT).as_posix()
            for path in (REPO_ROOT / "config").rglob("*")
            if path.is_file()
        }
        missing = on_disk - listed
        self.assertFalse(missing, msg=f"not shipped by the installers: {sorted(missing)}")

    def test_windows_launcher_source(self) -> None:
        source = read(self.INSTALLER_DIR / "windows" / "launcher.c")
        self.assertIn("Expand-Archive", source)
        self.assertIn("install-windows.ps1", source)
        self.assertIn("%TEMP%", source)
        self.assertIn("GetTempPathA", source)
        self.assertIn("/?", source)
        for banned in ("WinExec", "ShellExecute"):
            self.assertNotIn(banned, source, msg=f"launcher must stay console-only: {banned}")

    def test_macos_launcher_source(self) -> None:
        path = self.INSTALLER_DIR / "macos" / "Install SheepFox.command"
        self.assertTrue(path.is_file())
        text = read(path)
        self.assertTrue(text.startswith("#!/bin/bash\n"))
        self.assertIn("scripts/install-unix.sh", text)
        self.assertIn('"$@"', text, msg="switches must be forwarded unchanged")
        self.assertIn("set -euo pipefail", text)
        # A mounted read-only image can drop the execute bit, so never rely on it.
        self.assertIn("sh ./scripts/install-unix.sh", text)
        self.assertIn("if [ -t 0 ]", text, msg="must not block without a terminal")
        self.assertTrue(path.stat().st_mode & 0o111, msg="the .command must be executable")
        banner = read(self.INSTALLER_DIR / "macos" / "README.txt")
        for switch in ("--doctor", "--uninstall", "--strict", "--no-ui", "--low-memory"):
            self.assertIn(switch, banner)

    def test_readme_documents_the_installers(self) -> None:
        readme = read(REPO_ROOT / "README.md")
        for needle in (
            "SheepFox-Setup-<version>.exe",
            "SheepFox-<version>.dmg",
            "Install SheepFox.command",
            "make installers",
            "pip install ziglang pycdlib",
            "/releases/latest",
        ):
            self.assertIn(needle, readme, msg=f"README must document {needle}")
        makefile = read(REPO_ROOT / "Makefile")
        self.assertIn("build-installers.py --windows", makefile)
        self.assertIn("build-installers.py --macos", makefile)

    def test_warning_free_launcher_build(self) -> None:
        text = read(self.BUILD_SCRIPT)
        for flag in ('"-Wall"', '"-Wextra"', '"-Werror"'):
            self.assertIn(flag, text, msg=f"the .exe must be built with {flag}")
        self.assertIn("compiled with warnings", text)

    def test_release_workflow_builds_and_publishes(self) -> None:
        path = REPO_ROOT / ".github" / "workflows" / "release-installers.yml"
        self.assertTrue(path.is_file())
        text = read(path)
        self.assertIn("windows-latest", text)
        self.assertIn("macos-latest", text)
        self.assertIn("build-installers.py --windows", text)
        self.assertIn("build-installers.py --macos", text)
        self.assertIn("hdiutil", text)
        self.assertIn("SheepFox-Setup-*.exe", text)
        self.assertIn("SheepFox-*.dmg", text)
        self.assertIn("SheepFox-*.iso", text)

    def test_built_windows_executable(self) -> None:
        artifacts = sorted(self.DIST_DIR.glob("SheepFox-Setup-*.exe"))
        if not artifacts:
            self.skipTest("no .exe built in this checkout")
        data = artifacts[-1].read_bytes()
        self.assertEqual(data[:2], b"MZ")
        pe_offset = int.from_bytes(data[0x3C:0x40], "little")
        self.assertEqual(data[pe_offset:pe_offset + 4], b"PE\0\0")
        machine = int.from_bytes(data[pe_offset + 4:pe_offset + 6], "little")
        self.assertEqual(machine, 0x8664, msg="must be x86-64 Windows")
        optional = pe_offset + 24
        magic = int.from_bytes(data[optional:optional + 2], "little")
        self.assertEqual(magic, 0x20B, msg="PE32+ expected")
        subsystem = int.from_bytes(data[optional + 68:optional + 70], "little")
        self.assertEqual(subsystem, 3, msg="console subsystem so switches print to a terminal")
        # A real zip archive is embedded, and it carries the PowerShell installer.
        start = data.find(b"PK\x03\x04")
        self.assertGreater(start, 0, msg="payload zip not found in the executable")
        import io
        import zipfile

        payload = zipfile.ZipFile(io.BytesIO(data[start:]))
        self.assertIn("scripts/install-windows.ps1", payload.namelist())
        self.assertIn("config/user.js", payload.namelist())
        self.assertIn("config/modules/01-speedfox.js", payload.namelist())
        self.assertIn("scripts/install-windows.bat", payload.namelist())
        mode = payload.getinfo("scripts/install-windows.ps1")
        self.assertEqual(mode.create_system, 0)

    def test_built_dmg_is_a_valid_udif(self) -> None:
        artifacts = sorted(self.DIST_DIR.glob("SheepFox-*.dmg"))
        if not artifacts:
            self.skipTest("no .dmg built in this checkout")
        data = artifacts[-1].read_bytes()
        if "hdiutil" in read(self.BUILD_SCRIPT) and data[-512:-508] != b"koly":
            # A native hdiutil image (HFS+ UDZO) is fine as-is.
            self.assertGreater(len(data), 512)
            return
        trailer = data[-512:]
        self.assertEqual(trailer[:4], b"koly")
        self.assertEqual(int.from_bytes(trailer[4:8], "big"), 4)
        self.assertEqual(int.from_bytes(trailer[8:12], "big"), 512)
        data_offset = int.from_bytes(trailer[24:32], "big")
        data_length = int.from_bytes(trailer[32:40], "big")
        xml_offset = int.from_bytes(trailer[216:224], "big")
        xml_length = int.from_bytes(trailer[224:232], "big")
        self.assertEqual(data_offset, 0)
        self.assertEqual(xml_offset, data_length)
        self.assertEqual(xml_offset + xml_length + 512, len(data))
        self.assertEqual(
            int.from_bytes(trailer[492:500], "big"), (data_length + 511) // 512
        )
        import plistlib
        import zlib

        xml = data[xml_offset:xml_offset + xml_length]
        self.assertEqual(int.from_bytes(trailer[360:364], "big"), zlib.crc32(xml) & 0xFFFFFFFF)
        self.assertEqual(
            int.from_bytes(trailer[88:92], "big"),
            zlib.crc32(data[data_offset:data_offset + data_length]) & 0xFFFFFFFF,
        )
        resource_fork = plistlib.loads(xml)["resource-fork"]
        self.assertIn("blkx", resource_fork)
        mish = resource_fork["blkx"][0]["Data"]
        self.assertEqual(mish[:4], b"mish")
        self.assertEqual(int.from_bytes(mish[16:24], "big"), (data_length + 511) // 512)

    def test_built_iso_contains_the_installer(self) -> None:
        artifacts = sorted(self.DIST_DIR.glob("SheepFox-*.iso"))
        if not artifacts:
            self.skipTest("no .iso built in this checkout")
        data = artifacts[-1].read_bytes()
        self.assertEqual(data[0x8001:0x8006], b"CD001")
        self.assertIn(b"Install SheepFox.command", data)
        self.assertIn(b"install-unix.sh", data)


class TestZenBrowserSupport(unittest.TestCase):
    """First-class Zen Browser discovery, Workspaces safety, and UI isolation."""

    INSTALLER = REPO_ROOT / "scripts" / "install.py"
    CHROME = REPO_ROOT / "config" / "chrome" / "userChrome.css"
    PS1 = REPO_ROOT / "scripts" / "install-windows.ps1"

    def test_zen_preferences_and_workspace_containers(self) -> None:
        cfg = parse_prefs(read(CFG), ("lockPref", "defaultPref"))
        user = parse_prefs(read(USER_JS), ("user_pref",))
        self.assertIn("zen.urlbar.show-sponsored", cfg)
        self.assertIs(cfg["zen.urlbar.show-sponsored"][0], False)
        self.assertEqual(cfg["zen.urlbar.show-sponsored"][1], "lockPref")
        # Contextual Identities must stay enabled so Zen Browser Workspaces work.
        self.assertIs(user["privacy.userContext.enabled"][0], True)
        self.assertIs(user["privacy.userContext.ui.enabled"][0], True)

    def test_zen_browser_css_isolation(self) -> None:
        css = read(self.CHROME)
        self.assertIn(":root:not(:has(#zen-main-app-wrapper))", css)
        # Ancestor transform reset and pill shell must never match inside Zen Browser's
        # #zen-main-app-wrapper, preserving Zen Compact Mode & native floating URL bar.
        self.assertIn(
            ":root:not(:has(#zen-main-app-wrapper)) :is(#main-window,",
            css,
        )
        self.assertIn(
            ":root:not(:has(#zen-main-app-wrapper)) #urlbar:is(",
            css,
        )

    def test_zen_profile_autodetection_and_priority(self) -> None:
        if sys.platform == "win32":  # pragma: no cover
            self.skipTest("POSIX HOME layout test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            zen_prof = home / ".zen" / "Profiles" / "z123.Default (release)"
            ff_prof = home / ".mozilla" / "firefox" / "Profiles" / "f456.default-release"
            zen_prof.mkdir(parents=True)
            ff_prof.mkdir(parents=True)
            (home / ".zen" / "profiles.ini").write_text(
                "[Profile0]\nName=Default (release)\nIsRelative=1\n"
                "Path=Profiles/z123.Default (release)\n",
                encoding="utf-8",
            )
            (home / ".mozilla" / "firefox" / "profiles.ini").write_text(
                "[Profile0]\nName=default-release\nIsRelative=1\n"
                "Path=Profiles/f456.default-release\nDefault=1\n",
                encoding="utf-8",
            )
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"))

            # 1. --browser zen touches ONLY Zen Browser.
            only_zen = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--browser", "zen"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(only_zen.returncode, 0, msg=only_zen.stdout + only_zen.stderr)
            self.assertTrue((zen_prof / "user.js").is_file())
            self.assertFalse((ff_prof / "user.js").exists())

            # Clean up and verify --browser auto installs into BOTH with Zen first.
            (zen_prof / "user.js").unlink()
            both = subprocess.run(
                [sys.executable, str(self.INSTALLER)],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(both.returncode, 0, msg=both.stdout + both.stderr)
            self.assertTrue((zen_prof / "user.js").is_file())
            self.assertTrue((ff_prof / "user.js").is_file())
            self.assertLess(
                both.stdout.index("z123.Default (release)"),
                both.stdout.index("f456.default-release"),
                msg="Zen Browser profile must be prioritized ahead of stock Firefox",
            )

    def test_zen_xdg_and_flatpak_profile_roots(self) -> None:
        if sys.platform == "win32":  # pragma: no cover
            self.skipTest("POSIX XDG / Flatpak layout test")
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            xdg = Path(tmp) / "xdg"
            xdg_prof = xdg / "zen" / "Profiles" / "x1.Default Profile"
            flatpak_prof = (
                home / ".var" / "app" / "app.zen_browser.zen" / ".zen" / "Profiles" / "fp1.Default (release)"
            )
            xdg_prof.mkdir(parents=True)
            flatpak_prof.mkdir(parents=True)
            (xdg / "zen" / "profiles.ini").write_text(
                "[Profile0]\nName=Default Profile\nIsRelative=1\nPath=Profiles/x1.Default Profile\n",
                encoding="utf-8",
            )
            (home / ".var" / "app" / "app.zen_browser.zen" / ".zen" / "profiles.ini").write_text(
                "[Profile0]\nName=Default (release)\nIsRelative=1\nPath=Profiles/fp1.Default (release)\n",
                encoding="utf-8",
            )
            env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(xdg))
            result = subprocess.run(
                [sys.executable, str(self.INSTALLER), "--browser", "zen"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            self.assertTrue((xdg_prof / "user.js").is_file())
            self.assertTrue((flatpak_prof / "user.js").is_file())

    def test_zen_dir_alias_system_install_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "zen-profile"
            zen_dir = Path(tmp) / "zen-browser"
            profile.mkdir()
            zen_dir.mkdir()
            install = subprocess.run(
                [
                    sys.executable,
                    str(self.INSTALLER),
                    "--profile",
                    str(profile),
                    "--zen-dir",
                    str(zen_dir),
                    "--system",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(install.returncode, 0, msg=install.stdout + install.stderr)
            self.assertTrue((zen_dir / "sheepfox.cfg").is_file())
            self.assertTrue((zen_dir / "defaults" / "pref" / "local-settings.js").is_file())
            self.assertTrue((zen_dir / "distribution" / "policies.json").is_file())

            uninstall = subprocess.run(
                [
                    sys.executable,
                    str(self.INSTALLER),
                    "--profile",
                    str(profile),
                    "--zen-dir",
                    str(zen_dir),
                    "--system",
                    "--uninstall",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(uninstall.returncode, 0, msg=uninstall.stdout + uninstall.stderr)
            self.assertFalse((zen_dir / "sheepfox.cfg").exists())
            self.assertFalse((zen_dir / "distribution" / "policies.json").exists())

    def test_windows_installer_zen_browser_support(self) -> None:
        ps1 = read(self.PS1)
        for token in (
            '"ZenDir"',
            "[string]$Browser",
            '"Zen Browser"',
            "zen.exe",
            'Join-Path $env:APPDATA "zen"',
            "*.Default (release)",
            "*.Default Profile",
        ):
            self.assertIn(token, ps1, msg=f"install-windows.ps1 missing Zen token: {token}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
