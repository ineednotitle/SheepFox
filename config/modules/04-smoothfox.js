// ============================================================================
// MODULE 04: SMOOTHFOX — High-Refresh-Rate (120Hz/144Hz/240Hz) Input Physics
// Goal: Fluid, low-latency scrolling and Asynchronous Pan/Zoom responsiveness.
// ============================================================================

user_pref("general.smoothScroll", true);
user_pref("general.smoothScroll.msdPhysics.enabled", true);
user_pref("general.smoothScroll.msdPhysics.continuousMotionMaxDeltaMS", 12);
user_pref("general.smoothScroll.msdPhysics.motionBeginSpringConstant", 600);
user_pref("general.smoothScroll.msdPhysics.regularSpringConstant", 650);
user_pref("general.smoothScroll.msdPhysics.slowdownMinDeltaMS", 25);
user_pref("general.smoothScroll.msdPhysics.slowdownSpringConstant", 250);
user_pref("mousewheel.default.delta_multiplier_y", 275);
user_pref("apz.overscroll.enabled", true);
