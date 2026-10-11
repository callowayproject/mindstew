# Getting started

mindstew turns a folder of Markdown and text documents into a linked wiki, using a language model you choose. This page gets you from install to your first generated wiki page.

## Prerequisites

- macOS. Provider secrets are stored in the system keyring, and the project registry defaults to `~/Library/Application Support/mindstew`.
- Python 3.14 or later and [uv](https://docs.astral.sh/uv/).
- An OpenAI-compatible model endpoint, such as OpenAI, [Ollama](https://ollama.com), LM Studio, or OpenRouter.

## Install

Install the `mindstew` command from the GitHub repository:

```bash
uv tool install git+https://github.com/callowayproject/mindstew
```

Check that it works:

```bash
mindstew --help
```

## Create a wiki

1. Create a vault, which is the folder that holds your documents and the generated wiki:

    ```bash
    mindstew new ~/notes
    ```

    ```text
    Created vault at /Users/you/notes
    ```

2. Register a model provider. This example uses a local Ollama server:

    ```bash
    mindstew provider add ollama --base-url http://localhost:11434/v1
    mindstew provider set-route ingest ollama llama3.1
    ```

3. Copy a document into the vault and ingest it:

    ```bash
    mindstew ingest ~/notes ~/Documents/meeting-notes.md
    ```

    ```text
    started: meeting-notes.md
    finished: meeting-notes.md
    ```

4. List the pages that were generated:

    ```bash
    mindstew ls ~/notes
    ```

## Next steps

- Follow the [tutorial](./tutorial.md) for a complete walkthrough.
- Read [Concepts](./concepts.md) to understand vaults, pages, and routes.
- Look up every command in the [CLI reference](./reference/cli.md).
