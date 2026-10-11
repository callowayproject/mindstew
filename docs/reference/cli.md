# CLI reference

```text
mindstew COMMAND [ARGS]...
```

Every `VAULT` argument must be an existing folder. Page paths are relative to the vault's `wiki/` folder.

## new

Create a fresh vault.

```text
mindstew new PATH
```

Creates only missing files and folders, and registers the vault in the project registry. Fails if `PATH` is already a complete vault, or if an entry of the wrong kind blocks a scaffold path.

## open

Adopt an existing folder as a vault.

```text
mindstew open PATH
```

Adds only missing scaffolding. On a complete vault it prints `PATH is already a vault` and changes nothing. `PATH` must exist.

## ls

List pages, or registered vaults.

```text
mindstew ls [VAULT]
```

With `VAULT`, prints one tab-separated line per page: path, type, title. Without it, prints the registered vaults, most recently used first, and marks missing folders with `(missing)`.

## show

Print a page.

```text
mindstew show VAULT PAGE
```

Prints `type`, `title`, `sources`, `tags`, the body, and a `links:` list showing which page each `[[wikilink]]` resolves to.

## ingest

Ingest sources and run the queue.

```text
mindstew ingest VAULT [PATH] [--reingest PAGE]
```

| Argument or option | Description |
|--------------------|-------------|
| `PATH` | A file or folder to ingest. Files are copied into `sources/`. Default: everything in `sources/`. |
| `--reingest PAGE` | Regenerate `PAGE` from the sources in its frontmatter. |

Supported source types: `.md`, `.txt`. Exits non-zero if any processed item fails. See [Ingesting sources](../how-to/ingest-sources.md).

## watch

Ingest new and changed files continuously.

```text
mindstew watch VAULT [FOLDER]
```

Watches `sources/`, or `FOLDER` (copying its files into `sources/`). A file is queued after its size stops changing. Press **Ctrl-C** to stop.

## status

Show the ingest queue.

```text
mindstew status VAULT
```

Prints counts for `queued`, `running`, `done`, and `failed`, then one tab-separated line per item: status, file name, error.

## provider

Manage model providers and routes. See [Configuring providers](../how-to/configure-providers.md).

### provider add

```text
mindstew provider add PROVIDER_ID --base-url URL [OPTIONS]
```

| Option | Description |
|--------|-------------|
| `--base-url` | Required. The API base URL. |
| `--name` | Display name. Default: the id. |
| `--kind` | Provider kind. Default and only supported value: `openai-compatible`. |
| `--api-key` | Prompt for an API key, stored in the Keychain. |
| `--header NAME=VALUE` | Extra non-secret header. Repeatable. |
| `--secret-header NAME` | Prompt for a secret header value. Repeatable. |

### provider ls

```text
mindstew provider ls [--vault VAULT]
```

Lists providers (id, kind, base URL), then routes (role, provider, model). With `--vault`, shows the effective routes for that vault.

### provider rm

```text
mindstew provider rm PROVIDER_ID
```

### provider test

```text
mindstew provider test PROVIDER_ID
```

Exit codes: `0` reachable, `1` error, `2` auth failed, `3` unreachable.

### provider set-route

```text
mindstew provider set-route ROLE PROVIDER_ID MODEL [--vault VAULT]
```

`ROLE` is one of `chat`, `ingest`, `embedding`, `vision`. With `--vault`, the route overrides the global one for that vault only.

## Environment variables

| Variable | Description |
|----------|-------------|
| `MINDSTEW_HOME` | Folder for `projects.json` and `providers.json`. Default: `~/Library/Application Support/mindstew`. |
