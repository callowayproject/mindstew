# Rendering Mermaid diagrams in QtWebEngine (chat + Preview panes)

Research note for issue #25 (map: issue #1). Question: how should Mermaid
diagrams render in the chat and Preview panes of a PySide6 app using
QtWebEngine on macOS? No code was written; this is a recommendation note.

Source convention: every claim carries its URL. Items marked **UNVERIFIED**
could not be confirmed from a primary source in this pass (the Qt for Python
class pages are JS-rendered and unfetchable; Qt C++ docs at
`doc-snapshots.qt.io/qtwebengine/` were used instead, the PySide6 API mirrors
them 1:1 but that mirroring is itself an assumption).

## TL;DR recommendations

1. **Bundle** `mermaid.min.js` (single classic script, no chunk loading) pinned
   to an exact version (12.1.0 was `latest` on 2026-10-03), inject it with
   `<script src>` from a local file next to the HTML, loaded via
   `QWebEnginePage.setHtml(html, QUrl.fromLocalFile(<dir>/))` or, better,
   `QWebEngineView.load(file://.../shell.html)`. Ship as a data file in the
   PyInstaller onedir. Cost: ~5.5 MB (≈1.6 MB gzipped, irrelevant on disk).
2. **Security**: `securityLevel: "strict"` (default) plus defence in depth on
   the Qt side: dedicated off-the-record profile, no remote access, a
   `<meta>` CSP of `default-src 'none'` + local script/style/img-data,
   `acceptNavigationRequest` that rejects everything but the initial load, and
   a URL request interceptor blocking all non-`file:`/`data:` schemes. Do not
   use `sandbox` level as the primary mitigation.
3. **Theming**: `theme: "default"` / `"dark"` chosen from the app's palette
   (not from CSS media query), re-`initialize` + re-render all diagrams on
   appearance change (Qt `QStyleHints.colorSchemeChanged`). Keep source text
   per diagram so re-render is cheap.
4. **Errors**: `suppressErrorRendering: true`, call `mermaid.parse(src,
   {suppressErrors:true})` first, then `mermaid.render` in try/catch; on
   failure show the source as a code block with a one-line message. While
   streaming, render only when a fence is closed (or debounce and keep the last
   good SVG).
5. **llm_wiki** (the upstream) does this in React with `securityLevel:
   "strict"`, `suppressErrorRendering: true`, a silenced parse error handler,
   off-screen render, lazy IntersectionObserver render, error card; it has no
   dark-theme switch. Details in section 5.

## 1. Bundling mermaid.js offline

### Which dist file and version

- Mermaid docs name two supported forms: `mermaid.esm.min.mjs` (ESM, the
  documented/recommended one) and `mermaid.min.js` (traditional script tag).
  Source: https://mermaid.js.org/config/usage.html
- Measured on the jsDelivr package listing for `mermaid@12.1.0` (latest at
  time of writing; license MIT per the npm registry):
  `dist/mermaid.min.js` = 5,493,176 bytes (gzip ≈ 1.57 MB, measured locally);
  `dist/mermaid.esm.min.mjs` = 30,936 bytes. Sources:
  https://data.jsdelivr.com/v1/packages/npm/mermaid@12.1.0 ,
  https://registry.npmjs.org/mermaid/latest
- The ESM entry is only ~31 KB because it lazy-loads diagram code from a
  `chunks/` directory (inference from the size gap and the esm "min" build
  shape; the chunk directory size was **not measured**). That needs a
  directory of many files and dynamic `import()` over `file://`, which
  Chromium restricts for module scripts (module scripts require CORS-valid
  origins; **UNVERIFIED** for Qt `file://` specifically). The single-file
  `mermaid.min.js` avoids both issues. Recommendation: use `mermaid.min.js`
  (it exposes a global `mermaid`).
- Pin an exact version in a `scripts/` or `vendor/` step; do not use the
  npm unpacked tree (the package unpacks to ~122 MB incl. maps, per the npm
  registry `unpackedSize`; only ship `mermaid.min.js`, not the `.map`, which
  is 19 MB).

### Loading into QWebEngineView

Options, in order of preference:

