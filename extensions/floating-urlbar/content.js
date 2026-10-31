"use strict";
/*
 * (SheepFox) Floating URL Bar — in-page surface.
 *
 * Injected on demand by the background (`scripting.executeScript`) when the
 * shortcut is pressed, so a normal page load costs exactly nothing: no content
 * script is registered in the manifest, and nothing appears here until you ask
 * for it.
 *
 * A closed shadow root keeps the page's CSS out and this CSS in. On any page
 * that refuses injection (about:, addons.mozilla.org, the PDF viewer, strict
 * CSP corner cases) open() throws and the background falls back to its own
 * window — the shortcut never silently does nothing.
 */

(function (root) {
  "use strict";
  if (root.__sheepfoxFloatingBar) return;

  const browser = root.browser || root.chrome;
  const HOST_ID = "sheepfox-floating-url-bar";

  const state = {
    host: null,
    shadow: null,
    bar: null,
    previousFocus: null,
    open: false,
  };

  function ensureHost() {
    if (state.host && state.host.isConnected) return;
    const host = document.createElement("div");
    host.id = HOST_ID;
    // `all: initial` first, so a page rule like `div { display: flex }` cannot
    // leak into the shadow root through inherited properties.
    host.setAttribute(
      "style",
      "all: initial; display: block; position: fixed; inset: 0; z-index: 2147483647; pointer-events: none;"
    );
    const shadow = host.attachShadow({ mode: "closed" });
    const style = document.createElement("style");
    style.textContent = root.SHEEPFOX_BAR_CSS || "";
    shadow.appendChild(style);
    (document.body || document.documentElement).appendChild(host);
    state.host = host;
    state.shadow = shadow;
  }

  function open() {
    if (state.open) return;
    try {
      ensureHost();
      state.previousFocus = document.activeElement;
      state.bar = root.SheepFoxBar.mount({
        container: state.shadow,
        doc: document,
        mode: "overlay",
        onClose: close,
      });
      state.open = true;
      state.bar.focus();
    } catch (error) {
      state.open = false;
      removeHost();
      // The page refused the overlay: let the background open its window.
      void browser.runtime.sendMessage({ type: "sheepfox-fallback" });
    }
  }

  function removeHost() {
    if (state.bar) {
      state.bar.destroy();
      state.bar = null;
    }
    if (state.host && state.host.parentNode) state.host.parentNode.removeChild(state.host);
    state.host = null;
    state.shadow = null;
  }

  function close() {
    if (!state.open) return;
    state.open = false;
    const previous = state.previousFocus;
    removeHost();
    state.previousFocus = null;
    // Put the caret back where it was, so closing never loses your place.
    if (previous && typeof previous.focus === "function" && document.contains(previous)) {
      try {
        previous.focus({ preventScroll: true });
      } catch (error) {
        previous.focus();
      }
    }
  }

  function toggle() {
    if (state.open) close();
    else open();
  }

  browser.runtime.onMessage.addListener(function (message) {
    if (!message || message.type !== "sheepfox-toggle") return undefined;
    toggle();
    return Promise.resolve({ open: state.open });
  });

  // Never leave the overlay behind on a navigation or a bfcache restore.
  root.addEventListener("pagehide", close, true);
  root.addEventListener("unload", close, true);

  root.__sheepfoxFloatingBar = { open: open, close: close, toggle: toggle };
})(window);
