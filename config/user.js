// ============================================================================
// (SheepFox) Firefox — Unified Profile Configuration (config/user.js)
// Brave-class Gecko speed + LibreFox-grade privacy, with zero site breakage.
// License: Mozilla Public License 2.0 (MPL-2.0)
//
// AUTO-GENERATED FILE — DO NOT EDIT BY HAND.
// Edit config/modules/*.js and run:  make build-configs
// Modules: 01-speedfox.js, 02-shieldfox.js, 03-cleanfox.js, 04-smoothfox.js
// Preferences: 132 (27 locked in the system AutoConfig)
//
// `// @lock` annotations are inert here: they only promote a preference to
// lockPref() inside config/autoconfig/sheepfox.cfg.
// ============================================================================


// ---------------------------------------------------------------------------
// Source module: config/modules/01-speedfox.js
// ---------------------------------------------------------------------------
// ============================================================================
// MODULE 01: SPEEDFOX — Gecko GPU, Cache & Network Acceleration
// Goal: Brave-class page-load responsiveness without sacrificing stability.
// Every value here is a supported Gecko/WebRender/Necko knob. Nothing forces
// an unsupported GPU path, keeps the GPU crash-isolation process, and nothing
// disables JavaScript JIT or WebGL.
// ============================================================================

// --- Rendering & Content Layout Pipeline ---
// Paint as soon as there is something to paint. The Gecko default is already 0;
// the old 5 ms here delayed first paint (and the "avoids a flash of unstyled
// content" note was wrong - that delay only ever throttled paints).
user_pref("nglayout.initialpaint.delay", 0);

// --- WebRender, GPU Compositing & Skia Acceleration ---
// Enable the full GPU-driven WebRender pipeline and pre-cache shaders so the
// first scroll and the first animation never hitch
user_pref("gfx.webrender.all", true);
user_pref("gfx.webrender.precache-shaders", true);
user_pref("gfx.webrender.compositor", true);
// Hardware-accelerated 2D Canvas. The cache is capped at 128 MB (Firefox's own
// default is 256 MB) because this profile is meant to use less RAM, not more:
// 512 MB of canvas surfaces is a second browser's worth of memory on a 4 GB
// machine. Canvas-heavy apps (Figma, Maps) still fit comfortably.
user_pref("gfx.canvas.accelerated", true);
user_pref("gfx.canvas.accelerated.cache-items", 1024);
user_pref("gfx.canvas.accelerated.cache-size", 128);
// Expand the Skia glyph raster cache to 20 MB for crisp, zero-stall typography
user_pref("gfx.content.skia-font-cache-size", 20);
// Keep GPU work inside its own crash-resilient process (never disable: a GPU
// driver crash must not take the browser down)
user_pref("layers.gpu-process.enabled", true);
// Enable hardware video decode where the platform/GPU actually supports it
user_pref("media.hardware-video-decoding.enabled", true);
// Reuse decoded images across tabs instead of re-decoding on every navigation
user_pref("image.mem.shared.unmap.min_expiration_ms", 120000);

// --- RAM-First Caching (Zero Disk Bottleneck + Less SSD Wear) ---
// Disable the slow on-disk HTTP cache; serve hot assets straight from RAM
user_pref("browser.cache.disk.enable", false);
user_pref("browser.cache.memory.enable", true);
// 256 MB in-memory media/HTTP cache
user_pref("browser.cache.memory.capacity", 262144);
user_pref("browser.cache.memory.max_entry_size", 32768);
// Back/Forward cache stays on (Firefox default). The old
// browser.sessionhistory.max_total_viewers knob has been ignored since Fx 57 -
// setting it to 4 looked like a cap but changed nothing; the live limit is
// browser.sessionhistory.max_total_invisible_viewers, left at the default 10.
// Parallelise image decode and enlarge media streaming buffers
user_pref("image.mem.decode_bytes_at_a_time", 65536);
user_pref("image.cache.size", 10485760);
user_pref("media.memory_cache_max_size", 65536);
user_pref("media.cache_readahead_limit", 7200);
user_pref("media.cache_resume_threshold", 3600);

// --- HTTP/3 (QUIC), Connection Parallelism & TLS/DNS Speed ---
user_pref("network.http.http3.enable", true);
// Remove request pacing so a page's assets are fetched as one unpaced burst
user_pref("network.http.pacing.requests.enabled", false);
// Raise the global connection ceiling and per-host persistent pool
user_pref("network.http.max-connections", 1800);
user_pref("network.http.max-persistent-connections-per-server", 10);
user_pref("network.http.max-urgent-start-excessive-connections-per-host", 5);
// Keep DNS answers and TLS session tickets in cache for far longer
user_pref("network.dnsCacheEntries", 2000);
user_pref("network.dnsCacheExpiration", 3600);
user_pref("network.ssl_tokens_cache_capacity", 10240);

// --- Stability & Memory Pressure Safeguards ---
// Reclaim memory from idle tabs instead of swapping or crashing the browser
user_pref("browser.tabs.unloadOnLowMemory", true);

