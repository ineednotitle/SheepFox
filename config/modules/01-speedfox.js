// ============================================================================
// MODULE 01: SPEEDFOX — Gecko GPU, Cache & Network Acceleration
// Goal: Brave-class page-load responsiveness without sacrificing stability.
// Every value here is a supported Gecko/WebRender/Necko knob. Nothing forces
// an unsupported GPU path, keeps the GPU crash-isolation process, and nothing
// disables JavaScript JIT or WebGL.
// ============================================================================

// --- Rendering & Content Layout Pipeline ---
// Fast initial visual paint (5ms avoids flash-of-unstyled-content jank while
// still feeling instantaneous)
user_pref("nglayout.initialpaint.delay", 5);

// --- WebRender, GPU Compositing & Skia Acceleration ---
// Enable the full GPU-driven WebRender pipeline and pre-cache shaders so the
// first scroll and the first animation never hitch
user_pref("gfx.webrender.all", true);
user_pref("gfx.webrender.precache-shaders", true);
user_pref("gfx.webrender.compositor", true);
// Hardware-accelerated 2D Canvas with a 512 MB VRAM surface cache
user_pref("gfx.canvas.accelerated", true);
user_pref("gfx.canvas.accelerated.cache-items", 4096);
user_pref("gfx.canvas.accelerated.cache-size", 512);
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
// Keep 4 recent pages in the Back/Forward cache for 0ms history navigation
user_pref("browser.sessionhistory.max_total_viewers", 4);
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
