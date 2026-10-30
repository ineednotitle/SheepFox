// ============================================================================
// MODULE 03: CLEANFOX — Strip Bloat, Ads, Sponsored Tiles & Background AI
// Goal: Minimal RAM footprint and distraction-free interface out of the box.
// ============================================================================

// --- Disable Background ML / LLM Processes (Saves RAM & CPU) ---
user_pref("browser.ml.enable", false); // @lock
user_pref("browser.ml.chat.enabled", false);
user_pref("browser.ml.chat.sidebar", false);
user_pref("browser.ml.chat.shortcuts", false);
user_pref("browser.ml.linkPreview.enabled", false);
user_pref("extensions.ml.enabled", false);

// --- Remove Pocket, Sponsored Ads & Mozilla Upsells ---
user_pref("extensions.pocket.enabled", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsored", false); // @lock
user_pref("browser.newtabpage.activity-stream.showSponsoredTopSites", false); // @lock
user_pref("browser.newtabpage.activity-stream.feeds.section.topstories", false);
user_pref("browser.newtabpage.activity-stream.feeds.telemetry", false); // @lock
user_pref("browser.newtabpage.activity-stream.telemetry", false); // @lock
user_pref("browser.newtabpage.activity-stream.default.sites", "");
user_pref("browser.urlbar.suggest.quicksuggest.sponsored", false); // @lock
user_pref("browser.urlbar.suggest.quicksuggest.nonsponsored", false);
user_pref("browser.urlbar.quicksuggest.enabled", false);
user_pref("browser.urlbar.trending.featureGate", false);
user_pref("browser.urlbar.addons.featureGate", false);
user_pref("browser.urlbar.mdn.featureGate", false);
user_pref("browser.urlbar.pocket.featureGate", false);
user_pref("browser.urlbar.yelp.featureGate", false);
user_pref("browser.vpn_promo.enabled", false);
user_pref("browser.privatebrowsing.vpnpromourl", "");
user_pref("browser.promo.focus.enabled", false);
user_pref("extensions.getAddons.showPane", false);
user_pref("extensions.htmlaboutaddons.recommendations.enabled", false);
user_pref("browser.discovery.enabled", false);
user_pref("browser.shell.checkDefaultBrowser", false);
user_pref("browser.aboutConfig.showWarning", false);

// --- UI Customization & Annoyance Blocking ---
user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);
// Block intrusive notification & geolocation permission popups by default (per-site grant still works)
user_pref("permissions.default.desktop-notification", 2);
user_pref("permissions.default.geo", 2);
// Instant 0ms fullscreen transitions (matches Chromium/Brave responsiveness)
user_pref("full-screen-api.transition-duration.enter", "0 0");
user_pref("full-screen-api.transition-duration.leave", "0 0");
user_pref("full-screen-api.warning.timeout", 0);
