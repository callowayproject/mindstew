# Testing seams

Run everything through `uv run pytest` and `uv run ruff check`. Tests never touch a real provider, the real Keychain, or real Application Support.

## Autouse fixtures (`tests/conftest.py`)

- `mindstew_home` sets `MINDSTEW_HOME` to a temp dir, so the project registry and `providers.json` are isolated.
- `fake_keyring` swaps in an in-memory keyring and yields its backing dict, keyed `(service, "<provider-id>/api_key")` with service `mindstew`.
- `no_retry_delay` zeroes `mindstew.worker.RETRY_DELAY`. A test that needs the real backoff sets its own.

## Opt-in fixtures

- `make_vault(name)` returns a fresh scaffolded vault root under `tmp_path`.
- `fake_adapter` replaces `mindstew.adapter.complete` and `ping`. Queue canned responses with `fake_adapter.respond(model_instance_or_exception, ...)` and assert on `fake_adapter.calls` (`(route, messages, output_type)`).

## Rules the fixtures depend on

- Call the adapter as `adapter.complete(...)` through the module. `from mindstew.adapter import complete` bypasses the fake.
- Drive the CLI with `click.testing.CliRunner`, and the worker with a `process` callable that raises or returns.
- HTTP behaviour of the real adapter is tested against a stub server on `127.0.0.1`.

## Live provider smoke test

`tests/test_live.py` calls a real OpenAI-compatible endpoint. It is skipped unless these are set:

```bash
MINDSTEW_LIVE_BASE_URL=https://openrouter.ai/api/v1 \
MINDSTEW_LIVE_MODEL=<model-id> \
MINDSTEW_LIVE_API_KEY=<key> \
uv run pytest tests/test_live.py -m live
```

`MINDSTEW_LIVE_API_KEY` is optional for local servers such as Ollama. The key is placed in the in-memory keyring and never reaches the real Keychain.