// --- Resource footprint: less RAM and CPU for the same pages ---
// Fewer content processes (Firefox default: 8). Each process carries a fixed
// baseline RSS, so 6 trims idle memory while keeping site isolation intact.
// Raise back to 8 if you routinely keep 30+ heavy tabs open.
user_pref("dom.ipc.processCount", 6);
// Cap the media cache (Firefox default: 500 MB). Long video sessions no longer
// pin hundreds of megabytes of RAM for already-watched segments.
user_pref("media.cache_size", 131072);
// Session restore used to hit the disk every 15 s. 60 s cuts background I/O and
// wakeups without changing crash-recovery behaviour.
user_pref("browser.sessionstore.interval", 60000);

// ---------------------------------------------------------------------------
// Source module: config/modules/02-shieldfox.js
// ---------------------------------------------------------------------------
// ============================================================================
// MODULE 02: SHIELDFOX — LibreFox-grade privacy + zero-breakage compatibility
// Goal: eliminate cross-site tracking, telemetry and network leaks while
//       preserving 120Hz+ displays, hardware WebGL/Canvas, dark mode, timezones
//       and normal OAuth/SSO flows.
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
user_pref("security.tls.enable_0rtt_data", false);
// (security.ssl.require_safe_negotiation used to be forced on here. It aborts
// the handshake when a server does not implement RFC 7507's fallback SCSV,
// which turned ordinary HTTPS sites and some corporate proxies into
// SSL_ERROR_UNSAFE_NEGOTIATION. Dropped: this suite promises zero site
// breakage, and it bought no meaningful privacy.)
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

// ---------------------------------------------------------------------------
// Source module: config/modules/03-cleanfox.js
// ---------------------------------------------------------------------------
// ============================================================================
// MODULE 03: CLEANFOX — Strip telemetry-fed bloat, ads, sponsored tiles & AI
// Goal: minimal RAM footprint, no sponsored content, no background ML workers,
//       and an interface that never nags. `// @lock` is reserved for ad-serving,
//       Pocket and the ML master switch, because those fetch remote content.
// ============================================================================

// --- Disable Background ML / LLM Workers (saves RAM, CPU and battery) ---
user_pref("browser.ml.enable", false); // @lock
user_pref("browser.ml.chat.enabled", false);
user_pref("browser.ml.chat.sidebar", false);
user_pref("browser.ml.chat.shortcuts", false);
user_pref("browser.ml.linkPreview.enabled", false);
user_pref("extensions.ml.enabled", false);
user_pref("extensions.htmlaboutaddons.local_model_management", false);

// --- Remove Pocket, Sponsored Tiles & Mozilla Upsells ---
user_pref("extensions.pocket.enabled", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsored", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false); // @lock
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false); // @lock
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false); // @lock
user_pref("browser.newtabpage.activity-stream.telemetry", false); // @lock
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.newtabpage.activity-stream.default.sites", "");
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.urlbar.quicksuggest.enabled", false);
user_pref("browser.urlbar.trending.featureGate", false);
user_pref("browser.urlbar.addons.featureGate", false);
user_pref("browser.urlbar.mdn.featureGate", false);
user_pref("browser.urlbar.pocket.featureGate", false);
user_pref("browser.urlbar.yelp.featureGate", false);
user_pref("browser.vpn_promo.enabled", false);
user_pref("browser.promo.focus.enabled", false);
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutConfig.showWarning", false);

// --- UI Customization & Annoyance Blocking ---
// Enables config/chrome/*.css: the floating Zen/Arc-style new-tab search pill
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
// Block intrusive notification and geolocation popups by default; a site can
// still earn a per-site grant from the address-bar permission panel
user_pref("permissions.default.desktop-notification", 2);
user_pref("permissions.default.geo", 2);

// --- Instant 0ms Fullscreen Transitions (Chromium/Brave parity) ---
user_pref("full-screen-api.transition-duration.enter", "0 0");
user_pref("full-screen-api.transition-duration.leave", "0 0");
user_pref("full-screen-api.warning.timeout", 0);

// ---------------------------------------------------------------------------
// Source module: config/modules/04-smoothfox.js
// ---------------------------------------------------------------------------
// ============================================================================
// MODULE 04: SMOOTHFOX — High-refresh-rate (120Hz/144Hz/240Hz) input physics
// Goal: fluid, low-latency scrolling and Asynchronous Pan/Zoom that samples the
//       real display refresh rate. Nothing here caps the frame rate.
// ============================================================================

// --- Mass-Spring-Damper scroll physics (the 120Hz+ friendly curve) ---
user_pref("general.smoothScroll", true);
user_pref("general.smoothScroll.msdPhysics.enabled", true);
user_pref("general.smoothScroll.msdPhysics.continuousMotionMaxDeltaMS", 12);
user_pref("general.smoothScroll.msdPhysics.motionBeginSpringConstant", 600);
user_pref("general.smoothScroll.msdPhysics.regularSpringConstant", 650);
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaMS", 25);
user_pref("general.smoothScroll.msdPhysics.slowdownSpringConstant", 250);

// --- Wheel feel: one notch covers twice the ground ---
// 275% was 2.75x, which reads as skipped content rather than speed once MSD
// physics is also smoothing the motion. 200% stays quick and stays precise.
user_pref("mousewheel.default.delta_multiplier_y", 200);

// --- Async Pan/Zoom responsiveness ---
user_pref("apz.overscroll.enabled", true);
