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
