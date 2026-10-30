// ============================================================================
// MODULE 01: SPEEDFOX — Gecko GPU, Cache & Network Acceleration
// Goal: Brave-class page-load responsiveness without sacrificing stability.
// ============================================================================

// --- Rendering & Content Layout Pipeline ---
// Fast initial visual paint (5ms avoids FOUC while feeling instantaneous)
user_pref("nglayout.initialpaint.delay", 5);
// Coalesce DOM/reflow notifications at 100ms intervals to cut CPU layout thrashing
user_pref("content.notify.interval", 100000);
user_pref("content.notify.ontimer", true);

// --- WebRender, GPU Compositing & Skia Acceleration ---
// Enable full GPU-driven WebRender pipeline & shader pre-caching (eliminates first-scroll hitching)
user_pref("gfx.webrender.all", true);
user_pref("gfx.webrender.precache-shaders", true);
user_pref("gfx.webrender.compositor", true);
// Hardware-accelerated 2D HTML5 Canvas with expanded VRAM surface cache
user_pref("gfx.canvas.accelerated", true);
user_pref("gfx.canvas.accelerated.cache-items", 4096);
user_pref("gfx.canvas.accelerated.cache-size", 512);
// Expand Skia glyph raster cache (20 MB) for crisp, zero-stall typography
user_pref("gfx.content.skia-font-cache-size", 20);
// Keep GPU work isolated in its own crash-resilient process
user_pref("layers.gpu-process.enabled", true);
// Enable stable hardware video decode (avoids force-enabling on unsupported GPUs for stability)
user_pref("media.hardware-video-decoding.enabled", true);

// --- RAM-First Caching (Zero Disk Bottleneck + Less SSD Wear) ---
// Disable slow disk cache; serve hot assets directly from high-speed RAM
user_pref("browser.cache.disk.enable", false);
user_pref("browser.cache.memory.enable", true);
user_pref("browser.cache.memory.capacity", 262144);
user_pref("browser.cache.memory.max_entry_size", 32768);
// Keep 4 recent pages in Back/Forward cache (bfcache) for 0ms instant navigation
user_pref("browser.sessionhistory.max_total_viewers", 4);
// Parallelize & enlarge image decode and media streaming buffers
user_pref("image.mem.decode_bytes_at_a_time", 65536);
user_pref("image.cache.size", 10485760);
user_pref("media.memory_cache_max_size", 65536);
user_pref("media.cache_readahead_limit", 7200);
user_pref("media.cache_resume_threshold", 3600);

// --- HTTP/3 (QUIC), Connection Parallelism & TLS/DNS Speed ---
user_pref("network.http.http3.enable", true);
user_pref("network.http.pacing.requests.enabled", false);
user_pref("network.http.max-connections", 1800);
user_pref("network.http.max-persistent-connections-per-server", 10);
user_pref("network.http.max-urgent-start-excessive-connections-per-host", 5);
user_pref("network.dnsCacheEntries", 2000);
user_pref("network.dnsCacheExpiration", 3600);
user_pref("network.ssl_tokens_cache_capacity", 10240);

// --- Stability & Memory Pressure Safeguards ---
user_pref("dom.ipc.processPriorityManager.backgroundPerceivable.gracePeriodSeconds", 15);
user_pref("browser.tabs.unloadOnLowMemory", true);
