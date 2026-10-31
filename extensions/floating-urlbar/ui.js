"use strict";
/*
 * (SheepFox) Floating URL Bar — the shared UI.
 *
 * One renderer serves both surfaces:
 *   overlay  — mounted into a closed shadow root on top of the page
 *   window   — the popup window the extension opens when a page cannot host it
 *
 * Two views live in the same card:
 *   grid — the empty state: your bookmarks-toolbar items as tiles, folders open
 *          in place with a Back row (Arc's bookmark shelf, Zen's empty page)
 *   list — what you get while typing: address, open tabs, bookmarks, history,
 *          then the web search
 *
 * All it needs from the environment is `browser.runtime.sendMessage`; all the
 * data comes from background.js, so history/bookmark/tab access stays in one
 * privileged place and the content-script surface never has to ask for it.
 *
 * Every string that comes from a page or a bookmark (a tab title, a bookmark
 * name) is set with textContent — never innerHTML — because those are
 * page-controlled.
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
    folder: ["M3.5 7.5a2 2 0 0 1 2-2h3.3l1.8 2.2h7.9a2 2 0 0 1 2 2v7.8a2 2 0 0 1-2 2H5.5a2 2 0 0 1-2-2Z"],
    back: ["M14.5 6.5 9 12l5.5 5.5"],
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

    let view = "grid";
    let options_ = [];
    let optionNodes = [];
    let selected = -1;
    let folderStack = [];
    let folder = { id: null, title: "" };
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
      "aria-controls": "sheepfox-grid",
      "aria-label": "Address or search",
      placeholder: placeholder,
    });

    const key = element(doc, "kbd", { class: "sheepfox-key", "aria-hidden": "true" }, "esc");

    const crumb = element(doc, "div", { class: "sheepfox-crumb" });
    const back = element(doc, "button", { class: "sheepfox-back", type: "button" });
    back.appendChild(icon(doc, "back", "sheepfox-back-glyph"));
    back.appendChild(element(doc, "span", null, "Back"));
    const crumbLabel = element(doc, "span", { class: "sheepfox-crumb-label" });
    crumb.appendChild(back);
    crumb.appendChild(crumbLabel);

    const grid = element(doc, "div", { class: "sheepfox-grid", id: "sheepfox-grid", role: "listbox", "aria-label": "Bookmarks" });
    const list = element(doc, "ul", { class: "sheepfox-list", id: "sheepfox-list", role: "listbox", "aria-label": "Results" });

    const footer = element(doc, "div", { class: "sheepfox-footer", "aria-hidden": "true" });

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
    card.appendChild(crumb);
    card.appendChild(grid);
    card.appendChild(list);
    card.appendChild(footer);
    bar.appendChild(card);

    const fragment = doc.createDocumentFragment();
    if (backdrop) fragment.appendChild(backdrop);
    fragment.appendChild(bar);
    container.appendChild(fragment);
    measure();

    /* ---------------------------------------------------------------- */
    /* layout helpers                                                    */
    /* ---------------------------------------------------------------- */

    function measure() {
      if (!onHeight || destroyed) return;
      const height = Math.ceil(card.getBoundingClientRect().height);
      if (height > 0) onHeight(height);
    }

    function columns() {
      if (view !== "grid" || typeof root.getComputedStyle !== "function") return 1;
      const template = root.getComputedStyle(grid).gridTemplateColumns || "";
      const count = template.split(" ").filter(Boolean).length;
      return count > 0 ? count : 1;
    }

    function setFooter() {
      footer.textContent = "";
      const hints =
        view === "grid"
          ? folderStack.length
            ? ["← back", "↵ open", "esc back"]
            : ["↑ ↓ ← → move", "↵ open", "type to search"]
          : ["↑ ↓ move", "↵ open", mode === "window" ? "⌘/Ctrl ↵ new tab" : "⇧↵ new tab"];
      for (const hint of hints) footer.appendChild(element(doc, "span", null, hint));
    }

    function setView(next) {
      view = next;
      const isGrid = view === "grid";
      grid.hidden = !isGrid;
      list.hidden = isGrid;
      crumb.hidden = !isGrid || folderStack.length === 0;
      input.setAttribute("aria-controls", isGrid ? "sheepfox-grid" : "sheepfox-list");
      setFooter();
    }

    /* ---------------------------------------------------------------- */
    /* selection                                                         */
    /* ---------------------------------------------------------------- */

    function setSelected(index) {
      if (!options_.length) {
        selected = -1;
        input.removeAttribute("aria-activedescendant");
        return;
      }
      const count = options_.length;
      selected = ((index % count) + count) % count;
      for (let position = 0; position < optionNodes.length; position += 1) {
        optionNodes[position].setAttribute("aria-selected", position === selected ? "true" : "false");
      }
      const active = optionNodes[selected];
      if (!active) return;
      input.setAttribute("aria-activedescendant", active.id);
      active.scrollIntoView({ block: "nearest" });
    }

    /* ---------------------------------------------------------------- */
    /* rendering                                                         */
    /* ---------------------------------------------------------------- */

    function tile(item, index) {
      const node = element(doc, "div", {
        class: "sheepfox-tile",
        role: "option",
        id: item.id || "sheepfox-tile-" + index,
        "aria-selected": "false",
        title: item.url || item.title || "",
      });

      const glyphNode = element(doc, "span", { class: "sheepfox-tile-glyph", "aria-hidden": "true" });
      if (item.kind === "folder") {
        glyphNode.appendChild(icon(doc, "folder", "sheepfox-tile-icon"));
        glyphNode.classList.add("sheepfox-tile-glyph--folder");
      } else {
        glyphNode.textContent = item.initial || "?";
        glyphNode.style.setProperty("--sf-tile-hue", String(item.hue || 0));
        if (item.favicon) {
          // The letter stays underneath: if the icon 404s or the page's CSP
          // blocks it, removing the image leaves a usable tile rather than a
          // blank one.
          const image = element(doc, "img", {
            class: "sheepfox-tile-img",
            src: item.favicon,
            alt: "",
            loading: "lazy",
            referrerpolicy: "no-referrer",
          });
          image.addEventListener("error", function () {
            image.remove();
          });
          glyphNode.appendChild(image);
        }
      }
      node.appendChild(glyphNode);
      node.appendChild(element(doc, "span", { class: "sheepfox-tile-title" }, item.title || ""));
      if (item.kind === "folder" && item.childCount) {
        node.appendChild(element(doc, "span", { class: "sheepfox-tile-count" }, String(item.childCount)));
      }
      bind(node, index);
      return node;
    }

    function row(item, index) {
      const node = element(doc, "li", {
        class: "sheepfox-row",
        role: "option",
        id: item.id || "sheepfox-row-" + index,
        "aria-selected": "false",
        title: item.url || item.title || "",
      });
      node.appendChild(icon(doc, item.kind, "sheepfox-row-glyph"));

      const cell = element(doc, "div", { class: "sheepfox-row-text" });
      cell.appendChild(element(doc, "span", { class: "sheepfox-title" }, item.title || ""));
      cell.appendChild(element(doc, "span", { class: "sheepfox-subtitle" }, item.subtitle || ""));
      node.appendChild(cell);
      bind(node, index);
      return node;
    }

    function bind(node, index) {
      // mousedown, not click: the window surface loses focus on blur, and a
      // click that lands after a blur would be swallowed by the closing bar.
      node.addEventListener("mousedown", function (event) {
        if (event.button !== 0) return;
        event.preventDefault();
        setSelected(index);
        void activate(event.ctrlKey || event.metaKey || event.shiftKey);
      });
      node.addEventListener("mouseenter", function () {
        setSelected(index);
      });
    }

    function renderOptions(next, nextView) {
      options_ = Array.isArray(next) ? next : [];
      optionNodes = [];
      setView(nextView || view);

      const host = view === "grid" ? grid : list;
      // Empty both: a hidden list must not keep yesterday's rows around, and
      // the live region a screen reader reads is whichever one is visible.
      grid.textContent = "";
      list.textContent = "";
      const batch = doc.createDocumentFragment();

      optionNodes = options_.map(function (item, index) {
        const node = view === "grid" ? tile(item, index) : row(item, index);
        batch.appendChild(node);
        return node;
      });

      host.appendChild(batch);

      input.setAttribute("aria-expanded", options_.length ? "true" : "false");
      if (!options_.length) {
        host.appendChild(
          element(
            doc,
            view === "grid" ? "p" : "li",
            { class: "sheepfox-empty", role: "presentation" },
            view === "grid" ? "No bookmarks in your toolbar yet." : "No matches."
          )
        );
      }
      measure();
      setSelected(options_.length ? 0 : -1);
    }

    /* ---------------------------------------------------------------- */
    /* data                                                              */
    /* ---------------------------------------------------------------- */

    async function loadBookmarks(folderId) {
      const mine = (sequence += 1);
      setView("grid");
      try {
        const payload = await api.runtime.sendMessage({ type: "sheepfox-bookmarks", folderId: folderId || null });
        if (destroyed || mine !== sequence) return;
        folder = {
          id: payload && payload.folderId ? payload.folderId : null,
          title: (payload && payload.title) || "Bookmarks",
        };
        crumbLabel.textContent = folder.title;
        renderOptions((payload && payload.items) || [], "grid");
      } catch (error) {
        if (destroyed || mine !== sequence) return;
        renderOptions([], "grid");
      }
    }

    async function runQuery(text) {
      const mine = (sequence += 1);
      try {
        const response = await api.runtime.sendMessage({ type: "sheepfox-query", text: text });
        if (destroyed || mine !== sequence) return; // a newer keystroke already answered
        renderOptions((response && response.rows) || [], "list");
      } catch (error) {
        if (!destroyed && mine === sequence) renderOptions([], "list");
      }
    }

    function scheduleQuery() {
      root.clearTimeout(timer);
      const text = input.value;
      timer = root.setTimeout(function () {
        void runQuery(text);
      }, 70);
    }

    /* ---------------------------------------------------------------- */
    /* actions                                                           */
    /* ---------------------------------------------------------------- */

    function openFolder(item) {
      folderStack.push({ id: folder.id, title: folder.title });
      void loadBookmarks(item.id);
    }

    function goBack() {
      if (!folderStack.length) return false;
      const previous = folderStack.pop();
      void loadBookmarks(previous ? previous.id : null);
      return true;
    }

    async function openItem(item, newTab) {
      if (!item) return;
      if (item.kind === "folder") {
        openFolder(item);
        return;
      }
      try {
        await api.runtime.sendMessage({
          type: "sheepfox-open",
          row: item,
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

    function activate(newTab) {
      return openItem(options_[selected], newTab);
    }

    /* ---------------------------------------------------------------- */
    /* events                                                            */
    /* ---------------------------------------------------------------- */

    function onKeyDown(event) {
      const step = view === "grid" ? columns() : 1;
      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setSelected(selected + step);
          break;
        case "ArrowUp":
          event.preventDefault();
          setSelected(selected - step);
          break;
        case "ArrowRight":
          if (view !== "grid") break;
          event.preventDefault();
          setSelected(selected + 1);
          break;
        case "ArrowLeft":
          if (view !== "grid") break;
          event.preventDefault();
          setSelected(selected - 1);
          break;
        case "Home":
          if (options_.length) {
            event.preventDefault();
            setSelected(0);
          }
          break;
        case "End":
          if (options_.length) {
            event.preventDefault();
            setSelected(options_.length - 1);
          }
          break;
        case "Tab":
          event.preventDefault();
          setSelected(event.shiftKey ? selected - 1 : selected + 1);
          break;
        case "Enter":
          event.preventDefault();
          void activate(event.ctrlKey || event.metaKey || event.shiftKey);
          break;
        case "Escape":
          event.preventDefault();
          event.stopPropagation();
          // Inside a folder, Escape means "up one level", not "throw it away".
          if (view === "grid" && goBack()) break;
          close();
          break;
        case "Backspace":
          // Only when the field is already empty: "up" without reaching for Esc.
          if (view === "grid" && !input.value && goBack()) event.preventDefault();
          break;
        default:
          break;
      }
    }

    function onInput() {
      if (!input.value.trim()) {
        root.clearTimeout(timer);
        void loadBookmarks(folder.id);
        return;
      }
      scheduleQuery();
    }

    back.addEventListener("mousedown", function (event) {
      event.preventDefault();
      goBack();
    });

    input.addEventListener("keydown", onKeyDown);
    input.addEventListener("input", onInput);
    input.addEventListener("paste", function () {
      root.setTimeout(onInput, 0);
    });

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

    // Open on the bookmark grid: the pill shows your shelf before you type.
    setView("grid");
    setFooter();
    void loadBookmarks(null);

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
