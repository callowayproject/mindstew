# Ingesting sources

This guide shows how to add documents to a vault, monitor progress, and recover from failures.

## Before you begin

- You have a vault. See [Getting started](../getting-started.md).
- An `ingest` route is configured. See [Configuring providers](./configure-providers.md).

## Ingest everything in sources

Run `ingest` with only the vault path to process every `.md` and `.txt` file under `sources/`:

```bash
mindstew ingest ~/notes
```

If nothing is pending, mindstew prints `nothing to ingest`.

## Ingest a file or folder from elsewhere

Pass a path after the vault. mindstew copies supported files into `sources/` and ingests them:

```bash
mindstew ingest ~/notes ~/Documents/research
```

- Folder structure is preserved under `sources/`.
- Hidden files and folders (names starting with `.`) are skipped silently.
- Unsupported file types print `skipped (unsupported)`.
- If a different file with the same name already exists in `sources/`, mindstew keeps it and prints `skipped (exists in sources/, not overwritten)`.

## Check the queue

```bash
mindstew status ~/notes
```

```text
queued: 0  running: 0  done: 3  failed: 1
done	spaced-repetition.md
failed	broken.md	no ingest route configured; ...
```

## Retry a failed item

mindstew tries each item up to three times. After that the item stays `failed`. Fix the cause, then run `ingest` again. A repeat run requeues failed items whose content is unchanged.

```bash
mindstew ingest ~/notes
```

`ingest` exits with an error if any item it processed ends in `failed`.

## Regenerate a page

Use `--reingest` to rewrite a page from the sources listed in its frontmatter. This is useful after you edit `purpose.md` or switch models.

```bash
mindstew ingest ~/notes --reingest concepts/spaced-repetition.md
```

mindstew overwrites the page with the generated page that has the same title. If the model returns other pages, they are added as new pages.

> [!WARNING]
> `--reingest` replaces the page's contents, including any manual edits.

## Ingest automatically

`watch` ingests new and changed files until you press **Ctrl-C**. Without a folder, it watches `sources/`:

```bash
mindstew watch ~/notes
```

Pass a folder to watch it instead. mindstew copies its files into `sources/`, overwriting older copies:

```bash
mindstew watch ~/notes ~/Downloads/inbox
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `no ingest route configured` | No route for the `ingest` role | Run `mindstew provider set-route ingest PROVIDER MODEL` |
| `unsupported source type` | The file is not `.md` or `.txt` | Convert it to Markdown or text |
| `unreachable` or `auth-failed` errors | Provider is down or the key is wrong | Run `mindstew provider test PROVIDER` |
| `model returned unknown page type` | The model ignored the schema | Retry, or use a model with stronger structured-output support |
| A file is not re-ingested | Its content is unchanged | Edit the file, or use `--reingest` on its page |
