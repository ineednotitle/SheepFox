"use strict";
/*
 * (SheepFox) Floating URL Bar — background (event page).
 *
 * Everything privileged lives here: the shortcut, reading history/bookmarks/tabs,
 * and the decision whether the bar can be injected into the page or has to open
 * its own window. The two UI surfaces only ever send messages.
 */

const core = globalThis.SheepFoxCore;
const browser = globalThis.browser || globalThis.chrome;

//: Window surface geometry.
const BAR_WIDTH = 640;
const PILL_WINDOW_HEIGHT = 72;
const WINDOW_MARGIN = 96;
//: Injected into the tab on demand, in this order.
const OVERLAY_FILES = ["styles.js", "ui.js", "content.js"];

let cachedEngineName = null;

/* ------------------------------------------------------------------ */
/* helpers                                                             */
/* ------------------------------------------------------------------ */

async function attempt(action, fallback) {
  try {
    return await action();
  } catch (error) {
    return fallback;
  }
}

async function defaultEngineName() {
  if (cachedEngineName) return cachedEngineName;
  const engine = await attempt(async function () {
    if (browser.search.getDefault) return await browser.search.getDefault();
    const engines = await browser.search.get();
    return engines.find(function (candidate) {
      return candidate.isDefault;
    });
  }, null);
  cachedEngineName = engine && engine.name ? engine.name : null;
  return cachedEngineName || "the web";
}

/* ------------------------------------------------------------------ */
/* querying                                                            */
/* ------------------------------------------------------------------ */

function onlyHttpPages(items) {
  return items.filter(function (item) {
    return typeof item.url === "string" && /^(https?|file):/i.test(item.url);
  });
}

async function collectCandidates(query) {
  const results = await Promise.all([
    attempt(function () {
      return browser.tabs.query({});
    }, []),
    attempt(function () {
      return browser.bookmarks.search({ query: query });
    }, []),
    attempt(function () {
      return browser.history.search({ text: query, startTime: 0, maxResults: 30 });
    }, []),
  ]);

  const tabs = onlyHttpPages(results[0] || []).map(function (tab) {
    return { tabId: tab.id, windowId: tab.windowId, title: tab.title || "", url: tab.url };
  });
  const bookmarks = onlyHttpPages(results[1] || []).map(function (mark) {
    return { title: mark.title || "", url: mark.url };
  });
  const history = onlyHttpPages(results[2] || []).map(function (visit) {
    return { title: visit.title || "", url: visit.url };
  });

  return { tabs: tabs, bookmarks: bookmarks, history: history };
}

async function handleQuery(text) {
  const query = String(text || "").trim();
  const engineName = await defaultEngineName();
  if (!query) return { rows: [], engine: engineName };

  const candidates = await collectCandidates(query);
  candidates.directUrl = core.interpretAsUrl(query);
  candidates.engineName = engineName;

  return { rows: core.rank(query, candidates), engine: engineName };
}

/* ------------------------------------------------------------------ */
/* opening                                                             */
/* ------------------------------------------------------------------ */

async function focusWindow(windowId) {
  if (!windowId) return;
  await attempt(function () {
    return browser.windows.update(windowId, { focused: true });
  }, null);
}

async function goTo(url, target) {
  if (!url) return;
  if (target.newTab || !target.tabId) {
    await attempt(function () {
      return browser.tabs.create({ url: url });
    }, null);
    return;
  }
  await browser.tabs.update(target.tabId, { url: url, active: true });
  await focusWindow(target.windowId);
}

async function openTab(row, newTab) {
  if (newTab && row.url) {
    await goTo(row.url, { newTab: true });
    return;
  }
  await browser.tabs.update(row.tabId, { active: true });
  await focusWindow(row.windowId);
}

async function searchWeb(query, target) {
  // Firefox's own search service keeps the user's engine and its parameters.
  const used = await attempt(async function () {
    const properties = { query: query };
    if (target.newTab) properties.disposition = "NEW_TAB";
    else if (target.tabId) properties.tabId = target.tabId;
    await browser.search.search(properties);
    return true;
  }, false);

  if (used) {
    if (!target.newTab) await focusWindow(target.windowId);
    return;
  }

  // No search API (or it failed): fall back to a plain URL. DuckDuckGo is the
  // default here only because it needs no API key and no account.
  await goTo("https://duckduckgo.com/?q=" + encodeURIComponent(query), target);
}

