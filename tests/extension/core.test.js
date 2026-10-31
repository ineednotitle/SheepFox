"use strict";
/*
 * Unit tests for extensions/floating-urlbar/core.js.
 *
 * Run directly (`node tests/extension/core.test.js`) or through the Python
 * suite, which shells out to node and fails if this file fails. No framework:
 * the extension has no build step and no dependencies, and neither do its
 * tests.
 */

const path = require("node:path");
const assert = require("node:assert/strict");
const core = require(path.join(__dirname, "..", "..", "extensions", "floating-urlbar", "core.js"));

let checks = 0;
const failures = [];

function test(name, body) {
  try {
    body();
    checks += 1;
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
  }
}

/* ------------------------------------------------------------------ */
/* interpretAsUrl                                                      */
/* ------------------------------------------------------------------ */

test("plain hostname becomes https", () => {
  assert.equal(core.interpretAsUrl("example.com"), "https://example.com/");
  assert.equal(core.interpretAsUrl("www.example.co.uk/a?b=1"), "https://www.example.co.uk/a?b=1");
});

test("explicit schemes are preserved", () => {
  assert.equal(core.interpretAsUrl("http://example.com/x"), "http://example.com/x");
  assert.equal(core.interpretAsUrl("https://example.com"), "https://example.com/");
  assert.equal(core.interpretAsUrl("about:config"), "about:config");
});

test("localhost and IPv4 get http, not https", () => {
  assert.equal(core.interpretAsUrl("localhost:3000"), "http://localhost:3000/");
  assert.equal(core.interpretAsUrl("127.0.0.1:8080/admin"), "http://127.0.0.1:8080/admin");
  assert.equal(core.interpretAsUrl("192.168.1.10"), "http://192.168.1.10/");
});

test("port-only lookalikes are not protocols", () => {
  assert.equal(core.interpretAsUrl("example.com:8443"), "https://example.com:8443/");
  assert.equal(core.interpretAsUrl("example.com:8443/x"), "https://example.com:8443/x");
});

test("dangerous and unknown schemes are refused", () => {
  for (const text of ["javascript:alert(1)", "data:text/html,<b>x", "mailto:a@b.cd", "vbscript:x", "chrome://settings"]) {
    assert.equal(core.interpretAsUrl(text), null, `${text} must not be treated as an address`);
  }
});

test("sentences stay searches", () => {
  for (const text of [
    "how to fix a tv",
    "1.5",
    "v1.2",
    "a.b",
    "",
    "   ",
    "sheepfox",
  ]) {
    assert.equal(core.interpretAsUrl(text), null, `${JSON.stringify(text)} must stay a search`);
  }
});

test("invalid IPv4 octets are not addresses", () => {
  assert.equal(core.interpretAsUrl("999.1.1.1"), null);
});

test("punycode domains resolve", () => {
  assert.equal(core.interpretAsUrl("münchen.de"), null, "unicode needs the browser to punycode it");
  assert.equal(core.interpretAsUrl("xn--mnchen-3ya.de"), "https://xn--mnchen-3ya.de/");
});

/* ------------------------------------------------------------------ */
/* scoreMatch                                                          */
/* ------------------------------------------------------------------ */

test("exact and prefix matches outrank substring matches", () => {
  const exact = core.scoreMatch("github", "GitHub", "https://github.com/");
  const prefix = core.scoreMatch("git", "GitHub", "https://github.com/");
  const inside = core.scoreMatch("hub", "GitHub", "https://github.com/");
  const urlOnly = core.scoreMatch("github", "Something else", "https://github.com/");
  assert.ok(exact > prefix, `${exact} > ${prefix}`);
  assert.ok(prefix > inside, `${prefix} > ${inside}`);
  assert.ok(inside > urlOnly, `${inside} > ${urlOnly}`);
  assert.equal(core.scoreMatch("zzz", "GitHub", "https://github.com/"), 0);
});

test("empty query scores nothing", () => {
  assert.equal(core.scoreMatch("", "GitHub", "https://github.com/"), 0);
});

