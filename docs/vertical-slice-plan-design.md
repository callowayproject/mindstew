# Vertical-slice implementation plan for spec #30

## Summary

Spec #30 (mindstew, the native macOS llm_wiki reimplementation) is implemented as **core-first vertical slices**. The Qt-free core is built and proven slice by slice, each slice demonstrable through a `mindstew` CLI (or the MCP server once it exists) and covered by pytest through the spec's two seams. The GUI is added afterwards as a thin facade over the same core API, also in slices, with the signed/notarized DMG pipeline pulled forward right after the first GUI slice. This document is the reviewable plan; one GitHub issue per slice ("Part of #30", Blocked-by edges, user stories, acceptance criteria, demo script, test seams) is created only after this doc is approved. No visual was produced for this grill.

## Terms

- **Vertical slice**: a shippable increment cutting through every layer it needs (core, tools, CLI/MCP/GUI surface) and demoable end to end. Avoid: phase, module task, layer.
- **Walking skeleton**: the first slices (S1a, S1b): the thinnest real path through vault, provider, queue and ingest; also establishes fixtures. Avoid: scaffold, spike.
- **Core-first**: core slices come first, each demoed via CLI or MCP; the GUI is a thin facade added later. Avoid: backend-only, headless phase.
- Spec terms (Vault, Route, Skill, Vault archive, Derived data, Portable state, etc.) are as defined in `CONTEXT.md` and spec #30.

## Why

The user wants to plan implementation of spec #30 "divided into vertical slices that are fully functional". The spec's own suggested decomposition is 16 horizontal modules, which the user does not want. In the user's words: "I want risk first, but not risks associated with the GUI or packaging. I want a fully functional core, with the GUI as a facade first. Then work through the risks of the GUI." And: "the functionality must be demonstrable in the method it requires (CLI, MCP, etc)".

## Locked decisions

1. **Acceptance bar for "fully functional" (Q1, durable).** Each slice is demonstrable through the surface it actually requires: CLI for core capabilities, MCP for the MCP server, the app window for GUI slices. No slice is "done" merely because an internal API is unit-tested. Rejected: (B) headless-API-only slices with GUI wired later, because that recreates horizontal layers and defers integration risk; (A) strict everything-in-the-GUI, because the spec defers the GUI and nearly all core capability can be shown without it.
2. **Skeleton shape (Q2 + Q4, durable).** Slice 1 is vault create/open, tolerant page model, provider adapter with Keychain, serial SQLite queue with background worker, two-step ingest of Markdown/text, **without the Qt shell**. The demo surface is a `mindstew` CLI (pyproject already has a commented `mindstew = mindstew.cli:cli` entry); later the GUI and MCP are further facades over the same core API. Rejected: pytest-only proof (nothing to demo, no real-provider run); CLI until MCP lands then MCP-only (MCP exposes just four tools and cannot show ingest/review/lint). Note: Q2 was accepted with its window shell; Q1/Q3 and Q4 supersede that part, the shell moves to G1.
3. **Ordering principle (Q3, durable).** Risk-first, but only core risks; GUI and packaging risks come after the core is functional. The earlier proposal to pull a signed-DMG slice to slice 2 was rejected by the user; it is instead pulled forward within the GUI phase (Q7).

## Routine choices

- **S2 is the agent slice (Q5).** After the skeleton, retire Pydantic AI streaming+approval (LiteLLM fallback decision) and the Seatbelt sandbox first, because the tool layer is the contract for MCP and sources-only mode. It uses a minimal BM25/grep `wiki_search` so it is vertical; LanceDB comes in S3.
- **Remaining core order (Q6-A):** S3 index -> S4 extraction/captioning -> S5 sources-only -> S6 MCP -> S7 lint -> S8 graph -> S9 review -> S10 skills -> S11 archive. Archive is last because it serializes review flags and caption records, whose schemas must be stable.
- **GUI slicing (Q7-C):** one slice per surface, packaging pulled forward after G1: G1 shell, then packaging, then chat, graph, review+lint, settings.
- **Split S1 (Q8-A):** S1a = vault + page model + resolver + CLI; S1b = provider/Keychain + queue + text ingest.
- **Deliverable (Q9-A):** this doc, then one GitHub issue per slice created after approval.

## The slice plan

Every slice: tests through Seam 1 (headless core with fakes) and/or Seam 2 (tool surface); defensive-parsing test for any frontmatter reader; run via `uv run pytest` / `uv run ruff check`; one feature branch per issue, never commit to `main`. Story numbers refer to #30's User Stories.

