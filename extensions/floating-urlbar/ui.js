"use strict";
/*
 * (SheepFox) Floating URL Bar — the shared UI.
 *
 * One renderer serves both surfaces:
 *   overlay  — mounted into a closed shadow root on top of the page
 *   window   — the popup window the extension opens when a page cannot host it
 *
 * All it needs from the environment is `browser.runtime.sendMessage`; all the
 * data comes from background.js, so history/bookmark/tab access stays in one
 * privileged place and the content-script surface never has to ask for it.
 *
 * Every string that comes from a page (a tab title, a bookmark title) is set
 * with textContent — never innerHTML — because those are page-controlled.
 */

(function (root) {
  "use strict";
  if (root.SheepFoxBar) return;

  const NS = "http://www.w3.org/2000/svg";
  const api = root.browser || root.chrome;

  const ICON_PATHS = {
    url: [
      "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z",
      "M3.2 12h17.6",
      "M12 3c2.4 2.4 3.7 5.4 3.7 9s-1.3 6.6-3.7 9c-2.4-2.4-3.7-5.4-3.7-9S9.6 5.4 12 3Z",
    ],
    search: ["M10.5 4.2a6.3 6.3 0 1 0 0 12.6 6.3 6.3 0 0 0 0-12.6Z", "m15.3 15.3 4.7 4.7"],
    tab: ["M4.5 6.5h15v11h-15Z", "M4.5 10h15"],
    bookmark: ["m12 4.4 2.3 4.7 5.2.8-3.7 3.6.9 5.1-4.7-2.4-4.7 2.4.9-5.1L4.5 9.9l5.2-.8Z"],
    history: ["M12 7.2V12l3.1 1.9", "M3.8 12a8.2 8.2 0 1 0 2.5-5.9L3.8 8.6", "M3.8 4.4v4.2h4.2"],
  };

  function element(doc, tag, attributes, text) {
    const node = doc.createElement(tag);
    if (attributes) {
      for (const name of Object.keys(attributes)) {
        if (attributes[name] !== undefined && attributes[name] !== null) {
          node.setAttribute(name, String(attributes[name]));
        }
      }
    }
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function icon(doc, kind, className) {
    const node = doc.createElementNS(NS, "svg");
    node.setAttribute("viewBox", "0 0 24 24");
    node.setAttribute("fill", "none");
    node.setAttribute("stroke", "currentColor");
    node.setAttribute("stroke-width", "1.7");
    node.setAttribute("stroke-linecap", "round");
    node.setAttribute("stroke-linejoin", "round");
    node.setAttribute("aria-hidden", "true");
    node.setAttribute("class", className);
    const paths = ICON_PATHS[kind] || ICON_PATHS.search;
    for (const data of paths) {
      const path = doc.createElementNS(NS, "path");
      path.setAttribute("d", data);
      node.appendChild(path);
    }
    return node;
  }

  /**
   * Mount the bar.
   *
   * options:
   *   container   ShadowRoot or element to append into (defaults to body)
   *   doc         the Document that owns the nodes
   *   mode        "overlay" | "window"
   *   target      { tabId, windowId } to navigate when a row is opened
   *   placeholder input placeholder text
   *   onClose     called after the bar removed itself
   *   onHeight    called with the card height whenever the layout changes
   */
  function mount(options) {
    const settings = options || {};
    const doc = settings.doc || root.document;
    const container = settings.container || doc.body;
    const mode = settings.mode === "window" ? "window" : "overlay";
    const target = settings.target || {};
    const onClose = typeof settings.onClose === "function" ? settings.onClose : function () {};
    const onHeight = typeof settings.onHeight === "function" ? settings.onHeight : null;
    const placeholder = settings.placeholder || "Search or enter an address";

    let rows = [];
    let rowNodes = [];
    let selected = -1;
    let sequence = 0;
    let timer = null;
    let destroyed = false;

    const bar = element(doc, "div", {
      class: "sheepfox-bar sheepfox-bar--" + mode,
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "SheepFox floating address bar",
    });

    const card = element(doc, "div", { class: "sheepfox-card" });
    const field = element(doc, "div", { class: "sheepfox-field" });
    const glyph = element(doc, "span", { class: "sheepfox-glyph", "aria-hidden": "true" });
    glyph.appendChild(icon(doc, "url", "sheepfox-glyph-svg"));

    const input = element(doc, "input", {
      class: "sheepfox-input",
      type: "text",
      role: "combobox",
      autocomplete: "off",
      autocapitalize: "off",
      autocorrect: "off",
      spellcheck: "false",
      "aria-autocomplete": "list",
      "aria-expanded": "false",
      "aria-controls": "sheepfox-list",
      "aria-label": "Address or search",
      placeholder: placeholder,
    });

    const key = element(doc, "kbd", { class: "sheepfox-key", "aria-hidden": "true" }, "esc");
    const list = element(doc, "ul", { class: "sheepfox-list", id: "sheepfox-list", role: "listbox", "aria-label": "Results" });
    const footer = element(doc, "div", { class: "sheepfox-footer", "aria-hidden": "true" });
    footer.appendChild(element(doc, "span", null, "↑ ↓ to move"));
    footer.appendChild(element(doc, "span", null, "↵ to open"));
    footer.appendChild(element(doc, "span", null, mode === "window" ? "⌘/Ctrl ↵ new tab" : "⇧↵ new tab"));

    const backdrop = mode === "overlay" ? element(doc, "div", { class: "sheepfox-backdrop" }) : null;
    if (backdrop) {
      backdrop.addEventListener("mousedown", function (event) {
        event.preventDefault();
        close();
      });
    }

    field.appendChild(glyph);
    field.appendChild(input);
    field.appendChild(key);
    card.appendChild(field);
    card.appendChild(list);
    card.appendChild(footer);
    bar.appendChild(card);

    const fragment = doc.createDocumentFragment();
    if (backdrop) fragment.appendChild(backdrop);
    fragment.appendChild(bar);
    container.appendChild(fragment);

    function measure() {
      if (!onHeight || destroyed) return;
      const height = Math.ceil(card.getBoundingClientRect().height);
      if (height > 0) onHeight(height);
    }

    function setSelected(index) {
      if (!rows.length) {
        selected = -1;
        input.removeAttribute("aria-activedescendant");
        return;
      }
      const count = rows.length;
      selected = ((index % count) + count) % count;
      for (let position = 0; position < rowNodes.length; position += 1) {
        rowNodes[position].setAttribute("aria-selected", position === selected ? "true" : "false");
      }
      const active = rowNodes[selected];
      if (!active) return;
      input.setAttribute("aria-activedescendant", active.id);
      active.scrollIntoView({ block: "nearest" });
    }

    function render(nextRows) {
      rows = Array.isArray(nextRows) ? nextRows : [];
      rowNodes = [];
      list.textContent = "";
      const fragmentRows = doc.createDocumentFragment();

      rows.forEach(function (row, index) {
        const item = element(doc, "li", {
          class: "sheepfox-row",
          role: "option",
          id: row.id || "sheepfox-row-" + index,
          "aria-selected": "false",
        });
        item.appendChild(icon(doc, row.kind, "sheepfox-row-glyph"));

        const cell = element(doc, "div", { class: "sheepfox-row-text" });
        cell.appendChild(element(doc, "span", { class: "sheepfox-title" }, row.title || ""));
        cell.appendChild(element(doc, "span", { class: "sheepfox-subtitle" }, row.subtitle || ""));
        item.appendChild(cell);

        // mousedown, not click: the window surface loses focus on blur, and a
        // click that lands after a blur would be swallowed by the closing bar.
        item.addEventListener("mousedown", function (event) {
          if (event.button !== 0) return;
          event.preventDefault();
          setSelected(index);
          void openSelected(event.ctrlKey || event.metaKey || event.shiftKey);
        });
        item.addEventListener("mouseenter", function () {
          setSelected(index);
        });

        fragmentRows.appendChild(item);
        rowNodes.push(item);
      });

      list.appendChild(fragmentRows);
      input.setAttribute("aria-expanded", rows.length ? "true" : "false");
      setSelected(rows.length ? 0 : -1);
      measure();
    }

    async function runQuery(text) {
      const mine = (sequence += 1);
      try {
        const response = await api.runtime.sendMessage({ type: "sheepfox-query", text: text });
        if (destroyed || mine !== sequence) return; // a newer keystroke already answered
        render(response && response.rows);
      } catch (error) {
        if (!destroyed && mine === sequence) render([]);
      }
    }

    function scheduleQuery() {
      root.clearTimeout(timer);
      const text = input.value;
      timer = root.setTimeout(function () {
        void runQuery(text);
      }, 70);
    }

    async function openSelected(newTab) {
      const row = rows[selected];
      if (!row) return;
      try {
        await api.runtime.sendMessage({
          type: "sheepfox-open",
          row: row,
          options: {
            newTab: Boolean(newTab),
            targetTabId: target.tabId || null,
            targetWindowId: target.windowId || null,
          },
        });
      } catch (error) {
        // The background could not navigate (tab closed, permission revoked):
        // leave the bar open so the text is not lost.
        return;
      }
      close();
    }

    function onKeyDown(event) {
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setSelected(selected + 1);
          break;
        case "ArrowUp":
          event.preventDefault();
          setSelected(selected - 1);
          break;
        case "Home":
          if (rows.length) {
            event.preventDefault();
            setSelected(0);
          }
          break;
        case "End":
          if (rows.length) {
            event.preventDefault();
            setSelected(rows.length - 1);
          }
          break;
        case "Tab":
          event.preventDefault();
          setSelected(event.shiftKey ? selected - 1 : selected + 1);
          break;
        case "Enter":
          event.preventDefault();
          void openSelected(event.ctrlKey || event.metaKey || event.shiftKey);
          break;
        case "Escape":
          event.preventDefault();
          event.stopPropagation();
          close();
          break;
        default:
          break;
      }
    }

    function destroy() {
      if (destroyed) return;
      destroyed = true;
      root.clearTimeout(timer);
      if (fragment.parentNode) fragment.parentNode.removeChild(fragment);
      if (bar.parentNode) bar.parentNode.removeChild(bar);
    }

    function close() {
      if (destroyed) return;
      destroy();
      onClose();
    }

    input.addEventListener("keydown", onKeyDown);
    input.addEventListener("input", scheduleQuery);
    input.addEventListener("paste", function () {
      root.setTimeout(scheduleQuery, 0);
    });

    // Start empty: the pill opens as a pill, not a form.
    render([]);

    return {
      element: bar,
      input: input,
      close: close,
      destroy: destroy,
      focus: function () {
        input.focus({ preventScroll: true });
        input.select();
      },
    };
  }

  root.SheepFoxBar = { mount: mount };
})(typeof window !== "undefined" ? window : globalThis);
