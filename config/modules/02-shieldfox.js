// ============================================================================
// MODULE 02: SHIELDFOX — LibreFox Privacy + Zero-Breakage Site Compatibility
// Goal: Eliminate telemetry, cross-site tracking & leaks while preserving
//       120Hz+ displays, WebGL, dark mode, and modern web app compatibility.
// ============================================================================

// --- Total Cookie Protection (dFPI) & State Partitioning ---
user_pref("browser.contentblocking.category", "custom");
// Behavior 5 = Dynamic First-Party Isolation (isolates storage per top-level site without breaking SSO)
user_pref("network.cookie.cookieBehavior", 5);
user_pref("privacy.partition.network_state", true);
user_pref("privacy.partition.serviceWorkers", true);
user_pref("privacy.partition.always_partition_third_party_non_cookie_storage", true);
user_pref("privacy.trackingprotection.enabled", true);
user_pref("privacy.trackingprotection.socialtracking.enabled", true);
user_pref("privacy.trackingprotection.cryptomining.enabled", true);
user_pref("privacy.trackingprotection.fingerprinting.enabled", true);

// --- Balanced Anti-Fingerprinting (Preserves 120Hz+, Dark Mode & WebGL) ---
// Strict RFP is off by default so refresh rates, Canvas/WebGL apps, and timezones never break
user_pref("privacy.resistFingerprinting", false);
// Enable modern granular Fingerprinting Protection (FPP) instead
user_pref("privacy.fingerprintingProtection", true);
// Broadcast Global Privacy Control (Sec-GPC: 1) header like Brave Shields
user_pref("privacy.globalprivacycontrol.enabled", true);

// --- URL Tracking Parameter Stripping (Brave Query Filter Parity) ---
user_pref("privacy.query_stripping.enabled", true);
user_pref("privacy.query_stripping.enabled.pbmode", true);

// --- Prevent Unsolicited Speculative & Analytics Network Leaks ---
user_pref("network.prefetch-next", false);
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
// Replace live OCSP lookups (slow + leaks visited domains) with local Mozilla CRLite filters
user_pref("security.OCSP.enabled", 0);
user_pref("security.remote_settings.crlite_filters.enabled", true);
user_pref("security.pki.crlite_mode", 2);
// Mode 2 = Prefer Encrypted DNS-over-HTTPS (Quad9) with graceful fallback for captive portals/LAN
user_pref("network.trr.mode", 2);
user_pref("network.trr.uri", "https://dns.quad9.net/dns-query");

// --- Cross-Origin Referer & WebRTC IP Leak Protection ---
user_pref("network.http.referer.XOriginTrimmingPolicy", 2);
user_pref("media.peerconnection.ice.default_address_only", true);
user_pref("media.peerconnection.ice.no_host", false);

// --- Zero Telemetry, Studies, Crash Uploads & Ad Attribution (@lock in AutoConfig) ---
user_pref("datareporting.policy.dataSubmissionEnabled", false); // @lock
user_pref("datareporting.healthreport.uploadEnabled", false); // @lock
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
user_pref("captivedetect.canonicalURL", "");
user_pref("network.captive-portal-service.enabled", false);
user_pref("network.connectivity-service.enabled", false);
// Keep local SafeBrowsing lists active, but disable remote binary hash uploads to Google
user_pref("browser.safebrowsing.downloads.remote.enabled", false);
