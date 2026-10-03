# Settings / model-routing design

Wayfinder ticket #21 (map #1). Providers are a machine-global registry; routes (role → provider + model) are global defaults that a vault may override. Secrets live only in the macOS Keychain, one item per secret. Settings is a native Cmd+, window with Providers and Models tabs. Changing a vault's embedding route triggers a confirmed, queued re-embed.

## Terms

- **Provider** — a named endpoint + credential reference (OpenAI, Mistral, custom OpenAI-compatible URL) that can serve one or more roles. Avoid: backend, vendor.
- **Role** — a job the app gives a model: chat, ingest, embedding, vision. Avoid: task, purpose.
- **Route** — the binding of a role to a provider + model id. Avoid: mapping, assignment.

## Why

Chat, ingest, embeddings and image captioning all call cloud LLMs through one provider-agnostic adapter (#4, #5, #8, #20). Users need to choose providers and models, use gateways/local servers, keep keys safe, and not have a vault carry machine-specific secrets.

## Locked decisions

- **Layered config (q1 A).** Global registry holds providers and default routes (`~/Library/Application Support/mindstew/`). A vault's `.mindstew/config.yaml` may override **routes only**; providers never live in the vault. Rejected: fully per-vault (endpoints/headers would travel with synced vaults and break on other Macs); fully global (no per-project model choice, nowhere to record the embedding model).
- **Embedding route change (q5 A).** The vault records the embedding model id + dimension. On mismatch the app warns and offers a full re-embed, enqueued through the persistent ingest queue (#8); search degrades to BM25-only (#10) until done. Rejected: blocking the change (frustrating); silent background re-embed (hidden API spend).

## Routine choices

- **Roles (q2 A):** four roles — `chat`, `ingest` (CoT analysis, generation, and review-sweep judgment from #19), `embedding`, `vision` (captioning, #20). Per-step routing and "one model + embedding override" rejected.
- **Providers (q3 A):** provider = {name, kind (openai-compatible | anthropic | …), base_url, extra headers}; presets for known providers plus a Custom option. Preset-only and free-form-only rejected.
- **Keychain (q4 B):** one Keychain item per secret (`<provider-id>/api_key`, `<provider-id>/header/<name>`) via `keyring`. The registry file flags which headers are secret and never contains their values; the UI masks them. Rejected: one JSON blob per provider (read-modify-write coupling); plaintext headers in the registry.
- **UI (q6 A):** standard macOS Settings window (Cmd+,) with a Providers tab (global) and a Models tab (global defaults, with an "Override for this vault" toggle per role). Each provider has a "Test connection" button. Rejected: full-window rail mode (competes with Review Mode); hand-edited YAML only.

## Verified facts

None established beyond the closed tickets: #2 defines `.mindstew/config.yaml`; #5 chose OpenAI `text-embedding-3-small` default with Mistral as alternative; #20 requires a vision-capable model.

## Risks

- Vision role needs a vision-capable model; the UI should warn when the chosen model lacks image input (validation mechanism unspecified).
- Test-connection only proves reachability/auth, not capability per role.
- Re-embed on a large vault can be slow and costly; the confirm dialog should show an estimate.

## Deferred

- Per-step routing (reopen if users need to tune individual pipeline stages).
- Color/appearance and other non-model settings tabs.

## Open threads

None.