- **A. Static shell HTML + local file URL (recommended).** Ship
  `web/mermaid-shell.html` and `web/mermaid.min.js` as app data; load with
  `view.load(QUrl.fromLocalFile(shell_path))`. The page references
  `<script src="mermaid.min.js">`. Diagram sources are then pushed with
  `page.runJavaScript(...)` (or `QWebChannel`). Avoids the `setHtml` size
  cap and keeps the origin a stable `file://`. `runJavaScript` runs in a
  script world and returns QVariant-able values only (no Promises), so
  render results should be posted back via `QWebChannel`/DOM, not return
  values. Source: https://doc-snapshots.qt.io/qtwebengine/qwebenginepage.html
- **B. `setHtml(html, baseUrl)`**. Works with `baseUrl=QUrl.fromLocalFile(".../")`
  so `<script src="mermaid.min.js">` resolves, but "the maximum size of the
  percent encoded content is 2 megabytes minus 30 bytes", so the 5.5 MB script
  must never be inlined into the HTML string. Same source as above. Local
  documents can access other local URLs by default
  (`LocalContentCanAccessFileUrls`, default enabled), which is what makes the
  relative script work. Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebenginesettings.html
- **C. qrc / custom scheme.** A Qt resource would need `pyside6-rcc` of 5.5 MB
  into a Python module (slow import, big .py); a custom scheme needs
  `QWebEngineUrlScheme.registerScheme()` at startup plus
  `installUrlSchemeHandler()`. Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebengineprofile.html . This is
  the "most locked-down" option (no `file://` access at all) but is more
  code. Worth it only if we later want to remove `LocalContentCanAccessFileUrls`
  entirely. **Not required for v1.**
- Pane model: a single `QWebEngineView` per pane that hosts the whole markdown
  rendering? Or one view per diagram? Not decided here (outside scope);
  note only that each QWebEngineView carries a Chromium renderer cost, so
  per-diagram views in a long chat are expensive (**UNVERIFIED**
  qualitative; not measured).

### PyInstaller onedir

- Add the web assets as data files (`--add-data "web:web"` or the spec
  `datas=`), resolve at runtime via `sys._MEIPASS` / `Path(__file__)`.
  Source: https://pyinstaller.org/en/stable/runtime-information.html
  (general PyInstaller guidance; not re-fetched in this pass, **UNVERIFIED**
  in this session).
- PySide6 ships QtWebEngine hooks in PyInstaller, but the QtWebEngineProcess
  helper and resources must be present; existing project note on macOS
  packaging: `docs/research/macos-distribution.md`.
- Size: +5.5 MB for `mermaid.min.js`; negligible next to the QtWebEngine
  runtime itself. Code-signing: a JS data file in `Resources`/`_internal`
  needs no special handling (**UNVERIFIED**; see macos-distribution.md).

## 2. Sandbox and security for LLM-authored diagrams

Threat model: the LLM (and ingested documents that influence it) author diagram
text. Mermaid's job is to turn that text into SVG. Attack surface: HTML
injection in labels, `click` callbacks, `%%{init}%%` / frontmatter config
overrides, links, remote image/font loads, and navigation.

### Mermaid-side

