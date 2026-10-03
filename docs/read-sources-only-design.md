# "Read Sources Only" mode — design

Wayfinder ticket #26 in map #1. Grilled via grill-with-ui on 2026-10-03.

## Summary

"Read Sources Only" (working label; final UI copy is an implementation detail) is a per-conversation chat mode that grounds the agent exclusively in the original material under `sources/`. It is enforced by tool scoping, not by prompting: wiki pages never enter the model's context. Source text is searched through a second LanceDB table populated at ingest, and every claim must carry a structured citation to a source file with the retrieved passage quoted.

## Terms

- **Sources-only mode** — a chat mode in which the agent may ground answers only in the original material under `sources/`, never in LLM-generated wiki pages. Avoid: "raw mode".
- **Source text** — the normalized text extracted from a file in `sources/` (plus image captions, #20) that ingest already produces. Avoid: "raw file".

## Why

The wiki is LLM-synthesized; `sources/` is ground truth. The user wants to check a claim against the originals without the wiki's interpretation in the loop.

## Locked decisions

1. **Hard restriction by tool scoping (Q1 → A).** The agent sees only `sources/` content. Rejected: (B) keep wiki retrieval but force citations through each page's `sources[]` — wiki text would still shape the answer; (C) prompt-only — unenforceable.
2. **Second LanceDB table of source-text chunks (Q3 → A).** Populated by the ingest worker alongside wiki chunks, same hybrid (vector+BM25 RRF) search and the same embedding route (#21), keyed/hashed per chunk like #5. Derived and rebuildable, like the rest of the index. Costs extra embedding spend per source. Rejected: (B) lazy BM25-only over cached text — weaker on paraphrased questions; (C) rank via wiki_search then hop through `sources[]` — leaks wiki ranking into a mode meant to bypass it, and misses sources not reflected in any page.

## Routine choices

- **Toggle (Q2 → A):** per-conversation switch in the chat header. Changing it inserts a visible divider in the transcript; history stays, the new mode applies from the divider onward. Rejected: per-message (noisy), per-vault setting (buried).
- **Citations (Q4 → B):** every claim cites a source file path plus page/section locator when known, rendered as a clickable chip that opens the file in Preview. The exact quoted passage comes from the retrieved chunk (not model output) and shows on hover. Unsupported statements must be flagged as such. Citations are structured output, not prose markers.
- **Tool mapping (derived, not asked):** in this mode `wiki_search` and `vault_read` are re-scoped to `sources/` (the search tool takes the source table); `vault_write`, `enqueue_ingest` and `shell_exec` are withdrawn, since each can read or alter wiki content. The tool schemas from #11 are unchanged; the mode only changes which tools are registered and their scope. MCP surface (#18) is unaffected.

## Verified facts

- #11: `wiki_search` returns wiki chunks only; `vault_read` reads any vault path; `vault_write` is already denied `sources/`.
- #10/#5: the LanceDB index covers wiki chunks only today.
- #20: a normalized extraction step and image captions already exist at ingest, so source chunks need no new extraction.

## Risks

- Extra embedding cost and index size (roughly the size of the sources corpus); an embedding-route change (#21) must re-embed both tables.
- Extracted text quality (PDF parsing, captions) now directly limits answer quality in this mode.
- Source chunk locators (page numbers) depend on extractors preserving them; formats that cannot will cite file-level only.
- Withdrawing `shell_exec` means a user cannot ask the agent to grep sources by hand in this mode.

## Deferred

- Chunking strategy for source text (size, overlap, per-page vs per-section). Reopen at implementation spec; #5's per-H2 scheme does not apply to unstructured source text.
- Backfill of the source table for vaults ingested before this feature.
- Whether an "also show wiki pages that cite this" affordance belongs on citation chips.

## Open threads

None.
