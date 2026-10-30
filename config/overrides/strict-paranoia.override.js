// ============================================================================
// SheepFox Optional "Strict Paranoia" Override (LibreWolf / Arkenfox Mode)
// WARNING: Enabling strict ResistFingerprinting (RFP) caps refresh rate at 60Hz,
// spoofs timezone to UTC, forces light theme, and adds Canvas random noise.
// Apply via: python3 scripts/install.py --strict
// ============================================================================

user_pref("privacy.resistFingerprinting", true);
user_pref("privacy.resistFingerprinting.letterboxing", false);
user_pref("webgl.disabled", false); // Set true only if you never use 3D/maps/games
user_pref("network.trr.mode", 3);   // Strict DoH only (no OS DNS fallback)
user_pref("privacy.sanitize.sanitizeOnShutdown", true);
user_pref("privacy.clearOnShutdown_v2.cache", true);
user_pref("privacy.clearOnShutdown_v2.cookiesAndStorage", false); // Preserve logins unless changed
user_pref("media.peerconnection.ice.no_host", true);
