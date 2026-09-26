# macOS Distribution Research: Signing, Notarization, and Updates

Research for issue #6. Distribution is already fixed as **signed + notarized DMG via direct
distribution**, not the Mac App Store (QtWebEngine is incompatible with App Store sandboxing).
This document does not revisit that decision — it answers packaging tool choice, the
sign/notarize flow, and the update mechanism.

## Bottom line

- **Packaging tool: PyInstaller.** As of PyInstaller 6.x, QtWebEngine is explicitly supported on
  macOS in both `onedir` and `onefile` modes (onefile support landed later), and PyInstaller's own
  macOS bundle generation (since 6.0.0) restructures `.app` bundles specifically to satisfy
  code-signing requirements (binaries under `Contents/Frameworks`, data under `Contents/Resources`,
  cross-linked via symlinks). py2app has a long-standing open issue about correctly packaging
  QtWebEngine (PyQt5/PySide) that was never fully closed out on py2app's side. Qt's own docs
  recommend `pyside6-deploy` as "easier to use," but that tool wraps PyInstaller/Nuitka rather
  than being an independent third option for this case.
- **Sign/notarize flow: manual `codesign` + `notarytool`, not `macdeployqt -sign-for-notarization`.**
  `macdeployqt` is a qmake-integrated tool; PyInstaller bundles aren't produced by qmake, so the
  flag doesn't apply cleanly and the team should expect to write the inside-out signing script
  themselves (helpers → frameworks → `QtWebEngineProcess.app` → outer `.app`), each with the
  entitlements Apple's own docs specify, then `xcrun notarytool submit --wait` and
  `xcrun stapler staple`. `QtWebEngineProcess.app` needs its own entitlements file distinct from
  the main app's (`allow-jit`, `allow-unsigned-executable-memory`,
  `disable-library-validation`) because Chromium's V8 needs JIT and hardened runtime blocks that
  by default.
- **Update mechanism: DIY GitHub Releases check, not Sparkle — at least to start.** Sparkle is the
  de facto standard and works from Python via `pyobjc-core`, but it adds a second, independent
  codesigning/entitlements surface (its own XPC helpers need hardened-runtime entitlements) and,
  per a maintainer-confirmed GitHub Discussion, getting it working from PySide6 + PyInstaller
  today still requires manual troubleshooting (bundle path corrections, ObjC initializer quirks)
  with no established, documented recipe. For a small team, a simple "check GitHub Releases API →
  download the notarized DMG → prompt reinstall" flow avoids a second attack surface for
  notarization to go wrong and is what several non-App-Store Python/Qt projects have shipped with
  in practice (community-documented, not vendor-documented). Revisit Sparkle if/when delta updates
  or silent background updates become a real user-facing requirement.

---

## 1. Packaging tool: PyInstaller vs py2app

### PyInstaller