/* ------------------------------------------------------------------ */
/* rank                                                                */
/* ------------------------------------------------------------------ */

const candidates = {
  engineName: "DuckDuckGo",
  tabs: [
    { tabId: 4, windowId: 1, title: "GitHub", url: "https://github.com/" },
    { tabId: 9, windowId: 1, title: "Release notes", url: "https://example.com/notes" },
  ],
  bookmarks: [{ title: "GitHub Actions", url: "https://github.com/features/actions" }],
  history: [
    { title: "github.com", url: "https://github.com/" },
    { title: "Unrelated", url: "https://elsewhere.test/" },
  ],
};

test("rank orders address, tabs, bookmarks, history, search", () => {
  const rows = core.rank("github", Object.assign({ directUrl: "https://github.com/" }, candidates));
  const kinds = rows.map((row) => row.kind);
  assert.deepEqual(kinds, ["url", "tab", "bookmark", "search"]);
});

test("an address still offers the web search as the last row", () => {
  const rows = core.rank("example.com", { directUrl: "https://example.com/", engineName: "DuckDuckGo" });
  assert.deepEqual(rows.map((row) => row.kind), ["url", "search"]);
});

test("rank always ends with a search row for plain text", () => {
  const rows = core.rank("how to fix a tv", { engineName: "DuckDuckGo" });
  assert.equal(rows.length, 1);
  assert.equal(rows[0].kind, "search");
  assert.equal(rows[0].query, "how to fix a tv");
  assert.match(rows[0].subtitle, /DuckDuckGo/);
});

test("pages de-duplicate by URL, tabs by tab id", () => {
  const rows = core.rank("github", {
    tabs: [{ tabId: 4, windowId: 1, title: "GitHub", url: "https://github.com/" }],
    history: [
      { title: "GitHub", url: "https://github.com/" },
      { title: "GitHub", url: "https://github.com/" },
    ],
  });
  const kinds = rows.map((row) => row.kind);
  // one "switch to tab" plus one history page, never the same page twice
  assert.equal(kinds.filter((kind) => kind === "tab").length, 1);
  assert.equal(kinds.filter((kind) => kind === "history").length, 1);
});

test("rank never returns more than MAX_ROWS", () => {
  const many = { tabs: [], bookmarks: [], history: [] };
  for (let index = 0; index < 40; index += 1) {
    many.history.push({ title: `match ${index}`, url: `https://e${index}.test/` });
  }
  const rows = core.rank("match", many);
  assert.equal(rows.length, core.MAX_ROWS);
});

test("rank gives every row a unique id and no undefined fields", () => {
  const rows = core.rank("github", Object.assign({ directUrl: "https://github.com/" }, candidates));
  const ids = new Set(rows.map((row) => row.id));
  assert.equal(ids.size, rows.length);
  for (const row of rows) {
    assert.equal(typeof row.title, "string");
    assert.ok(row.title.length > 0, "every row needs a title");
    assert.equal(typeof row.subtitle, "string");
  }
});

test("rank tolerates missing collections", () => {
  const rows = core.rank("x", undefined);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].kind, "search");
});

/* ------------------------------------------------------------------ */
/* the bookmark grid                                                   */
/* ------------------------------------------------------------------ */

test("hostOf strips the www. prefix and refuses to throw", () => {
  assert.equal(core.hostOf("https://www.github.com/a"), "github.com");
  assert.equal(core.hostOf("https://developer.mozilla.org/"), "developer.mozilla.org");
  assert.equal(core.hostOf("not a url"), "");
  assert.equal(core.hostOf(undefined), "");
});

test("hueOf is deterministic and inside the colour wheel", () => {
  assert.equal(core.hueOf("github.com"), core.hueOf("github.com"));
  assert.notEqual(core.hueOf("github.com"), core.hueOf("mozilla.org"));
  for (const text of ["", "a", "https://example.test/", "x".repeat(400)]) {
    const hue = core.hueOf(text);
    assert.ok(Number.isInteger(hue) && hue >= 0 && hue < 360, `hue out of range for ${text}`);
  }
});

