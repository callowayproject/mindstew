# Project export/import archive format

Wayfinder ticket #24 of map #1. A **vault archive** is a single standard `.zip` of the vault tree plus a root `manifest.json`. Export always ships the full vault (sources, wiki, purpose/schema, vault config, vault-local skills) plus a small portable-state file; it never ships providers, secrets, the LanceDB index, or pure-derived tables. Import always creates a new vault in a new folder after validating the archive; there is no merge or overwrite.

## Terms

- **Vault archive** — A single file produced by Export Project that Import Project can turn back into a vault. _Avoid_: backup, bundle, package.
- **Derived data** — Anything under `.mindstew/index/` or `.mindstew/cache/` that can be rebuilt from `sources/` and `wiki/` (LanceDB, derived `ingest.db` tables). _Avoid_: cache, index files.
- **Portable state** — The non-derivable subset of `ingest.db` that travels in the archive as `portable-state.json`: review flags (including dismissed "won't-fix" markers, #19) and image caption records (#20).

## Why

The vault is already a plain Markdown folder, Obsidian-compatible (#2). Users need to move a vault between machines or share it, without mindstew-specific tooling and without leaking credentials. But `ingest.db` mixes rebuildable tables with state that cannot be recomputed for free (paid vision captions, user dismissals).

## Locked decisions

1. **Container: standard zip + `manifest.json` (Q1).** Stdlib `zipfile`, opens in Finder and on any OS; a recipient can unzip it into a working Obsidian vault without mindstew. `manifest.json` carries format version, app version, export time. _Rejected:_ macOS bundle directory (fragile when emailed/uploaded, no compression); tar.gz (no benefit for Mac users, less native).
2. **Derived data is rebuilt, portable state is exported (Q2).** Exclude LanceDB (`.mindstew/index/`), `cache/`, and pure-derived `ingest.db` tables (graph edges/communities, whole-file hash cache, queue). Include `portable-state.json` serialising review flags and image caption records. Import rebuilds embeddings and the graph. _Rejected:_ exclude everything (loses paid captions and dismissals); include everything verbatim (drags queue and DB schema version across machines, couples archive to the embedding route, large); an "Include search index" checkbox (extra option and coupling for little value).
3. **Config and secrets (Q3).** Include `.mindstew/config.yaml` (route overrides) and vault-local skills `.mindstew/skills/` (#22). Never include providers (machine-global, #21; custom headers can hide credentials) or Keychain secrets. On import, a route pointing at a provider the importing machine lacks is dropped back to the global default with a notice; an embedding-route change falls under #21's existing re-embed warning. _Rejected:_ embedding provider definitions in the archive (secret leakage via headers, silently mutates importer's registry); excluding config entirely (loses the vault's own routing choices).
4. **Collisions: import always creates a new vault (Q4).** User picks the parent folder; folder and display name get a numeric suffix on collision; registered in `projects.json` (#2). No merge, no overwrite, no vault-ID detection. _Rejected:_ import-into-existing merge mode (conflict resolution is its own product; risks corrupting wikilinks/graph/index); replace-by-manifest-ID (destructive).

## Routine choices

- **Import validation (Q5):** reject path traversal, absolute paths, symlinks, and entries outside the known tree; enforce size limits (zip-bomb guard). Refuse archives with a newer format version and prompt to update the app; migrate older versions forward on import. A missing or malformed `portable-state.json` is skipped with a notice and the vault still opens (consistent with the defensive-parsing rule from #3).
- **Export scope (Q6):** always the full vault, no options. Wiki pages cite sources by relative path (#3), and re-ingest, caption records, and hashes assume `sources/` exists; a wiki-only archive would dangle.

## Verified facts

- Explored repo docs: `docs/` holds sibling design docs for #19–#23; `CONTEXT.md` previously defined only Skill and Skill source.

## Risks

- `portable-state.json` is a second format to version alongside `manifest.json`; it must stay in step with `review_flags` and caption-record schemas (#19, #20).
- Large `sources/` makes archives big and export slow; no option to exclude them in v1.
- Re-embedding after import costs money and time on a large vault; BM25-only search applies until it completes (#21).

## Deferred

- "Include sources" checkbox / wiki-only export — reopen if sharing-without-sources becomes a real request.
- Merge or "update my copy" import — reopen if users need to reconcile diverged vault copies.

## Open threads

None.
