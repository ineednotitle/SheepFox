"use strict";
/*
 * DOM-level tests for extensions/floating-urlbar/ui.js.
 *
 * core.js is pure and tested without a browser; ui.js builds real elements, and
 * the parts most likely to break are exactly the ones a browser would be needed
 * to notice: does typing produce rows, does the keyboard move the selection, is
 * a page-controlled title inserted as text rather than markup, does closing
 * remove the bar.
 *
 * Requires jsdom:
 *   npm install --prefix tests/extension
 *   node tests/extension/ui.test.js
 *
 * Without jsdom the file exits 0 with a "skipped" line, so a checkout that has
 * not installed the optional dev dependency is not a failure.
 */

const path = require("node:path");
const fs = require("node:fs");

const EXT = path.join(__dirname, "..", "..", "extensions", "floating-urlbar");

let JSDOM;
try {
  ({ JSDOM } = require("jsdom"));
} catch (error) {
  console.log("skipped — jsdom is not installed (npm install --prefix tests/extension)");
  process.exit(0);
}

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

function assert(condition, message) {
  if (!condition) throw new Error(message || "assertion failed");
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message || "mismatch"}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  }
}

const tick = (ms) => new Promise((resolve) => setTimeout(resolve, ms || 0));

/** A window with styles.js + ui.js evaluated in it and a recording API stub. */
function environment() {
  // runScripts: "outside-only" is what makes window.eval() run *inside* the
  // jsdom window - without it the extension scripts would execute in node and
  // define themselves on the wrong global.
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    pretendToBeVisual: true,
    runScripts: "outside-only",
  });
  const { window } = dom;

  // jsdom does not implement layout APIs the bar calls.
  window.HTMLElement.prototype.scrollIntoView = function scrollIntoView() {};

  const sent = [];
  let responder = function () {
    return { rows: [] };
  };

  window.browser = {
    runtime: {
      sendMessage: async function (message) {
        sent.push(message);
        if (message.type === "sheepfox-query") return responder(message.text);
        return { ok: true };
      },
    },
  };

  for (const file of ["styles.js", "ui.js"]) {
    window.eval(fs.readFileSync(path.join(EXT, file), "utf8"));
  }

  return {
    window,
    document: window.document,
    sent,
    respondWith(fn) {
      responder = fn;
    },
    mount(options) {
      const merged = Object.assign({ container: window.document.body, doc: window.document, mode: "overlay" }, options);
      return window.SheepFoxBar.mount(merged);
    },
  };
}

function rows(count) {
  const output = [];
  for (let index = 0; index < count; index += 1) {
    output.push({
      id: `sheepfox-row-${index}`,
      kind: index === 0 ? "url" : "history",
      title: `Result <b>${index}</b>`,
      subtitle: `https://example.test/${index}`,
      url: `https://example.test/${index}`,
    });
  }
  return output;
}

async function type(env, text) {
  const input = env.document.querySelector(".sheepfox-input");
  input.value = text;
  input.dispatchEvent(new env.window.Event("input", { bubbles: true }));
  await tick(140); // longer than the 70 ms debounce
}

