"use strict";
/*
 * The bar's stylesheet, as a string.
 *
 * Why a string instead of a .css file: the in-page surface lives in a closed
 * shadow root. A `<link>` there would load asynchronously and flash an unstyled
 * pill on every open, a page-level content-style sheet cannot cross the shadow
 * boundary at all, and a fetch() to moz-extension:// is one more thing that can
 * fail on a strict page. A string injected synchronously is the only variant
 * that is guaranteed to paint correctly the first time, on every page.
 *
 * Everything is scoped under .sheepfox-bar, so the window surface (light DOM)
 * and the overlay (shadow DOM) share exactly one source of truth.
 * tests/test_repo.py parses this string with tinycss2.
 */

(function (root) {
  root.SHEEPFOX_BAR_CSS = `
.sheepfox-bar {
  --sf-radius: 24px;
  --sf-field-height: 56px;
  --sf-bg: rgba(26, 26, 30, 0.94);
  --sf-border: rgba(255, 255, 255, 0.13);
  --sf-text: #f4f4f5;
  --sf-dim: #9d9da7;
  --sf-hover: rgba(255, 255, 255, 0.07);
  --sf-selected: rgba(125, 211, 252, 0.16);
  --sf-accent: #7dd3fc;
  --sf-shadow: 0 24px 64px rgba(0, 0, 0, 0.55), 0 2px 10px rgba(0, 0, 0, 0.35);
  --sf-font: 15px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

  box-sizing: border-box;
  color: var(--sf-text);
  font: var(--sf-font);
  text-align: start;
  -webkit-font-smoothing: antialiased;
}

.sheepfox-bar *,
.sheepfox-bar *::before,
.sheepfox-bar *::after {
  box-sizing: border-box;
}

/* The overlay host is pointer-events:none so the page stays inert behind an
   inert element; pointer-events inherits, so the interactive children have to
   opt back in or nothing here can be clicked. */
.sheepfox-bar,
.sheepfox-backdrop {
  pointer-events: auto;
}

.sheepfox-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(8, 8, 10, 0.34);
  overscroll-behavior: contain;
  -webkit-backdrop-filter: blur(2px);
  backdrop-filter: blur(2px);
}

/* In-page surface: a pill centred in the viewport, over a dimmed page. */
.sheepfox-bar--overlay {
  position: fixed;
  inset-inline: 0;
  top: 30vh;
  z-index: 1;
  width: min(92vw, 640px);
  margin-inline: auto;
}

/* A percentage max-height needs a definite container, which the fixed pill is
   not: cap the card itself so a long shelf scrolls instead of running off the
   bottom of a short screen. */
.sheepfox-bar--overlay .sheepfox-card {
  max-height: min(560px, 68vh);
}

/* Window surface: the popup window is the pill, so the card fills it. */
.sheepfox-bar--window {
  position: fixed;
  inset: 6px;
  display: flex;
  align-items: flex-start;
}

.sheepfox-card {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 100%;
  overflow: hidden;
  background: var(--sf-bg);
  border: 1px solid var(--sf-border);
  border-radius: var(--sf-radius);
  box-shadow: var(--sf-shadow);
}

.sheepfox-card:focus-within {
  border-color: var(--sf-accent);
}

.sheepfox-field {
  display: flex;
  flex: none;
  align-items: center;
  gap: 12px;
  min-height: var(--sf-field-height);
  padding-inline: 20px;
}

.sheepfox-glyph {
  flex: none;
  width: 20px;
  height: 20px;
  color: var(--sf-dim);
}

.sheepfox-glyph svg {
  display: block;
  width: 100%;
  height: 100%;
}

.sheepfox-input {
  flex: 1 1 auto;
  min-width: 0;
  height: var(--sf-field-height);
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--sf-text);
  font: inherit;
  font-size: 16px;
  outline: none;
  caret-color: var(--sf-accent);
}

.sheepfox-input::placeholder {
  color: var(--sf-dim);
  opacity: 1;
}

.sheepfox-key {
  flex: none;
  padding: 4px 6px;
  border: 1px solid var(--sf-border);
  border-radius: 6px;
  color: var(--sf-dim);
  font: 11px/1 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

/* ---- empty state: the bookmarks shelf ---- */

.sheepfox-crumb {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 14px 8px;
  color: var(--sf-dim);
  font-size: 12.5px;
}

.sheepfox-crumb[hidden] {
  display: none;
}

.sheepfox-back {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 4px 10px 4px 6px;
  border: 1px solid var(--sf-border);
  border-radius: 999px;
  background: transparent;
  color: var(--sf-text);
  font: inherit;
  font-size: 12.5px;
  cursor: pointer;
}

.sheepfox-back:hover {
  background: var(--sf-hover);
}

.sheepfox-back-glyph {
  width: 14px;
  height: 14px;
}

.sheepfox-crumb-label {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sheepfox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(92px, 1fr));
  gap: 6px;
  max-height: min(46vh, 330px);
  margin: 0;
  padding: 2px 12px 10px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
}

.sheepfox-grid[hidden] {
  display: none;
}

.sheepfox-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 7px;
  padding: 9px 6px;
  border: 0;
  border-radius: 16px;
  background: transparent;
  color: var(--sf-text);
  font: inherit;
  text-align: center;
  cursor: pointer;
}

.sheepfox-tile:hover {
  background: var(--sf-hover);
}

.sheepfox-tile[aria-selected="true"] {
  background: var(--sf-selected);
}

.sheepfox-tile-glyph {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border-radius: 12px;
  background: hsl(var(--sf-tile-hue, 210) 62% 55% / 0.22);
  color: hsl(var(--sf-tile-hue, 210) 72% 74%);
  font-size: 15px;
  font-weight: 600;
}

.sheepfox-tile-img {
  width: 18px;
  height: 18px;
  border-radius: 5px;
  object-fit: contain;
}

.sheepfox-tile-glyph--folder {
  background: var(--sf-hover);
  color: var(--sf-accent);
}

.sheepfox-tile-icon {
  width: 20px;
  height: 20px;
}

.sheepfox-tile-title {
  display: -webkit-box;
  overflow: hidden;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow-wrap: anywhere;
  font-size: 12px;
  line-height: 1.3;
}

.sheepfox-tile-count {
  margin-top: -3px;
  color: var(--sf-dim);
  font-size: 10.5px;
}

.sheepfox-empty {
  margin: 0;
  padding: 10px 16px 14px;
  color: var(--sf-dim);
  font-size: 13px;
}

.sheepfox-list {
  min-height: 0;
  max-height: min(52vh, 380px);
  margin: 0;
  padding: 0 8px;
  overflow-y: auto;
  overscroll-behavior: contain;
  list-style: none;
  scrollbar-width: thin;
}

.sheepfox-list:empty {
  display: none;
}

.sheepfox-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 9px 12px;
  border-radius: 14px;
  color: var(--sf-text);
  cursor: pointer;
}

.sheepfox-row + .sheepfox-row {
  margin-top: 2px;
}

.sheepfox-row:hover {
  background: var(--sf-hover);
}

.sheepfox-row[aria-selected="true"] {
  background: var(--sf-selected);
}

.sheepfox-row-glyph {
  flex: none;
  width: 18px;
  height: 18px;
  color: var(--sf-dim);
}

.sheepfox-row[aria-selected="true"] .sheepfox-row-glyph {
  color: var(--sf-accent);
}

.sheepfox-row-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.sheepfox-title {
  overflow: hidden;
  font-size: 15px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sheepfox-subtitle {
  overflow: hidden;
  color: var(--sf-dim);
  font-size: 12.5px;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.sheepfox-footer {
  display: flex;
  flex: none;
  flex-wrap: wrap;
  gap: 16px;
  padding: 6px 20px 12px;
  color: var(--sf-dim);
  font-size: 12px;
}

@media (prefers-color-scheme: light) {
  .sheepfox-bar {
    --sf-bg: rgba(255, 255, 255, 0.97);
    --sf-border: rgba(15, 23, 42, 0.12);
    --sf-text: #0f172a;
    --sf-dim: #64748b;
    --sf-hover: rgba(15, 23, 42, 0.06);
    --sf-selected: rgba(14, 116, 144, 0.12);
    --sf-accent: #0e7490;
    --sf-shadow: 0 24px 64px rgba(15, 23, 42, 0.2), 0 2px 8px rgba(15, 23, 42, 0.12);
  }

  .sheepfox-backdrop {
    background: rgba(15, 23, 42, 0.16);
  }
}

@media (prefers-color-scheme: light) {
  .sheepfox-tile-glyph {
    background: hsl(var(--sf-tile-hue, 210) 70% 55% / 0.16);
    color: hsl(var(--sf-tile-hue, 210) 55% 38%);
  }
}

@media (prefers-reduced-motion: no-preference) {
  .sheepfox-bar--overlay .sheepfox-card {
    animation: sheepfox-card-in 90ms ease-out;
  }

  @keyframes sheepfox-card-in {
    from {
      opacity: 0;
      transform: translateY(-4px) scale(0.99);
    }

    to {
      opacity: 1;
      transform: none;
    }
  }
}

/* Windows High Contrast: the border becomes the only edge, so it must be a
   real system colour rather than a translucent one. */
@media (forced-colors: active) {
  .sheepfox-card {
    border: 1px solid CanvasText;
    background: Canvas;
    color: CanvasText;
    box-shadow: none;
  }

  .sheepfox-backdrop {
    background: transparent;
  }

  .sheepfox-row[aria-selected="true"],
  .sheepfox-tile[aria-selected="true"] {
    outline: 2px solid Highlight;
    outline-offset: -2px;
  }

  .sheepfox-tile-glyph {
    background: Canvas;
    color: CanvasText;
  }

  .sheepfox-input::placeholder,
  .sheepfox-subtitle,
  .sheepfox-footer {
    color: GrayText;
  }
}
`;
})(typeof window !== "undefined" ? window : globalThis);
