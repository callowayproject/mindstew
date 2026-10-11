# Wikilink resolver rules (#39, #40)

The shared wikilink resolver resolves a target by trying two candidate texts (the full text before any `|display`, then the text stripped at the first `#` or `^`) and, for each, three page-name tiers in order: filename stem, title, alias. `\|` is read as the display separator. Bare stems only. Ties go to the first page by sorted path. Decided during triage of issues #39 and #40; agent briefs are on those issues.

## Terms

- **Wikilink target**: the text inside `[[...]]` that names a page. Avoid: link text, slug.
- **Page name**: a string a target can match: a filename stem, a title or an alias. Avoid: key.

## Why

Today `extract_links` splits on the first `|`, `#` or `^` and keeps the left part. So `[[A\|b]]` (table-escaped pipe) yields `A\`, a page titled `C# notes` can never resolve, and a page without a valid `title` is unreachable although Obsidian resolves by filename.

## Locked decisions

- **Stem ranks first: stem, then title, then alias (Q3).** Chosen over title, alias, stem (the recommendation) and over stem-only-for-titleless pages and no fallback. It matches Obsidian. Cost: when page X's stem equals page Y's title, `[[name]]` now resolves to X, which can change an existing link.
- **Full text through all tiers, then stripped text through all tiers (Q4).** Rejected a per-tier interleave, which lets a short stem steal a link that exactly names another page's title. The more specific text always wins.

## Routine choices

- Q1: try the full pre-`|display` text first, then the form stripped at `#`/`^`. Rejected always stripping (titles with `# | ^` unsupported) and longest-prefix search (ambiguity for little gain). `extract_links` returns the raw target so the resolver can try both.
- Q2: `\|` is the display separator (`[[A\|b]]` targets `A`). Rejected treating it as a literal pipe in the name; a literal pipe in a title is reachable through Q1's full-text lookup.
- Q5: bare stems only; folder-qualified targets like `entities/ada` are not matched. Ties go to the first page by sorted path, as for titles and aliases.

## Verified facts

- `extract_links('[[A\\|b]]')` returns `['A\\']` and `extract_links('[[C# notes]]')` returns `['C']`.
- `Resolver` indexes titles, then aliases; titles win via `setdefault` in two passes.

## Risks

- Stem-first can silently change existing resolutions (see Q3). The #40 brief requires updating existing tests only where a stem legitimately wins.

## Deferred

- Folder-qualified targets. Reopen if duplicate stems across folders become common.

## Open threads

None.