test("initialOf uppercases one character and never returns nothing", () => {
  assert.equal(core.initialOf("github"), "G");
  assert.equal(core.initialOf("  mozilla"), "M");
  assert.equal(core.initialOf(""), "?");
  assert.equal(core.initialOf(undefined), "?");
  // A surrogate pair must stay one character, not half of one.
  assert.equal(core.initialOf("🦊 fox"), "🦊");
});

test("toGridItems skips separators and gives untitled bookmarks a name", () => {
  const items = core.toGridItems([
    { id: "1", type: "bookmark", title: "GitHub", url: "https://github.com/" },
    { id: "2", type: "separator" },
    { id: "3", type: "bookmark", title: "", url: "https://www.mozilla.org/en-US/" },
    null,
  ]);
  assert.equal(items.length, 2);
  assert.deepEqual(items.map((item) => item.kind), ["bookmark", "bookmark"]);
  assert.equal(items[0].title, "GitHub");
  assert.equal(items[0].initial, "G");
  assert.equal(items[1].title, "mozilla.org", "a blank title falls back to the host");
  assert.equal(items[1].subtitle, "mozilla.org");
});

test("toGridItems marks folders, counts children and needs no url", () => {
  const items = core.toGridItems([
    {
      id: "f",
      type: "folder",
      title: "Dev",
      children: [
        { id: "a", type: "bookmark", title: "A", url: "https://a.test/" },
        { id: "b", type: "bookmark", title: "B", url: "https://b.test/" },
        { id: "s", type: "separator" },
      ],
    },
  ]);
  assert.equal(items.length, 1);
  assert.equal(items[0].kind, "folder");
  assert.equal(items[0].title, "Dev");
  assert.equal(items[0].url, "");
  assert.equal(items[0].childCount, 3, "the count is raw, the grid decides what to do with it");
  assert.equal(items[0].favicon, "");
});

test("toGridItems keeps the order the toolbar was arranged in", () => {
  const items = core.toGridItems([
    { id: "1", type: "bookmark", title: "Zebra", url: "https://z.test/" },
    { id: "2", type: "bookmark", title: "Apple", url: "https://a.test/" },
  ]);
  assert.deepEqual(items.map((item) => item.title), ["Zebra", "Apple"]);
});

test("toGridItems stops at MAX_TILES and copes with no nodes", () => {
  const many = [];
  for (let index = 0; index < core.MAX_TILES + 20; index += 1) {
    many.push({ id: String(index), type: "bookmark", title: `Site ${index}`, url: `https://s${index}.test/` });
  }
  assert.equal(core.toGridItems(many).length, core.MAX_TILES);
  assert.deepEqual(core.toGridItems([]), []);
  assert.deepEqual(core.toGridItems(undefined), []);
});

test("toGridItems only carries a favicon a node actually has", () => {
  const items = core.toGridItems([
    { id: "1", type: "bookmark", title: "A", url: "https://a.test/", faviconUrl: "data:image/png;base64,AA" },
    { id: "2", type: "bookmark", title: "B", url: "https://b.test/" },
  ]);
  assert.equal(items[0].favicon, "data:image/png;base64,AA");
  assert.equal(items[1].favicon, "", "no favicon means the letter tile, never a network fetch");
});

test("toGridItems gives every tile a stable id and colour", () => {
  const first = core.toGridItems([{ id: "x", type: "bookmark", title: "X", url: "https://www.x.test/" }]);
  const second = core.toGridItems([{ id: "x", type: "bookmark", title: "X", url: "https://x.test/" }]);
  assert.equal(first[0].hue, second[0].hue, "www. must not change the colour");
  assert.equal(first[0].id, "x");
});

/* ------------------------------------------------------------------ */

if (failures.length) {
  for (const failure of failures) console.error("FAIL " + failure);
  console.error(`\n${failures.length} failing, ${checks} passing`);
  process.exit(1);
}
console.log(`ok — ${checks} extension core tests`);
