# Concepts

This page explains the ideas behind mindstew so the commands make sense.

## About vaults

A **vault** is a folder that holds your source documents and the wiki generated from them. It is [Obsidian](https://obsidian.md)-compatible, so you can open it in Obsidian, but mindstew never creates an `.obsidian/` folder.

```text
my-vault/
├── purpose.md        # what the wiki is for
├── schema.md         # how pages are structured
├── sources/          # your original documents
├── wiki/
│   ├── entities/
│   ├── concepts/
│   ├── sources/
│   ├── queries/
│   ├── comparisons/
│   └── synthesis/
└── .mindstew/
    ├── config.yaml   # per-vault route overrides
    ├── skills/
    ├── index/        # derived data
    └── cache/        # derived data
```

`mindstew new` and `mindstew open` only create what is missing. They never overwrite or modify existing files.

- Use `new` for a fresh folder. It refuses if the vault is already complete.
- Use `open` to adopt an existing folder, such as an Obsidian vault. Running it on a complete vault does nothing.

Both commands stop without changing anything if a file or symlink blocks a scaffold path, for example a file named `wiki`.

## About sources and pages

**Sources** are the documents you put in `sources/`. mindstew ingests Markdown (`.md`) and plain text (`.txt`) files.

**Pages** are the Markdown files mindstew generates in `wiki/`. Each page lives in a folder for its type and starts with YAML frontmatter:

```yaml
---
type: concept
title: Spaced repetition
sources: [sources/learning.md]
tags: [memory]
---
```

| Type | Folder |
|------|--------|
| `entity` | `wiki/entities/` |
| `concept` | `wiki/concepts/` |
| `source` | `wiki/sources/` |
| `query` | `wiki/queries/` |
| `comparison` | `wiki/comparisons/` |
| `synthesis` | `wiki/synthesis/` |

Pages link to each other with `[[wikilinks]]`. A link matches a page title or alias, ignoring case. `mindstew show` lists each page's links and marks the ones that resolve to no page as unresolved.

## About purpose and schema

`purpose.md` and `schema.md` are plain Markdown files you can edit. During ingest, mindstew sends both to the model along with the source. Describe your goals in `purpose.md` to steer which pages the model writes.

## About ingest

Ingesting a source runs two model calls:

1. **Analyze.** The model summarizes the source and plans which pages it warrants.
2. **Write.** The model produces those pages.

mindstew validates every generated page before writing any of them, so a failed ingest leaves no partial pages. New pages never overwrite existing ones. A title that already exists gets a numbered file name such as `spaced-repetition-2.md`.

Sources are queued and processed one at a time. mindstew records a hash of each file, so unchanged files are skipped on later runs. A failed item is retried, up to three attempts in total.

## About providers and roles

A **provider** is a named model endpoint with a base URL and optional credentials. mindstew speaks the OpenAI-compatible API, so any service that offers it works.

A **role** says what a model is used for: `chat`, `ingest`, `embedding`, or `vision`. A **route** binds a role to a provider and a model name.

Today the `ingest` role is the only one the CLI uses. You can store routes for the other roles.

Routes can be set in two places:

- **Globally**, in `providers.json`, for every vault.
- **Per vault**, in `.mindstew/config.yaml`, where they override the global route for that vault only.

Secrets such as API keys go in the macOS Keychain. They are never written to `providers.json` or any vault file.

## About derived data

Everything under `.mindstew/index/` and `.mindstew/cache/` is **derived data**. You can delete it and mindstew rebuilds it from `sources/` and `wiki/`. The ingest queue is kept in `.mindstew/index/ingest.db`.

## Next steps

- [Ingest sources](./how-to/ingest-sources.md)
- [Configure providers](./how-to/configure-providers.md)