/**
 * Resolve which tab an opened row should affect.
 *
 * The content-script surface knows its own tab through the message sender; the
 * window surface carries the tab it was opened from in its URL. Falling back to
 * "a new tab" is always correct, just less convenient.
 */
function resolveTarget(options, sender) {
  const settings = options || {};
  const senderTab = sender && sender.tab ? sender.tab : null;
  return {
    newTab: Boolean(settings.newTab),
    tabId: settings.targetTabId || (senderTab ? senderTab.id : null),
    windowId: settings.targetWindowId || (senderTab ? senderTab.windowId : null),
  };
}

async function openRow(row, options, sender) {
  if (!row || typeof row !== "object") return { ok: false };
  const target = resolveTarget(options, sender);

  if (row.kind === "tab" && row.tabId != null) {
    await openTab(row, target.newTab);
    return { ok: true };
  }
  if (row.kind === "search" && row.query) {
    await searchWeb(row.query, target);
    return { ok: true };
  }
  if (row.url) {
    await goTo(row.url, target);
    return { ok: true };
  }
  return { ok: false };
}

/* ------------------------------------------------------------------ */
/* surfaces                                                            */
/* ------------------------------------------------------------------ */

async function injectOverlay(tab) {
  if (!tab || tab.id == null) return false;
  if (!browser.scripting || !browser.scripting.executeScript) return false;

  try {
    // On demand, never on load: a page nobody asked the bar for is untouched.
    await browser.scripting.executeScript({ target: { tabId: tab.id }, files: OVERLAY_FILES });
  } catch (error) {
    return false; // about:, addons.mozilla.org, the PDF viewer, no host access
  }

  return attempt(async function () {
    await browser.tabs.sendMessage(tab.id, { type: "sheepfox-toggle" });
    return true;
  }, false);
}

async function openWindowSurface(tab) {
  const geometry = await attempt(function () {
    return browser.windows.getCurrent();
  }, null);

  const available = geometry && geometry.width ? geometry.width : BAR_WIDTH + WINDOW_MARGIN * 2;
  const width = Math.max(360, Math.min(BAR_WIDTH, Math.round(available) - WINDOW_MARGIN));
  const left = Math.round((geometry ? geometry.left || 0 : 0) + (available - width) / 2);
  const top = Math.round((geometry ? geometry.top || 0 : 0) + Math.max(80, (geometry ? geometry.height || 720 : 720) * 0.16));

  const params = new URLSearchParams();
  if (tab && tab.id != null) params.set("target", String(tab.id));
  if (tab && tab.windowId != null) params.set("window", String(tab.windowId));
  const suffix = params.toString() ? "?" + params.toString() : "";

  return browser.windows.create({
    url: browser.runtime.getURL("search.html") + suffix,
    type: "popup",
    width: width,
    height: PILL_WINDOW_HEIGHT,
    left: left,
    top: top,
    focused: true,
  });
}

async function openBar() {
  const tabs = await attempt(function () {
    return browser.tabs.query({ active: true, currentWindow: true });
  }, []);
  const tab = tabs && tabs[0] ? tabs[0] : null;

  if (tab && (await injectOverlay(tab))) return;
  await attempt(function () {
    return openWindowSurface(tab);
  }, null);
}

/* ------------------------------------------------------------------ */
/* wiring                                                              */
/* ------------------------------------------------------------------ */

browser.commands.onCommand.addListener(function (command) {
  if (command !== "open-floating-bar") return;
  void openBar();
});

if (browser.action && browser.action.onClicked) {
  browser.action.onClicked.addListener(function () {
    void openBar();
  });
}

browser.runtime.onMessage.addListener(function (message, sender) {
  if (!message || typeof message.type !== "string") return undefined;
  switch (message.type) {
    case "sheepfox-query":
      return handleQuery(message.text);
    case "sheepfox-open":
      return openRow(message.row, message.options, sender);
    case "sheepfox-fallback":
      // The page refused the overlay (mount threw): show the window instead.
      // Deliberately not openBar(), which would inject again and loop.
      return attempt(function () {
        return openWindowSurface(sender && sender.tab ? sender.tab : null);
      }, null);
    default:
      return undefined;
  }
});
