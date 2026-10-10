# Coding standards

Read during review, not implementation. Judgement calls only: anything ruff, mypy, pydoclint or pre-commit enforces is not listed here. The domain vocabulary is in `CONTEXT.md`.

## Persisted state

- Write persisted files (registry, vault config, pages) atomically: temp file in the same directory, then `os.replace`. Use `mindstew.vault.atomic_write_text`.
- Treat a corrupt or non-mapping user-owned file as an error to report, never as empty to overwrite.
- A write that spans several files undoes the files it already wrote when a later one fails.

## Tolerant reading

- Every reader of YAML frontmatter, `providers.json`, `config.yaml` or other hand-editable files returns a result plus a notice instead of raising on absent, null, scalar or non-mapping values. Guard with `isinstance`.
- Each new reader ships a malformed-input test covering those four shapes.

## Secrets and errors

- Secrets live only in the Keychain. Registry files hold a flag, never a value.
- Error messages, logs and CLI output carry status and reason only: no response bodies, credentials, or URLs with userinfo or key query strings.
- A failed Keychain read raises; it never degrades to an unauthenticated request.

## Boundaries

- The core is Qt-free. Anything a GUI will observe is an event, and callbacks run on the emitting thread.
- Code that calls a provider goes through `adapter.complete` / `adapter.ping` as module attributes, so `fake_adapter` can replace them.
- Only the directories named in the vault layout are written to. `sources/` is read-only to the app.

## Types

- A closed set of strings (queue status, event kind, role, page type) is a `Literal` or `Enum` defined once, not repeated as string literals.
- A value pair that travels together (provider id and model) is one small type, not a tuple.

## Structure

- A module changes for one reason. When `cli.py` gains a second unrelated responsibility, move that logic into its own module and keep the click command thin.
- Prefer reusing an existing helper over a near-duplicate, as with the single shared event printer in the ingest and watch commands.
- Add no parameter, class or option the ticket's acceptance criteria don't need.
