# mindstew

mindstew turns a folder of Markdown and text documents into a linked, Obsidian-compatible wiki, using any OpenAI-compatible model (OpenAI, Ollama, LM Studio, OpenRouter).

> [!NOTE]
> mindstew is alpha software. Today it ships as a macOS command-line tool.

## Install

Requires macOS, Python 3.14 or later, and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install git+https://github.com/callowayproject/mindstew
```

## Quickstart

```bash
mindstew new ~/notes
mindstew provider add ollama --base-url http://localhost:11434/v1
mindstew provider set-route ingest ollama llama3.1
mindstew ingest ~/notes ~/Documents/meeting-notes.md
mindstew ls ~/notes
```

## Documentation

Full documentation is at <https://callowayproject.github.io/mindstew>:

- [Getting started](docs/getting-started.md)
- [Tutorial](docs/tutorial.md)
- [Concepts](docs/concepts.md)
- [CLI reference](docs/reference/cli.md)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## License

See [LICENSE](LICENSE).