- PyInstaller's own changelog documents active, ongoing QtWebEngine support work:
  - v6.0.0: "(macOS) `QtWebEngine` now works in `onefile` builds (previously available only in
    `onedir` builds)" — closing
    [pyinstaller/pyinstaller#4361](https://github.com/pyinstaller/pyinstaller/issues/4361), which
    is itself a primary-source record of the historical "Could not find QtWebEngineProcess" /
    "nothing displayed in the QtWebEngine window" failure mode. See
    [PyInstaller 6.0.0 changelog](https://pyinstaller.org/en/v6.0.0/CHANGES.html).
  - v6.0.0 also restructured macOS `.app` bundle generation: shared libraries go under
    `Contents/Frameworks`, data files under `Contents/Resources`, cross-linked so QML and Qt
    resource lookup keeps working — explicitly motivated by code-signing compliance (signatures
    can't live in extended attributes, which is what the old layout relied on). See
    [PyInstaller 6.7.0 changelog](https://pyinstaller.org/en/v6.7.0/CHANGES.html) and
    [pyinstaller/pyinstaller#7619](https://github.com/pyinstaller/pyinstaller/issues/7619).
  - The changelog also notes: "Sandboxing for `QtWebEngine` in PySide6 is not disabled anymore by
    the corresponding run-time hooks, as it should work out-of-the-box thanks to PyInstaller now
    preserving the structure of the `QtWebEngineCore.framework` bundle" — i.e., PyInstaller
    started preserving the framework's internal structure rather than flattening it, which is what
    QtWebEngine's helper-process discovery depends on.
  - QtWebEngine support requires Qt6 ≥ 6.2.2 per the same changelog series.
  - Open community discussion on resource path issues still exists:
    [pyinstaller/pyinstaller discussion #7590](https://github.com/orgs/pyinstaller/discussions/7590)
    (macOS PySide6 QtWebEngine resources) — flagged as **secondary/community-sourced**, useful for
    troubleshooting but not a maintainer commitment.
  - `onefile` vs `onedir`: onedir is the safer default for signing — you sign a real directory
    tree of frameworks/binaries in place. Onefile packs everything into a self-extracting single
    binary that unpacks to a temp dir at runtime; signing implications for the *outer* single file
    are simpler (one binary) but the inside-out signing of bundled frameworks still has to happen
    at build time before that single file is assembled, and PyInstaller's onefile-mode QtWebEngine
    support is newer/less battle-tested than onedir per the same changelog history. No PyInstaller
    doc explicitly recommends one over the other for notarization; this is an **open gap** — see
    below.

### py2app

- py2app has a long-standing, still-relevant open issue directly on point:
  [ronaldoussoren/py2app#280 "Correctly packaging PyQt5's QtWebEngine"](https://github.com/ronaldoussoren/py2app/issues/280).
  This is py2app's own primary-source issue tracker describing the exact problem (QtWebEngine
  resources/helper process not correctly located in the bundle produced by py2app).
- I could not find a py2app changelog entry or official doc page (py2app's docs are thin compared
  to PyInstaller's) claiming resolved, first-class QtWebEngine support. This is a **gap**: absence
  of a fix doesn't prove py2app can't work, but there's no primary-source evidence it does, versus
  PyInstaller's explicit changelog entries closing the equivalent issue.
- Related: [Nuitka/Nuitka#3328](https://github.com/Nuitka/Nuitka/issues/3328) shows the same class
  of QWebEngineView-in-standalone-bundle failure recurs across multiple non-qmake packaging tools
  (Nuitka included), suggesting the underlying difficulty is Qt's own resource/helper-process
  discovery model rather than something specific to one tool — but only PyInstaller has a
  documented, closed fix for it.

### Qt's own guidance

- Qt for Python's official deployment docs
  ([doc.qt.io/qtforpython-6/deployment](https://doc.qt.io/qtforpython-6/deployment/index.html))
  list PyInstaller, `pyside6-deploy`, fbs, cx_Freeze, and briefcase as the supported paths and
  state cross-platform tools are "fbs, cx_Freeze, briefcase, and PyInstaller" — py2app is not in
  Qt's own supported-tools list for Qt6/PySide6 at all.
  [doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
  is Qt's dedicated PyInstaller page.
- Qt recommends `pyside6-deploy` as "easier to use... to get the most optimized executable"
  ([doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html)),
  but `pyside6-deploy` itself is a wrapper that drives PyInstaller (or Nuitka) under the hood, not
  an independent packaging engine — so it isn't a genuine alternative to the PyInstaller-vs-py2app
  choice, just a convenience layer on top of PyInstaller.

**Conclusion for part 1:** PyInstaller, onedir mode as the starting point (matches its more mature
QtWebEngine changelog history; revisit onefile only if there's a concrete reason to need it).

---

## 2. Codesigning + notarization for a QtWebEngine bundle

### Apple's primary documentation

- Hardened runtime overview: [developer.apple.com/documentation/security/hardened-runtime](https://developer.apple.com/documentation/security/hardened-runtime)
  and [Configuring the hardened runtime](https://developer.apple.com/documentation/xcode/configuring-the-hardened-runtime).
- Entitlements relevant to QtWebEngineProcess (Chromium/V8), each with its own Apple doc page:
  - [`com.apple.security.cs.allow-jit`](https://developer.apple.com/documentation/BundleResources/Entitlements/com.apple.security.cs.allow-jit) —
    "indicates whether the app may create writable and executable memory... required if the
    application uses JavaScriptCore" — without it, a WebView-hosting process using JS JIT will
    crash on initialization.
  - `com.apple.security.cs.allow-unsigned-executable-memory`
  - [`com.apple.security.cs.disable-library-validation`](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.security.cs.disable-library-validation) —
    needed so the process can load libraries that aren't all signed by the same team ID.
  - Full list: [Security entitlements](https://developer.apple.com/documentation/bundleresources/security-entitlements).
- Nested-code signing order: Apple's guidance is to recursively sign all helpers, tools,
  libraries, and frameworks bundled with the app *before* signing the outer app, because
  `codesign` writes nested-code signature references into the outer bundle's seal
  ([Ensuring Proper Code Signatures for Nested Code](https://developer.apple.com/library/archive/documentation/Security/Conceptual/CodeSigningGuide/Procedures/Procedures.html),
  and see also
  [TN3127: Inside Code Signing: Requirements](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements)). Practically: sign
  `QtWebEngineProcess.app` (with its own entitlements) and any other embedded frameworks first,
  then sign the outer app last, each with `--options runtime` for hardened runtime and, for
  helpers with special needs, a distinct entitlements plist passed via `--entitlements`.
- Notarization workflow itself:
  [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)
  describes codesign with hardened runtime + secure timestamp as a precondition, then
  `xcrun notarytool submit <path> --keychain-profile "<profile>" --wait`, then
  `xcrun stapler staple <path>`.
- `altool` deprecation for notarization is explicitly documented by Apple in
  [TN3147: Migrating to the latest notarization tool](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool):
  the notary service stopped accepting `altool`/Xcode-13-or-earlier uploads as of November 1,
  2023 (per Apple's
  [notary service update notice](https://developer.apple.com/news/upcoming-requirements/?id=11012023a)).
  `notarytool` is the only current supported path; `altool` remains usable for unrelated App
  Store Connect tasks but not notarization.

### The QtWebEngine-specific complication

- Multiple Qt Forum threads (community-sourced, cross-referenced against the Apple entitlement
  docs above for the actual technical claims) describe the same failure signature: a
  hardened-runtime-signed main app crashes or silently fails when `QtWebEngineProcess.app` (the
  Chromium child process) doesn't carry `allow-jit` / `allow-unsigned-executable-memory` /
  `disable-library-validation` entitlements of its own —
  [Qt Forum: "codesign - Unable to sign QtWebEngineProcess with --options runtime"](https://forum.qt.io/topic/151688/codesign-unable-to-sign-qtwebengineprocess-with-options-runtime),
  [Qt Forum: "QtWebEngine signing issues"](https://forum.qt.io/topic/102212/qtwebengine-signing-issues).
  Flagged explicitly as **secondary/community-sourced** — Apple's own docs establish what each
  entitlement does and Chromium's JIT-based JS engine's need for it is well-established
  independently (Electron's docs describe the identical requirement for its Chromium-based
  processes: [electron/electron#53448](https://github.com/electron/electron/pull/53448)), but I
  found no Qt-official (doc.qt.io) page spelling out the exact entitlements-plist contents for
  `QtWebEngineProcess.app`. This is a **gap** — the specific required entitlement set for
  `QtWebEngineProcess.app` should be verified empirically against a real signed build before
  shipping, not assumed from forum posts alone.

### `macdeployqt -sign-for-notarization` and PyInstaller

- Qt's own tool signs every bundled framework/plugin with hardened runtime and a secure timestamp
  when given `-sign-for-notarization="Developer ID Application: ..."` (behavior described across
  Qt Forum threads and the Qt macOS deployment doc page referenced from
  [doc.qt.io/qt-5/macos-deployment.html](https://doc.qt.io/qt-5/macos-deployment.html); I could not
  load the Qt6-specific macdeployqt reference page directly in this session — noted as a **gap**,
  the Qt5 page is the primary source actually retrieved).
- `macdeployqt` operates on bundles produced by qmake/CMake Qt builds; a PyInstaller-produced
  `.app` is not a qmake build product, so `-sign-for-notarization` is not a drop-in fit. The
  practical path documented by third parties working the same problem (e.g. GDATASoftwareAG's
  [fork of macdeployqt fixing "broken code signing of nested frameworks in app bundles"](https://github.com/GDATASoftwareAG/macdeployqt))
  confirms nested-framework signing in Qt app bundles is a known pain point even for native Qt/qmake
  builds — for a PyInstaller bundle, expect to write a manual signing script following Apple's
  inside-out nested-code-signing order rather than relying on `macdeployqt` at all. This is
  consistent with what several non-Qt-official guides do (e.g. the
  [DoltHub blog: "How to Publish a Mac Desktop App Outside the App Store"](https://www.dolthub.com/blog/2024-10-22-how-to-publish-a-mac-desktop-app-outside-the-app-store/),
  flagged **secondary/community-sourced**).

---

## 3. Update mechanism

### Sparkle

- Official docs: [sparkle-project.org/documentation](https://sparkle-project.org/documentation/).
- Sparkle's own sandboxing doc confirms it ships XPC Services/helper tools that need hardened
  runtime and their own entitlements, and that Xcode's default re-signing behavior on
  archive/export "preserves the Hardened Runtime" — implying manual builds (e.g. from a
  PyInstaller pipeline with no Xcode project) need to replicate that signing step themselves. It
  also documents `com.apple.security.temporary-exception.mach-lookup.global-name` entitlements
  required for sandboxed apps using Sparkle's `-spks`/`-spki` XPC services. See
  [Sandboxing with Sparkle](https://sparkle-project.org/documentation/sandboxing/).
- Sparkle is Objective-C/Swift-native; from Python it's used via the `pyobjc-core` bridge
  ([pyobjc.readthedocs.io](https://pyobjc.readthedocs.io/)). A live GitHub Discussion on Sparkle's
  own repo,
  [sparkle-project/Sparkle#2402 "How can I get this project working in PySide6 Qt for Python and PyInstaller"](https://github.com/sparkle-project/Sparkle/discussions/2402),
  shows a developer hitting exactly this integration: wrong framework path in the PyInstaller
  bundle (`Resources/FrameWorks/Sparkle.framework` vs. the correct
  `Contents/Frameworks/Sparkle.framework`), an unavailable ObjC initializer
  (`SPUStandardUpdaterController.alloc().init()`), and update-check-interval misconfiguration. The
  Sparkle maintainer engaged but noted they're "unfamiliar with Python-objc bindings." No
  fundamental incompatibility was declared, but there is **no maintained, documented recipe** for
  PySide6 + PyInstaller + Sparkle as of this research — it's a DIY integration on top of a DIY
  integration.
- A secondary source, the fman.io blog post
  ["Codesigning and automatic updates for PyQt apps"](https://fman.io/blog/codesigning-and-automatic-updates-for-pyqt-apps/)
  (Michael Herrmann, fman file-manager project — **community-sourced**, flagged as such), documents
  a working PyQt5 + PyInstaller + Sparkle + `pyobjc-core` integration in production, including
  relocating PyInstaller's `base_library.zip` for compatibility with Sparkle's delta-update
  mechanism, and explicitly rejects a from-scratch DIY updater (dismissing the old Esky framework
  as incompatible with macOS code-signing requirements). This is the closest thing to a working
  precedent for Sparkle-from-Python, but it predates PySide6/Qt6 and current notarization
  requirements (altool-era), so some of its specifics are stale.

### DIY alternative

- Pattern: app checks GitHub's Releases API for the latest tag/version, compares to current
  version, and if newer, downloads the new signed+notarized DMG and either auto-launches the
  installer or simply prompts the user to download/reinstall manually (no delta patching, no
  background silent install).
- This is the lower-integration-cost option: it reuses artifacts you're already building and
  signing (the notarized DMG) with no additional entitlements, no XPC helper, no ObjC bridge
  dependency, and no packaging-time framework-embedding step. The tradeoff is UX (full reinstall
  vs. Sparkle's in-place relaunch, no delta downloads) and no automated silent updates.
- I did not find an official "reference implementation" for this pattern from any vendor (there
  isn't one to find — it's just calling GitHub's REST API) — noting as expected, not a gap, since
  the claim being verified is "this is simple," which is self-evidently true from the API
  surface, not something requiring a primary-source citation beyond
  [GitHub REST API docs for Releases](https://docs.github.com/en/rest/releases/releases).

### Recommendation

For a small team building v1 of this app, **start with the DIY GitHub Releases check**. Rationale
purely on integration cost, backed by what was found above:

- Sparkle from PySide6/PyInstaller has no current, maintained, official recipe — the only
  evidence of it working is a stale (PyQt5/pre-Qt6) blog post and an open, still-being-debugged
  GitHub Discussion on Sparkle's own repo. Expect to spend real time solving framework-placement
  and ObjC-initializer problems that the DIY path doesn't have.
- Sparkle adds its own entitlements/signing surface (XPC helpers, hardened runtime, sandboxing
  temporary-exception entitlements) on top of the QtWebEngineProcess entitlements already
  required — compounding an already nontrivial nested-signing pipeline for a first release.
- The DIY path produces exactly the same signed/notarized artifact you already build for
  distribution, with zero additional signing surface.

Revisit Sparkle later if delta/background updates become a real product requirement — at that
point, budget for a dedicated spike given the unresolved integration friction documented above.

---

## Open gaps

1. No official Qt6/PySide6-era `macdeployqt` reference page was retrieved in this session (the
   Qt5 macOS-deployment page was the actual source used) — should confirm behavior on current
   Qt6 before relying on any macdeployqt-derived guidance.
2. No Qt-official (doc.qt.io) documentation was found spelling out the exact entitlements plist
   required for `QtWebEngineProcess.app` under hardened runtime — the entitlement list here
   (`allow-jit`, `allow-unsigned-executable-memory`, `disable-library-validation`) is inferred from
   Apple's general entitlement docs plus community Qt Forum reports, and should be verified against
   an actual signed, notarized build of this app before shipping.
2b. No primary source found stating PyInstaller's `onefile` vs `onedir` mode has a *specific*
   notarization/signing tradeoff beyond onedir's QtWebEngine support being more mature in the
   changelog history — this is inferred, not documented explicitly by PyInstaller.
3. No official py2app documentation (as opposed to an open GitHub issue) was found addressing
   QtWebEngine bundling status one way or the other — absence of evidence, not evidence of
   permanent incompatibility.
4. No maintained, official (Sparkle-team or Qt-team) integration guide exists for
   PySide6 + PyInstaller + Sparkle; the only working precedent found (fman.io) is PyQt5-era and
   predates Qt6/current notarization tooling, and the live Sparkle GitHub Discussion for this
   exact stack is unresolved as of the date it was fetched.
