"use strict";
/*
 * Tests for extensions/floating-urlbar/background.js.
 *
 * background.js is the only file that talks to privileged APIs, so it is loaded
 * into a node `vm` context with a stubbed `browser` object. That is enough to
 * pin down the parts that would otherwise only be testable by clicking around:
 * which bookmark tree it reads, what it sends the UI, and whether the query
 * pipeline still orders rows the way the core says it should.
 *
 * Run: node tests/extension/background.test.js
 */

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const EXT = path.join(__dirname, "..", "..", "extensions", "floating-urlbar");

let checks = 0;
const failures = [];

async function test(name, body) {
  try {
    await body();
    checks += 1;
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
  }
}

/** Load core.js + background.js into a fresh context with a fake browser. */
function load(trees) {
  const calls = [];
  const listeners = { command: null, action: null, message: null };

  const browser = {
    commands: { onCommand: { addListener: (fn) => { listeners.command = fn; } } },
    action: { onClicked: { addListener: (fn) => { listeners.action = fn; } } },
    runtime: {
      onMessage: { addListener: (fn) => { listeners.message = fn; } },
      getURL: (page) => "moz-extension://sheepfox/" + page,
    },
    bookmarks: {
      getSubTree: async (id) => {
        calls.push(["getSubTree", id]);
        if (!trees[id]) throw new Error("no such folder: " + id);
        return [trees[id]];
      },
      search: async (query) => {
        calls.push(["search", query.query]);
        return [];
      },
    },
    tabs: {
      query: async () => [],
      update: async () => {},
      create: async () => {},
      sendMessage: async () => {},
    },
    history: { search: async () => [] },
    search: {
      getDefault: async () => ({ name: "DuckDuckGo" }),
      search: async () => {},
    },
    windows: { update: async () => {}, getCurrent: async () => ({ width: 1280, height: 800 }) },
    scripting: { executeScript: async () => {} },
  };

  const sandbox = { browser, console, URL, URLSearchParams, setTimeout, clearTimeout, Promise };
  sandbox.globalThis = sandbox;
  vm.createContext(sandbox);
  for (const file of ["core.js", "background.js"]) {
    vm.runInContext(fs.readFileSync(path.join(EXT, file), "utf8"), sandbox, { filename: file });
  }
  return { listeners, calls };
}

/**
 * Values built inside the vm belong to another realm, so an array from there is
 * not `deepEqual` to a local literal. Compare plain JSON copies instead.
 */
const plain = (value) => JSON.parse(JSON.stringify(value));

const TOOLBAR = {
  id: "toolbar_____",
  type: "folder",
  title: "Bookmarks Toolbar",
  children: [
    { id: "b1", type: "bookmark", title: "GitHub", url: "https://github.com/" },
    { id: "s1", type: "separator" },
    {
      id: "f1",
      type: "folder",
      title: "Dev",
      children: [
        { id: "b2", type: "bookmark", title: "MDN", url: "https://developer.mozilla.org/" },
        { id: "b3", type: "bookmark", title: "Hooks", url: "https://react.dev/" },
      ],
    },
  ],
};

const DEV = {
  id: "f1",
  type: "folder",
  title: "Dev",
  parentId: "toolbar_____",
  children: [
    { id: "b2", type: "bookmark", title: "MDN", url: "https://developer.mozilla.org/" },
    { id: "b3", type: "bookmark", title: "Hooks", url: "https://react.dev/" },
  ],
};

async function main() {
  await test("the shelf starts at the toolbar root, addressed by its fixed id", async () => {
    const { listeners, calls } = load({ toolbar_____: TOOLBAR, f1: DEV });
    const level = await listeners.message({ type: "sheepfox-bookmarks", folderId: null }, {});

    assert.deepEqual(plain(calls[0]), ["getSubTree", "toolbar_____"], "Firefox's toolbar root id is fixed");
    assert.equal(level.folderId, "toolbar_____");
    assert.equal(level.title, "Bookmarks Toolbar");
    assert.equal(level.atRoot, true);

    // Separators never reach the view, and folders are marked as folders.
    assert.equal(level.items.length, 2);
    assert.deepEqual(plain(level.items.map((item) => item.kind)), ["bookmark", "folder"]);
    assert.equal(level.items[0].initial, "G");
    assert.equal(level.items[1].childCount, 2);
    assert.equal(level.items[1].url, "");
  });

  await test("a folder request reads that folder only", async () => {
    const { listeners, calls } = load({ toolbar_____: TOOLBAR, f1: DEV });
    const level = await listeners.message({ type: "sheepfox-bookmarks", folderId: "f1" }, {});

    assert.deepEqual(plain(calls[0]), ["getSubTree", "f1"]);
    assert.equal(level.folderId, "f1");
    assert.equal(level.title, "Dev");
    assert.equal(level.atRoot, false);
    assert.deepEqual(plain(level.items.map((item) => item.title)), ["MDN", "Hooks"]);
  });

  await test("an unreadable folder is an empty shelf, not an exception", async () => {
    const { listeners } = load({});
    const level = await listeners.message({ type: "sheepfox-bookmarks", folderId: "gone" }, {});
    assert.deepEqual(plain(level.items), []);
    assert.equal(level.folderId, null);
    assert.equal(level.atRoot, true);
  });

  await test("the query pipeline keeps the address first and the search last", async () => {
    const { listeners, calls } = load({ toolbar_____: TOOLBAR });
    const answer = await listeners.message({ type: "sheepfox-query", text: "example.com" }, {});

    assert(calls.some((call) => call[0] === "search"), "bookmarks are searched too");
    assert.equal(answer.engine, "DuckDuckGo");
    assert.equal(answer.rows[0].kind, "url");
    assert.equal(answer.rows[0].url, "https://example.com/");
    assert.equal(answer.rows[answer.rows.length - 1].kind, "search");
  });

  await test("an empty query asks for nothing", async () => {
    const { listeners, calls } = load({ toolbar_____: TOOLBAR });
    const answer = await listeners.message({ type: "sheepfox-query", text: "   " }, {});
    assert.deepEqual(plain(answer.rows), []);
    assert.equal(calls.length, 0);
  });

  await test("unknown messages are ignored instead of answered", async () => {
    const { listeners } = load({ toolbar_____: TOOLBAR });
    assert.equal(listeners.message({ type: "not-ours" }, {}), undefined);
    assert.equal(listeners.message(null, {}), undefined);
    assert.equal(listeners.message({}, {}), undefined);
  });

  await test("the shortcut is wired to the one command the manifest declares", async () => {
    const { listeners } = load({ toolbar_____: TOOLBAR });
    assert.equal(typeof listeners.command, "function");
    assert.equal(typeof listeners.action, "function");
    // The handler must tolerate a command it does not own.
    assert.equal(listeners.command("something-else"), undefined);
  });

  if (failures.length) {
    for (const failure of failures) console.error("FAIL " + failure);
    console.error(`\n${failures.length} failing, ${checks} passing`);
    process.exit(1);
  }
  console.log(`ok — ${checks} extension background tests`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