async function main() {
  await test("mounts a dialog with the ARIA combobox contract", () => {
    const env = environment();
    const bar = env.mount({ mode: "overlay" });
    const dialog = env.document.querySelector(".sheepfox-bar--overlay");
    assert(dialog, "the overlay bar was not mounted");
    assertEqual(dialog.getAttribute("role"), "dialog");
    assert(env.document.querySelector(".sheepfox-backdrop"), "the overlay needs a backdrop");

    const input = env.document.querySelector(".sheepfox-input");
    assertEqual(input.getAttribute("role"), "combobox");
    assertEqual(input.getAttribute("aria-controls"), "sheepfox-list");
    assertEqual(input.getAttribute("aria-expanded"), "false");
    assertEqual(env.document.querySelector(".sheepfox-list").getAttribute("role"), "listbox");
    bar.destroy();
  });

  await test("window mode has no backdrop", () => {
    const env = environment();
    const bar = env.mount({ mode: "window" });
    assertEqual(env.document.querySelectorAll(".sheepfox-bar--window").length, 1);
    assertEqual(env.document.querySelectorAll(".sheepfox-backdrop").length, 0);
    bar.destroy();
  });

  await test("typing asks the background and renders the rows as text", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(3) }));
    const bar = env.mount();

    await type(env, "exa");
    const sentQuery = env.sent.find((message) => message.type === "sheepfox-query");
    assert(sentQuery, "no query was sent");
    assertEqual(sentQuery.text, "exa");

    const items = env.document.querySelectorAll(".sheepfox-row");
    assertEqual(items.length, 3);
    assertEqual(env.document.querySelector(".sheepfox-input").getAttribute("aria-expanded"), "true");
    // Titles are rendered as text: "<b>" must not become an element.
    assertEqual(items[0].querySelectorAll("b").length, 0, "row titles must not be parsed as HTML");
    assertEqual(items[0].querySelector(".sheepfox-title").textContent, "Result <b>0</b>");
    bar.destroy();
  });

  await test("arrow keys move the selection and wrap", () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(3) }));
    const bar = env.mount({ mode: "overlay" });

    return type(env, "exa").then(() => {
      const input = env.document.querySelector(".sheepfox-input");
      const items = () => Array.from(env.document.querySelectorAll(".sheepfox-row"));
      assertEqual(items()[0].getAttribute("aria-selected"), "true");
      assertEqual(input.getAttribute("aria-activedescendant"), items()[0].id);

      input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
      assertEqual(items()[1].getAttribute("aria-selected"), "true");
      assertEqual(items()[0].getAttribute("aria-selected"), "false");

      input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
      input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
      assertEqual(items()[2].getAttribute("aria-selected"), "true", "selection must wrap to the last row");
      bar.destroy();
    });
  });

  await test("Enter opens the selected row, then closes", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(2) }));
    let closed = 0;
    const bar = env.mount({ onClose: () => { closed += 1; } });

    await type(env, "open me");
    const input = env.document.querySelector(".sheepfox-input");
    input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await tick();

    const opened = env.sent.find((message) => message.type === "sheepfox-open");
    assert(opened, "Enter did not send sheepfox-open");
    assertEqual(opened.row.url, "https://example.test/1", "the wrong row was opened");
    assertEqual(opened.options.newTab, false);
    assertEqual(closed, 1, "the bar must close after opening");
    assertEqual(env.document.querySelectorAll(".sheepfox-bar").length, 0, "the DOM was not cleaned up");
    bar.destroy();
  });

  await test("Ctrl/Cmd+Enter opens in a new tab", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(1) }));
    const bar = env.mount();

    await type(env, "new tab");
    const input = env.document.querySelector(".sheepfox-input");
    input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true }));
    await tick();

    const opened = env.sent.find((message) => message.type === "sheepfox-open");
    assertEqual(opened.options.newTab, true);
    bar.destroy();
  });

  await test("Escape closes without opening anything", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(2) }));
    let closed = 0;
    const bar = env.mount({ onClose: () => { closed += 1; } });

    await type(env, "escape me");
    const input = env.document.querySelector(".sheepfox-input");
    input.dispatchEvent(new env.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await tick();

    assertEqual(closed, 1);
    assert(!env.sent.some((message) => message.type === "sheepfox-open"), "Escape must not navigate");
    assertEqual(env.document.querySelectorAll(".sheepfox-bar").length, 0);
    bar.destroy();
  });

  await test("clicking a row opens it", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: rows(3) }));
    const bar = env.mount();

    await type(env, "click me");
    const item = env.document.querySelectorAll(".sheepfox-row")[2];
    const event = new env.window.MouseEvent("mousedown", { bubbles: true, button: 0 });
    item.dispatchEvent(event);
    await tick();

    const opened = env.sent.find((message) => message.type === "sheepfox-open");
    assert(opened, "clicking a row did nothing");
    assertEqual(opened.row.url, "https://example.test/2");
    bar.destroy();
  });

  await test("an empty result set collapses the list", async () => {
    const env = environment();
    env.respondWith(() => ({ rows: [] }));
    const bar = env.mount();

    await type(env, "zzzz");
    assertEqual(env.document.querySelectorAll(".sheepfox-row").length, 0);
    assertEqual(env.document.querySelector(".sheepfox-input").getAttribute("aria-expanded"), "false");
    assertEqual(env.document.querySelector(".sheepfox-input").hasAttribute("aria-activedescendant"), false);
    bar.destroy();
  });

  await test("a failed query does not throw and does not keep stale rows", async () => {
    const env = environment();
    env.respondWith(() => {
      throw new Error("background gone");
    });
    const bar = env.mount();

    await type(env, "boom");
    assertEqual(env.document.querySelectorAll(".sheepfox-row").length, 0);
    bar.destroy();
  });

  await test("window mode reports its height so the window can grow", async () => {
    const env = environment();
    const heights = [];
    env.window.HTMLElement.prototype.getBoundingClientRect = function bounding() {
      return { height: 112, width: 640, top: 0, left: 0, right: 640, bottom: 112 };
    };
    const bar = env.mount({ mode: "window", onHeight: (height) => heights.push(height) });
    assert(heights.length > 0, "onHeight was never called");
    assertEqual(heights[0], 112);
    bar.destroy();
  });

  await test("a slow, older response cannot overwrite a newer one", async () => {
    const env = environment();
    env.respondWith((text) =>
      // "a" answers late with three rows; "ab" answers at once with one row.
      text === "a"
        ? new Promise((resolve) => setTimeout(() => resolve({ rows: rows(3) }), 160))
        : { rows: rows(1) }
    );
    const bar = env.mount();
    const input = env.document.querySelector(".sheepfox-input");
    const typeValue = (value) => {
      input.value = value;
      input.dispatchEvent(new env.window.Event("input", { bubbles: true }));
    };

    typeValue("a");
    await tick(90); // the first (slow) query is now in flight
    typeValue("ab");
    await tick(120); // the second query has answered
    assertEqual(env.document.querySelectorAll(".sheepfox-row").length, 1, "newer result must render first");

    await tick(200); // the stale answer arrives late and must be ignored
    assertEqual(env.document.querySelectorAll(".sheepfox-row").length, 1, "a stale response overwrote the list");
    bar.destroy();
  });

  if (failures.length) {
    for (const failure of failures) console.error("FAIL " + failure);
    console.error(`\n${failures.length} failing, ${checks} passing`);
    process.exit(1);
  }
  console.log(`ok — ${checks} extension ui tests`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
