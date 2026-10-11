# Tutorial: building your first wiki

In this tutorial you create a vault, connect a local model, ingest two documents, and explore the generated pages. It takes about 15 minutes.

## Before you begin

- Install mindstew as described in [Getting started](./getting-started.md).
- Install [Ollama](https://ollama.com) and pull a model that supports structured JSON output:

    ```bash
    ollama pull llama3.1
    ```

Any OpenAI-compatible provider works. Substitute your own base URL and model name.

## 1. Create the vault

```bash
mindstew new ~/tutorial-wiki
```

Open `~/tutorial-wiki/purpose.md` and replace its contents with a sentence or two about your wiki, for example:

```markdown
# Purpose

Notes on how I learn. Emphasize techniques and the people who developed them.
```

mindstew reads this file on every ingest.

## 2. Connect a model

Register the provider, then route the `ingest` role to a model:

```bash
mindstew provider add ollama --base-url http://localhost:11434/v1
mindstew provider set-route ingest ollama llama3.1
mindstew provider test ollama
```

```text
reachable: ollama
```

If the test prints `unreachable`, check that Ollama is running. See [Configure providers](./how-to/configure-providers.md#troubleshooting).

## 3. Add two documents

Create `~/tutorial-wiki/sources/spaced-repetition.md`:

```markdown
# Spaced repetition

Spaced repetition schedules reviews at increasing intervals. Hermann Ebbinghaus
described the forgetting curve that motivates it.
```

Create `~/tutorial-wiki/sources/active-recall.md`:

```markdown
# Active recall

Active recall means testing yourself instead of rereading. It pairs well with
spaced repetition.
```

## 4. Ingest

```bash
mindstew ingest ~/tutorial-wiki
```

mindstew prints progress for each file:

```text
started: active-recall.md
finished: active-recall.md
started: spaced-repetition.md
finished: spaced-repetition.md
```

The page titles depend on your model.

## 5. Explore the wiki

List the pages. Each line shows the path, type, and title:

```bash
mindstew ls ~/tutorial-wiki
```

Print one page, using the path from the listing:

```bash
mindstew show ~/tutorial-wiki concepts/spaced-repetition.md
```

The output ends with the page's `[[wikilinks]]` and the page each one points to. `(unresolved)` means no page has that title yet.

You can also open `~/tutorial-wiki` in Obsidian to browse and graph the pages.

## 6. Keep it up to date

Leave `watch` running and drop new files into `sources/`:

```bash
mindstew watch ~/tutorial-wiki
```

mindstew ingests each new or changed file once it finishes writing. Press **Ctrl-C** to stop.

To regenerate a single page from its sources, for example after editing `purpose.md`:

```bash
mindstew ingest ~/tutorial-wiki --reingest concepts/spaced-repetition.md
```

## Next steps

- [Ingest sources](./how-to/ingest-sources.md) covers folders, failures, and re-ingesting.
- [CLI reference](./reference/cli.md) lists every option.
