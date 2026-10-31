"use strict";
/*
 * (SheepFox) Floating URL Bar — pure core.
 *
 * Address interpretation and result ranking live here, with no `browser.*`
 * access at all, so exactly the same file runs inside the extension background
 * and inside `node tests/extension/core.test.js`. Everything that can be wrong
 * without a browser is therefore covered by tests that need no Firefox.
 *
 * Exposes `globalThis.SheepFoxCore`.
 */

(function (root) {
  //: How many rows the bar will ever show. Beyond this the list stops being
  //: scannable without reading.
  const MAX_ROWS = 8;

  //: How many bookmark tiles the grid will render before it just scrolls.
  const MAX_TILES = 60;

  //: Schemes a launcher may open. `javascript:` and `data:` are deliberately
  //: absent: a URL can arrive from a paste, and a launcher must never execute
  //: what it was handed.
  const OPENABLE_SCHEMES = ["http:", "https:", "ftp:", "file:", "about:", "view-source:", "moz-extension:"];

  const IPV4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(:\d+)?(\/\S*)?$/;

  function safeUrl(text) {
    try {
      return new URL(text);
    } catch (error) {
      return null;
    }
  }

  function isValidIpv4(text) {
    const match = IPV4.exec(text);
    if (!match) return false;
    return match.slice(1, 5).every(function (octet) {
      return Number(octet) <= 255;
    });
  }

  /**
   * Turn what the user typed into an address, or return null when it is a
   * search phrase.
   *
   * The rules are deliberately narrow. A launcher that guesses too eagerly is
   * worse than one that does not guess: "how to fix a tv" must never become
   * `https://how to fix a tv`.
   */
  function interpretAsUrl(raw) {
    const text = String(raw == null ? "" : raw).trim();
    if (!text) return null;
    // An address never contains whitespace.
    if (/\s/.test(text)) return null;

    const scheme = /^([a-z][a-z0-9+.-]*):/i.exec(text);
    if (scheme) {
      const protocol = scheme[1].toLowerCase() + ":";
      if (OPENABLE_SCHEMES.indexOf(protocol) !== -1) {
        const url = safeUrl(text);
        return url ? url.href : null;
      }
      // `localhost:8080` and `example.com:8443/x` match the scheme pattern
      // above but are host:port, not protocols. Keep those; refuse the rest
      // (javascript:, data:, mailto:, ...).
      const remainder = text.slice(scheme[0].length);
      if (!/^\d+(\/\S*)?$/.test(remainder)) return null;
    }

    // Everything below is a bare host: normalise it through URL so the result
    // has the same shape as an explicit address ("https://x.test/" with the
    // trailing slash the URL parser adds).
    if (/^(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(\/\S*)?$/i.test(text)) {
      return normalize("http://" + text);
    }
    if (isValidIpv4(text)) {
      return normalize("http://" + text);
    }
    // host.tld[/path] — the TLD must be at least two characters, so "1.5" and
    // "v1.2" stay searches instead of becoming odd hostnames. A real TLD such
    // as "node.js" IS an address here, exactly as it is in every browser.
    if (/^([a-z0-9-]+\.)+[a-z][a-z0-9-]+(:\d+)?(\/\S*)?$/i.test(text)) {
      return normalize("https://" + text);
    }
    // ... and the punycode form of an internationalised name.
    if (/^([a-z0-9-]+\.)+xn--[a-z0-9-]+(:\d+)?(\/\S*)?$/i.test(text)) {
      return normalize("https://" + text);
    }
    return null;
  }

  function normalize(text) {
    const url = safeUrl(text);
    return url ? url.href : null;
  }

  function isSubsequence(needle, haystack) {
    let index = 0;
    for (let position = 0; position < haystack.length && index < needle.length; position += 1) {
      if (haystack[position] === needle[index]) index += 1;
    }
    return index === needle.length;
  }

  /**
   * How well one row matches the query, 0–100. Exact and prefix matches beat
   * word-start matches, which beat scattered subsequences. Keeping this a pure
   * number makes the ordering testable instead of "looks about right".
   */
  function scoreMatch(query, primary, secondary) {
    const needle = String(query || "").toLowerCase().trim();
    if (!needle) return 0;
    const title = String(primary || "").toLowerCase();
    const url = String(secondary || "").toLowerCase();

    if (title === needle) return 100;
    if (title.startsWith(needle)) return 92;
    if (url === needle) return 88;
    if (url.startsWith(needle)) return 80;

    const inTitle = title.indexOf(needle);
    if (inTitle >= 0) return 70 - Math.min(inTitle, 20);
    const inUrl = url.indexOf(needle);
    if (inUrl >= 0) return 60 - Math.min(inUrl, 20);

    // "gh" -> "GitHub", "mdn" -> "MDN Web Docs"
    if (isSubsequence(needle, title)) return 25;
    return 0;
  }

  /* ------------------------------------------------------------------ */
  /* bookmark grid                                                       */
  /* ------------------------------------------------------------------ */

  function hostOf(url) {
    try {
      return new URL(url).hostname.replace(/^www\./i, "");
    } catch (error) {
      return "";
    }
  }

  /**
   * Deterministic 0-359 hue for a string.
   *
   * Tiles need a colour, and a fixed palette would either need curating or look
   * random between reloads. Hashing the host means github.com is always the same
   * colour on every machine, with no state and no flicker.
   */
  function hueOf(text) {
    const value = String(text || "");
    let hash = 0;
    for (let index = 0; index < value.length; index += 1) {
      hash = (hash * 31 + value.charCodeAt(index)) % 360000;
    }
    return hash % 360;
  }

  function initialOf(title, host) {
    const source = String(title || host || "").trim();
    const characters = Array.from(source);
    return characters.length ? characters[0].toUpperCase() : "?";
  }

  /**
   * Shape Firefox bookmark nodes into grid tiles.
   *
   * Firefox returns separators as nodes too, and a bookmark with no title is
   * common; both would render as blank squares if passed straight through.
   * Firefox's own order is kept: the toolbar is arranged by hand.
   */
  function toGridItems(nodes) {
    const items = [];
    for (const node of nodes || []) {
      if (items.length >= MAX_TILES) break;
      if (!node || node.type === "separator") continue;
      const isFolder = node.type === "folder";
      const host = isFolder ? "" : hostOf(node.url);
      const title = String(node.title || "").trim() || (isFolder ? "Folder" : host || "Bookmark");
      items.push({
        id: node.id,
        kind: isFolder ? "folder" : "bookmark",
        title: title,
        url: isFolder ? "" : String(node.url || ""),
        subtitle: isFolder ? "Folder" : host,
        host: host,
        // Firefox does not expose favicons for bookmark nodes, so this is
        // usually empty and the tile falls back to a letter. When a node does
        // carry one it is used as-is — never fetched from a favicon service,
        // because asking a third party about a bookmark is a leak.
        favicon: isFolder ? "" : String(node.faviconUrl || ""),
        initial: initialOf(title, host),
        hue: hueOf(host || title),
        childCount: isFolder && node.children ? node.children.length : 0,
      });
    }
    return items;
  }

  function toRows(rows) {
    const seen = new Set();
    const result = [];
    for (const row of rows) {
      if (result.length >= MAX_ROWS) break;
      // Tabs are unique per tab, not per URL: "Open address" and "Switch to
      // tab" are different actions and both belong in the list. Pages
      // (bookmark + history) collapse onto the URL so the same page never
      // appears twice.
      const key =
        row.kind === "tab" ? "tab:" + row.tabId : row.url || row.kind + ":" + row.query;
      if (seen.has(key)) continue;
      seen.add(key);
      result.push(Object.assign({ id: "sheepfox-row-" + result.length }, row));
    }
    return result;
  }

  function byScore(query, collection, weight, titleKey, urlKey) {
    return collection
      .map(function (item) {
        return { item: item, score: scoreMatch(query, item[titleKey], item[urlKey]) + weight };
      })
      .filter(function (entry) {
        return entry.score > weight;
      })
      .sort(function (a, b) {
        return b.score - a.score;
      })
      .map(function (entry) {
        return entry.item;
      });
  }

  /**
   * Build the visible rows, in order, from already-fetched candidates:
   *
   *   address  →  open tabs  →  bookmarks  →  history  →  web search
   *
   * Weights encode what a keyboard launcher is usually after: a tab you
   * already have open beats a bookmark, which beats a page you once visited.
   */
  function rank(query, candidates) {
    const text = String(query || "").trim();
    const collections = candidates || {};
    if (!text) return [];

    const rows = [];
    if (collections.directUrl) {
      rows.push({
        kind: "url",
        url: collections.directUrl,
        title: collections.directUrl.replace(/^[a-z]+:\/\//i, "").replace(/\/$/, ""),
        subtitle: "Open address",
      });
    }

    for (const tab of byScore(text, collections.tabs || [], 6, "title", "url")) {
      rows.push({
        kind: "tab",
        tabId: tab.tabId,
        windowId: tab.windowId,
        title: tab.title || tab.url,
        url: tab.url,
        subtitle: "Switch to tab",
      });
    }
    for (const mark of byScore(text, collections.bookmarks || [], 4, "title", "url")) {
      rows.push({ kind: "bookmark", url: mark.url, title: mark.title || mark.url, subtitle: "Bookmark" });
    }
    for (const visit of byScore(text, collections.history || [], 0, "title", "url")) {
      rows.push({ kind: "history", url: visit.url, title: visit.title || visit.url, subtitle: "History" });
    }

    rows.push({
      kind: "search",
      query: text,
      title: "Search for “" + text + "”",
      subtitle: collections.engineName || "the web",
    });

    return toRows(rows);
  }

  const api = {
    MAX_ROWS: MAX_ROWS,
    MAX_TILES: MAX_TILES,
    hostOf: hostOf,
    hueOf: hueOf,
    initialOf: initialOf,
    toGridItems: toGridItems,
    OPENABLE_SCHEMES: OPENABLE_SCHEMES.slice(),
    interpretAsUrl: interpretAsUrl,
    scoreMatch: scoreMatch,
    isSubsequence: isSubsequence,
    isValidIpv4: isValidIpv4,
    rank: rank,
    toRows: toRows,
  };

  root.SheepFoxCore = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
