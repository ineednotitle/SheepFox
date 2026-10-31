# (SheepFox) Floating URL Bar

A floating, Arc/Zen-style address bar. Press **`Ctrl+Shift+Space`**
(`Command+Shift+Space` on macOS) on any page, type, press `Enter`.

It searches **your open tabs**, **bookmarks**, **history** and the web at once,
in one list; a URL you type is the first row.

```
┌───────────────────────────────────────────────────────────┐
│  🌐  Search or enter an address                    esc     │
├───────────────────────────────────────────────────────────┤
│  ⟳  github.com                              Open address    │
│  ▭  GitHub — pull requests                  Switch to tab   │
│  ★  GitHub Actions                          Bookmark        │
│  🕘  Releases · SheepFox                     History        │
│  🔍  Search for “github”                    DuckDuckGo      │
└───────────────────────────────────────────────────────────┘
```

## What it can and cannot do

**An extension cannot style Firefox's address bar.** WebExtensions get no access
to the browser chrome (`#urlbar`, `#nav-bar`), so no add-on can detach Mozilla's
own bar and float it — that is what SheepFox's `config/chrome/userChrome.css`
does, and it is on by default.

This extension exists for the case where profile CSS is unavailable or unwanted
(a locked-down machine, a profile you would rather not modify, or a floating bar
that also works on `about:` pages). It cannot float the real bar, so it ships its
own surface, in the two ways a WebExtension actually can:

| Surface | When | How it looks |
| :--- | :--- | :--- |
| **In-page overlay** | any `http(s)`/`file` page | a pill centred over the dimmed page, in a closed shadow root |
| **Popup window** | `about:` pages, `addons.mozilla.org`, the PDF viewer, anything that refuses injection | a small borderless window shaped like the pill, which grows as results appear |

The shortcut never silently does nothing: if the overlay cannot be injected, the
window opens instead.

## Install

Release Firefox refuses unsigned extensions, so there are two honest options:

**Try it (no signing, resets on restart)**

1. Open `about:debugging#/runtime/this-firefox`.
2. **Load Temporary Add-on…** and pick `SheepFox-Floating-URL-Bar-<version>.xpi`
   (or this folder's `manifest.json`).

**Keep it (sign it yourself, no cost)**

```bash
npx web-ext sign --channel unlisted \
  --api-key   "$AMO_JWT_ISSUER" \
  --api-secret "$AMO_JWT_SECRET" \
  --source-dir extensions/floating-urlbar
```

`api-key`/`api-secret` come from <https://addons.mozilla.org/developers/addon/api/key/>.
The signed `.xpi` installs like any other add-on and survives restarts.

Build the unsigned `.xpi` yourself with:

```bash
make extension            # -> dist/SheepFox-Floating-URL-Bar-<version>.xpi
make extension-check      # validate manifest + sources only (CI gate)
```

## Permissions, and why each one

| Permission | Why |
| :--- | :--- |
| `activeTab` | inject the overlay into the one tab you pressed the shortcut on |
| `scripting` | the injection itself (on demand — nothing runs on page load) |
| `tabs` | list open tabs by title so "switch to tab" works |
| `history` | match pages you have visited |
| `bookmarks` | match bookmarks |
| `search` | use *your* default search engine rather than a hardcoded one |

There are **no host permissions**, no `content_scripts` in the manifest and no
remote code: until you press the shortcut, the extension does not touch any page.

## What is deliberately not here

- **No telemetry, no analytics, no network requests.** History and bookmarks are
  read locally, per keystroke, and never leave the machine.
- **No search suggestions.** Live suggestions mean sending every keystroke to the
  search engine before you press Enter. Arc does it; this does not.
- **No `javascript:` / `data:` URLs.** A launcher can be handed a URL by a paste,
  so anything that would execute in the address bar is refused by
  `core.js` and covered by tests.
- **No page mutation.** The overlay is removed on close, navigation and
  `pagehide`; the page's own DOM is never modified beyond one host element that
  exists only while the bar is open.

## Layout

```text
extensions/floating-urlbar/
├── manifest.json     MV3, Gecko id floating-urlbar@sheepfox, one command
├── core.js           pure: URL interpretation + result ranking (no browser.*)
├── background.js     shortcut, query pipeline, which surface to use
├── ui.js             shared renderer: list, keyboard, ARIA combobox pattern
├── content.js        in-page surface (closed shadow root, on demand)
├── window.js         window surface (grows to fit the results)
├── styles.js         the stylesheet, as a string (see the note at the top)
├── search.html       the window surface's page
└── icons/bar.svg     toolbar + add-on icon
```

`core.js` has no browser-API dependency on purpose: `tests/extension/core.test.js`
runs it under plain `node` and covers the cases that are easy to get wrong —
`localhost:3000` versus `localhost:` as a scheme, `1.5` versus `example.com`,
ranking order, de-duplication and the row cap.

## Keyboard

| Key | Action |
| :--- | :--- |
| `Ctrl+Shift+Space` | open the bar (remap it in `about:addons` → gear → Manage Extension Shortcuts) |
| `↑` `↓` / `Tab` | move through results |
| `Enter` | open in the current tab (a tab row switches to that tab) |
| `Ctrl`/`⌘` + `Enter` | open in a new tab |
| `Esc` | close |
