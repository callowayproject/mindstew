# Structural lint — design

Wayfinder ticket #27 in map #1. Grilled via grill-with-ui on 2026-10-03.

## Summary

Structural lint is a deterministic, no-LLM pass over the vault's wiki files that reports orphan pages, broken wikilinks, no-outlink pages and schema violations from #3. It runs on demand and automatically after each ingest queue drain, shows results in its own Lint view (separate from the Review inbox, #19) with a count badge on its rail icon, and is **report-only**: from a finding the user can open the page or hand the finding to the chat agent. Findings are recomputed each run, never persisted.

## Terms

- **Structural lint** — deterministic, no-LLM checks over the wiki's files, frontmatter and wikilinks, a separate surface from the Review inbox. Avoid: "lint flag", "review lint".
- **Finding** — one result of a lint check, tied to a page (and a link or field when relevant); recomputed each run, not persisted. Avoid: "flag", "issue".

## Why

#3 deferred schema enforcement to "the lint pass", and #19 split structural lint from LLM review. This ticket fixes what lint checks, when it runs, how it is surfaced, and what the user can do about a finding.

## Locked decisions

1. **Check set (Q1 → B).** Upstream's three — `orphan`, `broken-link`, `no-outlinks` — plus schema checks: missing/invalid required field (`type`, `title`, `sources`), unknown `type`, type vs. typed-folder mismatch, `sources[]` entry pointing at a missing file, duplicate `title` (ambiguous wikilink target), and unparseable/malformed frontmatter as its own finding. Root/structural files (`index.md`, `log.md`, `overview.md`, `purpose.md`, `schema.md`) are exempt per #3. Rejected: (A) upstream's three only — leaves #3's rules unenforced; (C) adding style checks (slug/filename mismatch, tags not a list, empty body) — cosmetic, and #3 says malformed optional fields are tolerated, so they would be noise. Every check must skip, never throw, on absent/null/scalar/non-mapping frontmatter fields.
2. **No auto-fix in v1 (Q3 → C).** All findings are report-only. This narrows #19's wording that structural lint is "mechanically auto-fixable"; that claim is superseded by this decision. Rejected: (A) restricted deterministic fixes (case/slug link rewrite, set type from folder, default fields) and (B) additionally upstream's content-creating fixes (stub page for broken link, append wikilink to orphan) — the user chose not to have the app write into Obsidian-shared Markdown unprompted. The deterministic fix candidates from A are the natural first thing to add if this is reopened.

## Routine choices

- **Trigger and surface (Q2 → B).** Lint runs manually (Run Lint) and automatically when the ingest queue drains (the same event that starts the review sweep, #19/#8). Its view has its own rail item with a finding-count badge, a list grouped by check, click to open the page in Preview. Results are recomputed each run and not stored; no `ingest.db` table. Rejected: manual-only (stale between runs); a tab inside Review Mode (contradicts #19).
- **Row actions (Q4 → B).** "Open page" (jump to the page in Preview, to the line when known) and "Fix with chat", which starts a chat turn pre-filled with the finding(s) so the agent proposes and applies the edit through its normal tools (`vault_read`/`vault_write`, #11; no new fix engine). Rejected: open-only (no path to repair); adding a persistent per-finding Ignore (would add stored state that Q2 avoided; #19's won't-fix covers judgment calls, not deterministic checks).
- **Execution.** Pure local file reads, run off the UI thread; no LLM or network calls.

## Verified facts

- Upstream llm_wiki structural lint is `orphan | broken-link | no-outlinks`, runs in a Web Worker, is manual only, has non-persistent incrementing IDs (each run clears and repopulates), and has fixes `appendWikilink`, `ensureBrokenLinkStub`, `rewriteWikilinkTarget` (from #19's research, `docs/review-system-design.md`).
- #3 requires `type`/`title`/`sources[]`, six types in typed folders, case-insensitive title wikilinks with alias support, and tolerant reads everywhere.

## Risks

- Report-only means a large vault can accumulate findings (e.g. many orphans) with only a per-finding "Fix with chat" path; no bulk repair.
- "Fix with chat" relies on the unapproved `vault_write` tool; the agent could edit more than the finding warrants (mitigated by pre-filled prompt scoping, not enforced).
- Duplicate-title and orphan results depend on the same wikilink resolver as the graph (#9); the two must share one implementation to avoid disagreement.
- Running after every queue drain on a very large vault may be slow; the off-thread run must be cancellable/coalesced.

## Deferred

- Deterministic one-click fixes (Q3 option A) — reopen if "Fix with chat" proves too heavy for trivial repairs.
- Persistent per-finding Ignore — reopen if recurring false positives (e.g. intentional orphans) annoy users.
- Style checks (Q1 option C).
- Bulk "Fix all with chat".

## Open threads

None.
