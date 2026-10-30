// ============================================================================
// (SheepFox) Low-memory override — 4 GB machines, VMs, many-tab power users
//
// Apply with:  python3 scripts/install.py --low-memory
//          or  .\scripts\install-windows.bat -LowMemory
//
// TRADE-OFF: fission.autostart = false disables per-site process isolation
// (Fission). That is where most of the saving comes from on multi-tab sessions,
// but it also means a compromised renderer shares a process with other sites.
// Keep this OFF unless memory pressure is a real problem.
// ============================================================================

// One content process (plus the parent) instead of N.
user_pref("fission.autostart", false);
user_pref("dom.ipc.processCount", 2);

// Smaller in-memory caches. Disk cache stays off (see 01-speedfox.js).
user_pref("browser.cache.memory.capacity", 65536);
user_pref("browser.sessionhistory.max_total_viewers", 1);
user_pref("media.cache_size", 32768);

// Reclaim idle tabs sooner once memory pressure starts.
user_pref("browser.tabs.unloadOnLowMemory", true);
user_pref("browser.tabs.min_inactive_duration_before_unload", 60000);