### Core slices (demo via CLI/MCP)

| Slice | Delivers | Demo | Stories | Blocked by |
|---|---|---|---|---|
| **S1a** Vault & pages | Vault scaffold, non-destructive adoption, project registry, page model (6 types, tolerant frontmatter, slugs, numeric disambiguation), the one shared wikilink resolver, fixtures (temp vault builder, fake provider adapter, sample sources), `mindstew` CLI (`new`, `open`, `ls`, `show`) | Create a vault; open an existing Obsidian vault unchanged; list/show pages with resolved links | 1, 2, 3, 5, 6, 7, 8, 9-16 | none |
| **S1b** Provider & text ingest | Provider registry, routes (global + per-vault override), Keychain secrets, Test connection, SQLite serial queue + SHA256 cache, resume, retry cap 3, background worker, two-step structured ingest of Markdown/text, folder import, source-folder watch, re-ingest, event emission, CLI (`provider`, `ingest`, `watch`, `status`) | Ingest a text source with a real provider; kill and relaunch to see queue resume; failed item shows `failed` | 17-19, 20 (text/Markdown only), 21-25, 27, 28, 101-105 (core) | S1a |
| **S2** Chat agent | Shared Pydantic-typed tool layer (`wiki_search` minimal BM25, `vault_read`, `vault_write`, `enqueue_ingest`, `shell_exec`), Pydantic AI agent with streaming + cancel, approval gate for `shell_exec` (CLI prompt with editable command), denial as tool result, session-scoped approval memory, Seatbelt sandbox with fail-closed self-test; decision recorded on Pydantic AI vs LiteLLM fallback | `mindstew chat` REPL: ask over wiki, write a page, approve/deny/edit a sandboxed command; sandbox blocks writes outside vault | 59-62, 63-67 (CLI form), 60 | S1b |
| **S3** Index & search | LanceDB wiki-chunk table (per-H2 chunks, `chunk_id`, `merge_insert`, per-chunk SHA256, stale removal), embedding stage with own retry cap, hybrid vector+BM25 RRF, BM25-only fallback, re-embed warning with cost estimate on embedding-route change; `wiki_search` upgraded; source-text table scaffolding | `mindstew search`; change embedding route and see warning + BM25-only | 40-46, 106, 107 | S2 |
| **S4** Extraction & captioning | PDF/DOCX/EPUB/image extraction to normalized text + image list, caption store (content-hash cache), vision route, downscale setting, inline alt text, `wiki/media/<slug>/`, independent retry cap 3, vision-support warning, retry-caption CLI command; populates source-text table | Ingest a PDF with images; captions appear in page; retry a failed caption | 20, 29-39 (non-GUI parts) | S3 |
| **S5** Sources-only mode | Per-conversation switch in CLI chat, tool re-scoping (wiki absent from context, write/enqueue/shell withdrawn), mode-toggle divider, structured citations (file, locator, retrieved passage, unsupported flag) | Chat in sources-only mode; citations carry exact chunk text | 71-77 (non-GUI parts) | S4 |
| **S6** MCP server | Standalone stdio executable exposing `wiki_search`, `vault_read`, `wiki_write`, `enqueue_ingest` only; scope-stating descriptions; stdio protocol smoke test | Connect Claude Code/Desktop to a vault | 118-121 | S5 |
| **S7** Structural lint | All spec lint checks, report-only, recomputed, cancellable/coalesced, auto-run after queue drain, "Fix with chat" prefill via CLI chat | `mindstew lint` on a crafted bad vault | 86-91 (core), 88, 89 | S6 (needs only S1b events; ordered here by Q6) |
| **S8** Graph engine | Four-signal scores (4.0/3.0/1.5/1.0 constants), per-page edge recompute, global Louvain, cached spring layout, `graph_edges`/`graph_communities`, color-mode data, CLI export (JSON) | `mindstew graph` prints edges/communities for a fixture | 47-49, 50 (layout cache), 51 (size data) | S7 |
| **S9** Review system | `review_flags`, five flag types, content-derived IDs, two-stage sweep (rule-based, then capped LLM judgment 5x40), won't-fix dismissals, accept/dismiss/edit-and-resolve/re-ingest actions, Activity-visible via `status` | `mindstew review` list/act | 78-84 (core) | S8 |
| **S10** Skills | Two skill sources, shadowing, lazy rescan, invalid-skill counting, `load_skill` confined to skill folder (no `..`, no symlink escape), system-prompt listing, `/skill` in CLI chat | Use a vault-local skill in chat | 92-99 (core) | S9 |
| **S11** Archive | Export zip with `manifest.json` and `portable-state.json`, import to new vault with numeric suffix, traversal/absolute/symlink/zip-bomb rejection, version handling, unknown-provider route drop, malformed portable-state skip, rebuild embeddings and graph | `mindstew export` / `import` round trip | 108-117 | S10 |