- `securityLevel` values: `strict` (default; HTML tags in text are encoded and
  click is disabled), `antiscript` (HTML minus script, click enabled),
  `loose` (HTML and click enabled), `sandbox` (render in an iframe, "prevents
  any JavaScript from running in the context" but "may hinder interactive
  functionality... links to other tabs or targets"). Sources:
  https://mermaid.js.org/config/usage.html ,
  https://mermaid.js.org/config/schema-docs/config.html
- Source of `mermaidAPI.ts` shows: sandbox mode does the work in a
  sandboxed iframe; otherwise the output SVG is passed through DOMPurify with
  `ADD_TAGS: ['foreignobject']`, `ADD_ATTR: ['dominant-baseline']` and
  `HTML_INTEGRATION_POINTS: {foreignobject: true}`. (Source view was
  summarised by the fetch tool; quoted fragments are as reported.) Source:
  https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/mermaidAPI.ts
  (fetched via raw.githubusercontent.com). `dompurifyConfig` is a config key
  to tune this: https://mermaid.js.org/config/schema-docs/config.html
- **Directives / `%%{init}%%`**: deprecated since v10.5.0 in favour of
  frontmatter `config`. Source: https://mermaid.js.org/config/directives.html
  The `secure` option lists config keys that "can only be changed via call to
  `mermaid.initialize`. This prevents malicious graph directives from
  overriding a site's default security"; default secure keys: `secure`,
  `securityLevel`, `startOnLoad`, `maxTextSize`, `suppressErrorRendering`,
  `maxEdges`. Source:
  https://mermaid.js.org/config/schema-docs/config.html
  So an LLM-authored `%%{init: {securityLevel: 'loose'}}%%` cannot override
  `securityLevel` by default. Recommendation: also extend `secure` with `theme`
  and `themeVariables` if we want theme to be app-controlled, **UNVERIFIED**
  that those keys are permitted in `secure` (the doc says "keys of
  currentConfig"; should hold, but test it), and/or strip `%%{init` and
  frontmatter `config:` blocks from the source before render (cheap, no
  dependence on mermaid internals).
- `htmlLabels`: "whether or not a html tag should be used for rendering
  labels". Under `strict` the HTML is encoded; foreignObject output still
  passes through DOMPurify. Setting `htmlLabels: false` renders labels as SVG
  text, reduces the DOMPurify/foreignObject surface and avoids a known class
  of rendering inconsistencies in WebKit-like engines (**UNVERIFIED**
  claim; no primary source fetched). Cost: no HTML (bold, `<br/>`) in labels
  (markdown strings still work, per mermaid docs, **UNVERIFIED** here).
  Source for the key: https://mermaid.js.org/config/schema-docs/config.html
- Resource limits: `maxTextSize` default 50000 chars, `maxEdges` default 500.
  Both are in the secure list, so diagrams cannot raise them. Good DoS
  mitigation for LLM output; consider lowering. Source: same schema page.
- `click` callbacks and links: disabled at `strict`. `bindFunctions` from
  `mermaid.render` is only needed for interactivity, so do not call it.
  Source: https://mermaid.js.org/config/usage.html
- Do **not** use `securityLevel: "sandbox"` as the main defence: it makes
  Mermaid build an iframe inside the page (more moving parts in a WebEngine
  view, sizing and theming across the iframe boundary), and `strict` already
  gives DOMPurify. Reasonable only as an extra if we render in a view that
  also hosts other trusted UI. In our design the view hosts only diagrams,
  so the Qt-side lock-down below is the stronger layer.

### Qt-side mitigations (defence in depth)

- **Remote content from local pages**: `LocalContentCanAccessRemoteUrls` is
  disabled by default (keep it); `AllowRunningInsecureContent` disabled by
  default. `LocalContentCanAccessFileUrls` is enabled by default; set it
  `False` once the shell page is the only local document if scripts are
  inlined or via a scheme handler, otherwise keep it on (the shell needs to
  load `mermaid.min.js`). Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebenginesettings.html
- **JavaScript** must stay enabled (Mermaid is JavaScript). Disable
  `JavascriptCanOpenWindows` (default enabled). `ErrorPageEnabled` can be
  disabled to avoid Chromium error pages. Same source.
- **Navigation**: override `QWebEnginePage.acceptNavigationRequest(url, type,
  isMainFrame)`; allow only the initial `file://` shell load, reject
  `LinkClickedType` etc. and hand external `http(s)` links to
  `QDesktopServices.openUrl` after user confirmation if wanted. The API
  filters by `NavigationType`. Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebenginepage.html
- **Request interception**: `QWebEngineProfile.setUrlRequestInterceptor()` with
  a `QWebEngineUrlRequestInterceptor` that blocks any request whose scheme is
  not `file`/`data`/`blob`. "interceptRequest... will be stalling the URL
  request until handled", and runs with main-thread blocking implications, so
  keep it trivial. Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebengineurlrequestinterceptor.html
  (the page text says `block()` was not mentioned in the fetched summary;
  `info.block(True)` exists on `QWebEngineUrlRequestInfo` per Qt docs,
  **UNVERIFIED** in this session).
- **Profile**: use an off-the-record profile (`QWebEngineProfile()` with no
  storage name) so no cookies/cache/localStorage persist. Source:
  https://doc-snapshots.qt.io/qtwebengine/qwebengineprofile.html
- **CSP**: put a `<meta http-equiv="Content-Security-Policy" content="default-src
  'none'; script-src 'self'; style-src 'unsafe-inline'; img-src data:">` in the
  shell. Mermaid injects `<style>` elements, so `style-src 'unsafe-inline'`
  (or a nonce) is needed. `script-src 'self'` for a `file://` origin
  semantics is **UNVERIFIED** (Chromium treats file origins as opaque; may need
  `script-src file:`); test before committing. No primary source fetched for CSP
  in this session; spec: https://www.w3.org/TR/CSP3/ (not fetched).
- If the process model ever hosts the shell with Chromium sandbox disabled
  (e.g. `--no-sandbox` flags), do not do that; Qt WebEngine's default
  sandbox on macOS stays on. (**UNVERIFIED**; no source fetched.)

## 3. Light/dark theming

- Mermaid has built-in themes (`default`, `neutral`, `dark`, `forest`, `base`
  plus newer `redux*`/`neo*`). Only `base` accepts `themeVariables`
  customization; `darkMode: true` affects how derived colours are computed;
  colours must be hex (no names). Source:
  https://mermaid.js.org/config/theming.html
- Set via `mermaid.initialize({theme})` site-wide, or per-diagram via
  frontmatter. Same source. Mermaid has no automatic OS-appearance switch in
  that doc; the `initialize` call is global and rendered SVGs are static, so a
  theme change requires **re-initialize and re-render**. (Inference from the
  render API returning static SVG strings; the docs page for `render` does not
  state it, but SVG output has colours baked into an inline `<style>`.)
- **Following macOS appearance**: Qt exposes the system scheme through
  `QStyleHints.colorScheme()` and `colorSchemeChanged` (Qt 6.5+, **UNVERIFIED**
  in this session; source would be
  https://doc.qt.io/qt-6/qstylehints.html). Wire it to push
  `mermaid.initialize({theme: dark ? "dark" : "default"})` and re-render every
  diagram from stored sources via `runJavaScript`. Do not rely on
  `prefers-color-scheme` inside the view: the QWebEngine docs fetched
  (page/settings/profile) expose no colour-scheme property, only a global
  `ForceDarkMode` web attribute ("all web contents will be rendered using a
  dark theme", default disabled), which would auto-darken page chrome but is
  wrong for diagrams (it inverts SVG colours heuristically). Sources:
  https://doc-snapshots.qt.io/qtwebengine/qwebenginesettings.html ,
  https://doc-snapshots.qt.io/qtwebengine/qwebenginepage.html . Whether
  Chromium inside QtWebEngine propagates the Qt palette to
  `prefers-color-scheme` on macOS is **UNVERIFIED**; avoid depending on it.
- Match page background: `QWebEnginePage.setBackgroundColor()` (documented as
  preventing white flash) set from the app palette. Source: qwebenginepage
  page above. Use a transparent background so the pane colour shows through.
- Recommended minimum: two themes, `default` and `dark`. Use `base` +
  `themeVariables` only if brand-matching the app palette is wanted (hex only).

## 4. Error fallback and streaming

- `mermaid.parse(text, {suppressErrors: true})` returns `false` instead of
  throwing on invalid input; otherwise it throws, and `mermaid.parseError`
  is called only when not suppressed. On success it returns `{diagramType}`.
  Source: https://mermaid.js.org/config/usage.html
- `mermaid.render(id, text)` returns `{svg, bindFunctions}`. By default, a
  failing render does not throw: `mermaidAPI.render` replaces the diagram with
  the "Syntax error" error diagram unless `suppressErrorRendering` is true, in
  which case it removes temp elements and rethrows. Sources:
  https://github.com/mermaid-js/mermaid/blob/develop/packages/mermaid/src/mermaidAPI.ts ,
  https://mermaid.js.org/config/schema-docs/config.html ("Suppresses inserting
  'Syntax error' diagram in the DOM").
- Known leak (**UNVERIFIED**, from experience/reported issues, no source
  fetched): a failed `render` can leave a stray element with the `id` (or
  `d`+id) in `document.body`. Mitigation: render into a detached off-screen
  container (the 4th `container` argument exists in recent versions, and
  llm_wiki uses it, see section 5) and remove any element with the id in a
  `finally`.
- **Recommended flow** per diagram: (1) strip directives/frontmatter config;
  (2) cap length; (3) `await mermaid.parse(src, {suppressErrors:true})`; if
  `false` fall back; (4) `try { svg = (await mermaid.render(id, src)).svg }
  catch { fallback }`; (5) fallback = `<pre><code>` with the source plus a
  one-line "Diagram could not be rendered" label (and optionally the first
  line of the error message, escaped). Never insert Mermaid's own error SVG.
- **Streaming**: LLM output arrives token by token, so a mid-stream diagram is
  almost always invalid. Options: (a) render only once the closing fence
  arrives (simplest; show source as a code block meanwhile, then swap to the
  SVG), (b) debounce (~300 ms) and keep the last successfully rendered SVG
  on failure. Recommend (a) for v1; (b) later if live-diagram feel matters. No
  primary source covers this; it is a design recommendation. Because
  `parse` with `suppressErrors` is cheap-ish and non-mutating, (b) is
  implementable without error flicker.
- Render in a serialized queue: `mermaid.render` is async and uses a global
  config/ids; concurrent renders with the same id can clash. Use unique ids
  (counter). (**UNVERIFIED** concurrency claim; the doc just uses a fixed
  `'graphDiv'` id in its example, Source: usage.html.)

## 5. How upstream llm_wiki does it

llm_wiki (Tauri v2, React 19 + Vite, so a browser-class webview, not
QtWebEngine) renders Mermaid code fences in chat, wiki reader, research
panel and file preview, plus standalone `.mmd`/`.mermaid` files. Sources:
https://github.com/nashsu/llm_wiki (README: "render Mermaid code blocks
directly in chat and preview, with compact syntax-error cards instead of raw
parser output") and the code search of the repo (files
`src/components/mermaid-diagram.tsx`, `src/components/chat/chat-message.tsx`,
`src/components/editor/file-preview.tsx`, `src/lib/file-types.ts`;
dependency `mermaid ^11.14.0` in `package.json`).

From https://raw.githubusercontent.com/nashsu/llm_wiki/main/src/components/mermaid-diagram.tsx
(as summarised by the fetch tool; read the file for exact code before
copying):

- `mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel:
  "strict", suppressErrorRendering: true })`.
- `mermaid.setParseErrorHandler(() => {})` so mermaid does not inject its own
  error block; errors are caught, summarised (`summarizeMermaidError`, first
  useful line) and shown as an alert card with collapsible details; i18n
  string "Mermaid diagram could not be rendered".
- Renders into an off-screen div (`left: -10000px`) via `mermaid.render(id,
  code, renderHost)` then removes it; SVG is injected with
  `dangerouslySetInnerHTML` (relies on Mermaid's `strict` + DOMPurify).
- Lazy rendering via `IntersectionObserver` with a 200 px margin.
- Theme hard-coded to `default`; no dark switching in that component (so
  dark mode is not solved upstream).
- A prompt line in `src-tauri/src/agent/context.rs` tells the agent to reply
  with a ```mermaid fence rather than generating HTML.

What we should borrow: strict + suppressErrorRendering, off-screen render
host, error card, `.mmd` as a first-class previewable file type, lazy render.
What we must add: Qt-side lock-down (no CSP/navigation hardening is visible
upstream), dark theme switching, and streaming handling.

## Open questions / unverified (needs a quick spike)

- Does `file://` shell + `script-src` CSP work in QtWebEngine as written (or
  is `file:` needed)?
- Does `QStyleHints.colorSchemeChanged` fire reliably on macOS appearance
  switch in PySide6, and does the web view's `prefers-color-scheme` follow it?
- Can `theme`/`themeVariables` be added to `secure`?
- `mermaid.render` 4th-arg container and stray-element cleanup behaviour in
  12.1.0.
- Chunk-directory size if ESM build were preferred.

## Scope note / follow-ups (not done here)

- A spike prototype confirming the open questions above.
- Decide single-view-per-pane vs one-view-per-diagram (separate issue).
- Consider a pre-render step (headless mermaid-cli) for the Preview pane only
  if Chromium cost proves too high; out of scope.
