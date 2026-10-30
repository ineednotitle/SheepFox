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

// --- Wheel feel: one notch covers more ground without feeling floaty ---
user_pref("mousewheel.default.delta_multiplier_y", 275);

// --- Async Pan/Zoom responsiveness ---
user_pref("apz.overscroll.enabled", true);
