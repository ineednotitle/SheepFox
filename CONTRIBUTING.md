# Contributing to (SheepFox) Firefox

Thank you for helping make **(SheepFox) Firefox** faster and more private! Every contribution must uphold our three core engineering invariants:

1. **Speed Without Instability:** Prefer documented Gecko/WebRender/Necko optimizations (`gfx.webrender.*`, HTTP/3, RAM caching, compiler LTO/PGO). Never force unstable graphics flags that crash older GPU drivers, and never disable the GPU crash-isolation process (`layers.gpu-process.enabled`).
2. **Privacy Without Breakage:** Default configurations (`01-speedfox.js` through `04-smoothfox.js`) must not break WebGL, high-refresh-rate monitors (120Hz+), dark mode, timezones, or standard OAuth/SSO flows. High-breakage hardening belongs in `config/overrides/strict-paranoia.override.js`.
3. **User Sovereignty (`defaultPref` over `lockPref`):** Only tag a preference with `// @lock` if enabling it transmits telemetry, ad-attribution data, sponsored pings, or unsolicited background studies to remote servers.

## Workflow for Modifying Preferences

1. Edit the appropriate module in `config/modules/`:
   - `01-speedfox.js` — Rendering, GPU, cache, and network speed
   - `02-shieldfox.js` — Tracking protection, partitioning, TLS/DoH, and telemetry removal
   - `03-cleanfox.js` — UI de-bloating, ads/Pocket removal, and ML/AI process disabling
   - `04-smoothfox.js` — Scrolling and input responsiveness
2. Regenerate compiled artifacts (`config/user.js` and `config/autoconfig/sheepfox.cfg`):
   ```bash
   make build-configs
   ```
3. Run the automated verification suite before committing:
   ```bash
   make check
   make test
   ```

## Workflow for Adding Source Patches

1. Format patches as clean unified git diffs (`-p1`) against the upstream version specified in `build/firefox-version.json`.
2. Place the `.patch` file in `patches/` with a numbered prefix (`0005-...patch`) and append its filename to `patches/series`.
3. Run `make test` to validate unified diff hunk line counts automatically.
