// ============================================================================
// MODULE 02: SHIELDFOX — LibreFox-grade privacy + zero-breakage compatibility
// Goal: eliminate cross-site tracking, telemetry and network leaks in Zen
//       Browser (and Firefox) while preserving 120Hz+ displays, Zen Compact
//       Mode & Mica/vibrancy themes, hardware WebGL/Canvas, dark mode,
//       timezones, Workspaces and normal OAuth/SSO flows.
// Lines tagged `// @lock` are promoted to lockPref() in the AutoConfig and can
// only be changed by editing this module — they are reserved for things that
// transmit data to remote servers.
// ============================================================================

// --- Total Cookie Protection (dFPI) & State Partitioning ---
user_pref("browser.contentblocking.category", "custom");
// 5 = dynamic first-party isolation: every third-party cookie/storage is
// partitioned by top-level site (SSO and normal logins keep working)
user_pref("network.cookie.cookieBehavior", 5);
user_pref("privacy.partition.network_state", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);
user_pref("privacy.trackingprotection.cryptomining.enabled", true);
user_pref("privacy.trackingprotection.emailtracking.enabled", true);
// Keep Contextual Identities enabled so Zen Browser Workspaces & Containers work
user_pref("privacy.userContext.enabled", true);
user_pref("privacy.userContext.ui.enabled", true);

// --- Balanced Anti-Fingerprinting (preserves 120Hz+, dark mode & WebGL) ---
// Strict RFP stays OFF: it caps the refresh rate at 60Hz, forces light mode,
// spoofs the timezone to UTC and adds Canvas noise that breaks real apps.
user_pref("privacy.resistFingerprinting", false);
// Granular Firefox Fingerprinting Protection instead (per-category, per-site
// exemptible, and it leaves display refresh rate and timezone intact)
user_pref("privacy.fingerprintingProtection", true);
// Apply the same granular protection inside private browsing windows
user_pref("privacy.fingerprintingProtection.pbmode", true);
// Broadcast Global Privacy Control (Sec-GPC: 1) and expose the JS API
user_pref("privacy.globalprivacycontrol.enabled", true);
user_pref("privacy.globalprivacycontrol.functionality.enabled", true);

// --- URL Tracking-Parameter Stripping (Brave query-filter parity) ---
user_pref("privacy.query_stripping.enabled", true);
user_pref("privacy.query_stripping.enabled.pbmode", true);

// --- Prevent Unsolicited Speculative & Analytics Network Leaks ---
user_pref("network.prefetch-next", false);
user_pref("network.dns.disablePrefetch", true);
user_pref("network.dns.disablePrefetchFromHTTPS", true);
user_pref("network.predictor.enabled", false);
user_pref("network.http.speculative-parallel-limit", 0);
user_pref("browser.urlbar.speculativeConnect.enabled", false);
user_pref("beacon.enabled", false);
user_pref("browser.send_pings", false);

// --- HTTPS-Only, CRLite Local Revocation & Encrypted DNS (DoH) ---
user_pref("dom.security.https_only_mode", true);
user_pref("dom.security.https_only_mode_send_http_background_request", false);
user_pref("security.ssl.require_safe_negotiation", true);
user_pref("security.tls.enable_0rtt_data", false);
// Replace live OCSP lookups (slow, and they leak every visited domain) with
// Mozilla's local CRLite binary filters
user_pref("security.OCSP.enabled", 0);
user_pref("security.remote_settings.crlite_filters.enabled", true);
user_pref("security.pki.crlite_mode", 2);
// Mode 2 = prefer encrypted DNS-over-HTTPS through Quad9, with graceful
// fallback so captive portals and LAN-only devices keep working
user_pref("network.trr.mode", 2);
user_pref("network.trr.uri", "https://dns.quad9.net/dns-query");

// --- Referer Trimming & WebRTC LAN IP Leak Protection ---
user_pref("network.http.referer.XOriginTrimmingPolicy", 2);
// Only expose ICE candidates for the default route, never the LAN address
user_pref("media.peerconnection.ice.default_address_only", true);
user_pref("media.peerconnection.ice.no_host", false);

// --- Zero Telemetry, Studies, Crash Uploads & Ad Attribution ---
// These are the only preferences SheepFox locks in the AutoConfig.
user_pref("datareporting.policy.dataSubmissionEnabled", false); // @lock
user_pref("datareporting.healthreport.uploadEnabled", false); // @lock
user_pref("datareporting.usage.uploadEnabled", false); // @lock
user_pref("toolkit.telemetry.unified", false); // @lock
user_pref("toolkit.telemetry.enabled", false); // @lock
user_pref("toolkit.telemetry.server", "data:,"); // @lock
user_pref("toolkit.telemetry.archive.enabled", false); // @lock
user_pref("toolkit.telemetry.newProfilePing.enabled", false); // @lock
user_pref("toolkit.telemetry.shutdownPingSender.enabled", false); // @lock
user_pref("toolkit.telemetry.updatePing.enabled", false); // @lock
user_pref("toolkit.telemetry.bhrPing.enabled", false); // @lock
user_pref("toolkit.telemetry.firstShutdownPing.enabled", false); // @lock
user_pref("toolkit.coverage.opt-out", true); // @lock
user_pref("toolkit.coverage.endpoint.base", ""); // @lock
user_pref("app.shield.optoutstudies.enabled", false); // @lock
user_pref("app.normandy.enabled", false); // @lock
user_pref("app.normandy.api_url", ""); // @lock
user_pref("breakpad.reportURL", ""); // @lock
user_pref("browser.tabs.crashReporting.sendReport", false); // @lock
user_pref("dom.private-attribution.submission.enabled", false); // @lock

// --- Background Connectivity Pings (disabled, but not locked) ---
user_pref("captivedetect.canonicalURL", "");
user_pref("network.captive-portal-service.enabled", false);
user_pref("network.connectivity-service.enabled", false);
// Keep local Safe Browsing lists active, drop remote binary hash uploads
user_pref("browser.safebrowsing.downloads.remote.enabled", false);
