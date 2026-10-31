# Contributing to (SheepFox) Zen browser

Thank you for helping make **(SheepFox) Zen browser** faster and more private! Every contribution must uphold our three core engineering invariants:

1. **Speed Without Instability:** Prefer documented Gecko/WebRender/Necko optimizations (`gfx.webrender.*`, HTTP/3, RAM caching, compiler LTO/PGO). Never force unstable graphics flags that crash older GPU drivers, and never disable the GPU crash-isolation process (`layers.gpu-process.enabled`).
2. **Privacy Without Breakage:** Default configurations (`01-speedfox.js` through `04-smoothfox.js`) must not break Zen Browser features (Workspaces, Compact Mode, Glance, Split View, Mica/vibrancy backdrops), WebGL, high-refresh-rate monitors (120Hz+), dark mode, timezones, or standard OAuth/SSO flows. High-breakage hardening belongs in `config/overrides/strict-paranoia.override.js`.
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

1. Format patches as clean unified git diffs (`-p1`) against the upstream version specified in `mozbuild/firefox-version.json`.
2. Place the `.patch` file in `patches/` with a numbered prefix (`0005-...patch`) and append its filename to `patches/series`.
3. Run `make test` to validate unified diff hunk line counts and diffstat totals automatically,
   then `make patch-source` against the pinned tree to confirm every patch applies.

## Workflow for the Fork Build Scaffold

1. `mozbuild/` holds the build machinery — it is deliberately **not** called `build/` or `dist/`
   so that sandbox snapshots, CI caches and packagers never exclude it.
2. Only use configure switches that exist in the pinned Firefox tag. An unknown
   `ac_add_options` aborts `./mach configure` with `Unknown option: …`, so verify against
   `build/moz.configure/*.configure` before adding one (for example, Firefox 159 has no
   `--enable-jxl` switch — JPEG-XL is gated by the `image.jxl.enabled` pref).
3. Never force GPU paths that Firefox enables per driver (`gfx.webrender.all` in the patch series,
   disabling `layers.gpu-process.enabled`, …). Those belong in `config/modules/01-speedfox.js`
   where a user can revert them.

## Running the gates locally

```bash
make build-configs     # regenerate user.js + sheepfox.cfg
make check             # fail if the generated files are stale
pip install -r requirements-dev.txt   # optional: real CSS + PowerShell parsers
make test              # config invariants, policies, patches, launchers, installers
make verify            # check + test, exactly what CI runs
```
