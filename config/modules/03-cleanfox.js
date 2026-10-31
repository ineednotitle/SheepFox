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

// --- Remove Pocket, Sponsored Tiles & Mozilla/URLBar Upsells ---
user_pref("extensions.pocket.enabled", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsored", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false); // @lock
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false); // @lock
user_pref("zen.urlbar.show-sponsored", false); // @lock
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
