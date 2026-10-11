# Configuring providers

This guide shows how to register a model provider, route roles to models, and override routes for one vault.

## Before you begin

You need the base URL of an OpenAI-compatible API and, for hosted services, an API key.

| Service | Base URL |
|---------|----------|
| OpenAI | `https://api.openai.com/v1` |
| Ollama | `http://localhost:11434/v1` |
| LM Studio | `http://localhost:1234/v1` |
| OpenRouter | `https://openrouter.ai/api/v1` |

## Add a provider

Pass `--api-key` to be prompted for the key. The key is saved in the macOS Keychain, not in a file.

```bash
mindstew provider add openai --base-url https://api.openai.com/v1 --api-key
```

```text
API key: 
Added provider openai
```

Options:

- `--name`: a display name. The default is the id.
- `--header NAME=VALUE`: an extra, non-secret header. Repeatable.
- `--secret-header NAME`: prompts for an extra header whose value is stored in the Keychain. Repeatable.

Adding a provider with an existing id replaces it.

## Test the provider

```bash
mindstew provider test openai
```

| Output | Exit code | Meaning |
|--------|-----------|---------|
| `reachable: openai` | 0 | The endpoint answered and accepted the credentials |
| Error message | 1 | Unknown provider or another failure |
| `auth-failed: ...` | 2 | The key was rejected |
| `unreachable: ...` | 3 | The endpoint could not be reached |

## Route a role to a model

Bind a role (`chat`, `ingest`, `embedding`, or `vision`) to a provider and model:

```bash
mindstew provider set-route ingest openai gpt-4o-mini
```

```text
ingest -> openai / gpt-4o-mini
```

mindstew requires a model that supports structured JSON output (`response_format` with a JSON schema).

## Override a route for one vault

Add `--vault` to write the route to that vault's `.mindstew/config.yaml` instead of the global settings:

```bash
mindstew provider set-route ingest ollama llama3.1 --vault ~/notes
```

The file then contains:

```yaml
routes:
  ingest:
    provider: ollama
    model: llama3.1
```

A vault can override routes only. Providers must be registered globally.

## List providers and routes

```bash
mindstew provider ls
mindstew provider ls --vault ~/notes   # show effective routes for a vault
```

## Remove a provider

```bash
mindstew provider rm openai
```

This also deletes the provider's Keychain secrets and any global routes that use it.

## Where settings are stored

| Item | Location |
|------|----------|
| Providers and global routes | `providers.json` |
| Project registry | `projects.json`, next to `providers.json` |
| Vault route overrides | `<vault>/.mindstew/config.yaml` |
| API keys and secret headers | macOS Keychain, service `mindstew` |

`providers.json` lives in `~/Library/Application Support/mindstew`. Set the `MINDSTEW_HOME` environment variable to use a different folder.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `notice: ... names unknown provider` | A route points at a provider you removed. Add the provider again or set a new route. |
| `refusing to overwrite vault config` | `.mindstew/config.yaml` is not valid YAML or not a mapping. Fix or delete it. |
| `unknown role` | Use one of `chat`, `ingest`, `embedding`, `vision`. |