### GUI slices (facade over the core)

| Slice | Delivers | Stories | Blocked by |
|---|---|---|---|
| **G1** Shell | Main window (icon rail, File Tree dock, Preview with QtWebEngine Markdown render, Activity column bound to core events), New/Open project, single-window project switching, registry on launch, pytest-qt smoke test, right-click Retry caption in Preview | 4, 5, 26, 27, 36, 38, plus GUI side of 1-3, 7 | S11 |
| **G-pkg** Packaging | PyInstaller onedir, inside-out codesign with QtWebEngine helper entitlements, notarize, staple, DMG, GitHub Releases update check | 122-124 | G1 |
| **G2** Chat panel | Streaming transcript, inline editable approval card, Mermaid renderer (offline, lockdown, theme, close-fence render), `/` skill popup with skipped footer, sources-only switch/chips with hover passage | 60, 63, 68-70, 74-77, 93, 97 (GUI parts) | G-pkg |
| **G3** Graph view | QGraphicsView, size by links, community/type color toggle (QSettings), legend, weak-edge hiding, hover highlight, click/double-click | 50-58 | G-pkg |
| **G4** Review & Lint views | Review Mode inbox with filters and actions, Lint rail item with badge, Open page / Fix with chat | 78-85, 90 | G-pkg |
| **G5** Settings | Cmd+, window, Providers and Models tabs, per-vault override, Test connection, max-image-dimension setting, re-embed confirm dialog | 100-107 (GUI parts), 39 | G-pkg |

Coverage check to perform when issues are written: every story 1-124 maps to exactly one slice's acceptance criteria (CLI/core part in an S slice, GUI part in a G slice where noted).

## Verified facts

- The repo is greenfield: `mindstew/` contains only `__init__.py`, `tests/` is empty, `prototype/three_pane_ui_prototype.py` is a throwaway Qt prototype; `pyproject.toml` has only `pydantic-settings` as a dependency and a commented `mindstew.cli:cli` script entry; Python >= 3.14.
- Issues live in GitHub Issues; the map is #1, spec is #30 with no comments; wayfinding conventions (sub-issues, native dependencies, `Blocked by:` fallback) are in `docs/agents/issue-tracker.md`.
- #30 itself lists a 16-item horizontal decomposition as follow-ups; this plan replaces it.

## Risks

- S1b and S2 carry the biggest uncertainty (worker threading with LLM calls; Pydantic AI streaming+approval, possibly forcing the LiteLLM fallback). S2's CLI approval prompt does not prove the GUI's inline streaming card; that is re-tested in G2.
- The GUI phase is where QtWebEngine, Mermaid lockdown and notarization risk live; deferring them is deliberate, but a core API shaped without GUI threading in mind could need rework at G1. Mitigation: core emits events and runs the worker off any Qt object; G1 includes the pytest-qt smoke test.
- S11 archive freezes two versioned formats; review-flag and caption-record schemas (S4, S9) must be stable first.
- Seatbelt is deprecated and bounds only where files are touched; PDF extraction quality limits sources-only answers; re-embedding two tables is slow and costly.
- Keychain access in a CLI process may behave differently from a signed app (prompts/ACLs); verify in S1b.

## Deferred

- Sparkle updates, parallel ingest, MCP HTTP/SSE and everything else in #30's Out of Scope stay out.
- Open implementation questions in #30 (source-text chunking strategy, where max-image-dimension lives, model image-support validation, skills list cap, source-text backfill, "pages citing this" on chips) are decided inside the slice that touches them (S3/S4, G5, S10) and would reopen only if that slice's acceptance criteria cannot be written without them.

## Open threads

- Whether S7 (lint) and S8 (graph) should move before S6 (MCP): Q6-A put MCP first; their dependencies allow either order.
- G5 (Settings) comes last in the GUI phase, so GUI users configure providers via the CLI until then; the user may want it moved right after G1. Not discussed.
- Per-slice sizing of S2 (agent + approval + sandbox in one slice) was not challenged; it may warrant a split into S2a agent/tools and S2b sandbox when the issue is written.
