"use strict";
/*
 * (SheepFox) Floating URL Bar — window surface.
 *
 * Loaded by search.html when the background opened a popup window instead of
 * injecting into the page (about:, addons.mozilla.org, the PDF viewer, or any
 * tab that refused the overlay). The window is created at pill height and grows
 * downwards as results appear, so it reads as a bar rather than a dialog.
 */

(function (root) {
  "use strict";

  const browser = root.browser || root.chrome;
  const params = new URLSearchParams(root.location.search);
  const target = {
    tabId: Number(params.get("target")) || null,
    windowId: Number(params.get("window")) || null,
  };

  //: Leave room for the 6px inset on each side of the card.
  const WINDOW_CHROME = 12;
  //: Never taller than this: past it the list scrolls inside the card.
  const MAX_HEIGHT = 620;

  let lastHeight = 0;

  function closeWindow() {
    // windows.remove() is the supported way out of a window the extension
    // created; window.close() covers the case where it is refused.
    browser.windows.remove(browser.windows.WINDOW_ID_CURRENT).catch(function () {
      root.close();
    });
  }

  function resizeTo(cardHeight) {
    if (!Number.isFinite(cardHeight) || cardHeight <= 0) return;
    const height = Math.min(MAX_HEIGHT, Math.ceil(cardHeight) + WINDOW_CHROME);
    if (height === lastHeight) return;
    lastHeight = height;
    browser.windows.update(browser.windows.WINDOW_ID_CURRENT, { height: height }).catch(function () {
      // A fixed-size window manager may refuse; the CSS keeps the card usable.
    });
  }

  const bar = root.SheepFoxBar.mount({
    container: document.body,
    doc: document,
    mode: "window",
    placeholder: "Search or enter an address",
    target: target,
    onClose: closeWindow,
    onHeight: resizeTo,
  });

  bar.focus();

  // Spotlight behaviour: clicking anywhere else dismisses the bar.
  root.addEventListener("blur", function () {
    root.setTimeout(function () {
      if (!document.hasFocus()) closeWindow();
    }, 120);
  });
})(window);
