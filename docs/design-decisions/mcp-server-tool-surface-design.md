# MCP server tool surface

mindstew bundles a local MCP server exposing four of #11's five shared tools — `wiki_search`, `vault_read`, `wiki_write` (the MCP-facing name for `vault_write`), and `enqueue_ingest` — over stdio, as a standalone executable any MCP client spawns via its own config. `shell_exec` is deliberately excluded from this surface: it stays a chat-agent-only tool, kept inside the one UI (approval card + #16's sandbox-exec confinement) it was designed and vetted for.

## Terms

- **MCP surface** — The set of tools the bundled MCP server exposes to external clients (Claude Desktop, Claude Code, other MCP-aware IDEs/agents), as distinct from the tools the in-app chat agent uses. _Avoid: "tool list", "API"._
- **elicitation** — An MCP spec primitive (introduced 2025-06-18) letting a server pause mid-call and ask the client's UI for structured input (accept/decline/cancel) — usable for approval prompts but not approval-specific. _Avoid: "confirmation dialog", "approval API"._

## Why

Issue #11 defined five shared, Pydantic-typed tools (`wiki_search`, `vault_read`, `vault_write`, `shell_exec`, `enqueue_ingest`) meant to be reusable by both the in-app chat agent and the future MCP server. This ticket had to decide what actually crosses over to external MCP clients, since "reusable" doesn't mean "identical surface" — an arbitrary external client has none of the in-app chat transcript's context or UX.

## Locked decisions

### Tool surface excludes shell_exec

**Decision:** The MCP server exposes `wiki_search`, `vault_read`, `vault_write` (renamed `wiki_write`, see below), and `enqueue_ingest` as-is. `shell_exec` is not exposed on the MCP surface at all.

**Rejected options:**
- *Expose all five, gating shell_exec with an MCP elicitation prompt* — Research turned up that MCP does have a human-in-the-loop primitive, **elicitation** (spec 2025-06-18, `client/elicitation`): a server can pause a call and ask the client to prompt the human with a small accept/decline/cancel form. But it's general-purpose (not approval-specific), the spec itself says servers must not rely on it for anything sensitive and that adoption across clients is still uneven, and MCP's own tool-annotation spec (2025-03-26) explicitly disclaims annotations/hints as an authorization substitute. Rejected because it would put mindstew's most dangerous tool behind a best-effort, not-guaranteed-present gate.
- *Expose all five with no extra gate, relying entirely on the connecting client's own approval UX* — Interactive clients (Claude Desktop, Claude Code) do already gate MCP tool calls with native per-call approval dialogs in front of anything the server does, which makes a server-side wrapper feel redundant for them. But that native gate isn't guaranteed for a programmatic/headless MCP client, and `shell_exec`'s entire design (approval card, denial fed back as a tool result, session-scoped remembering, #16's sandbox-exec confinement) was purpose-built around the chat transcript's specific UX — not something that degrades gracefully onto a client we don't control. Rejected for the same reason as above, more starkly: zero gate is a strictly worse version of the elicitation option.

**Why A won:** Keeping `shell_exec` inside the one UI it was actually designed and vetted for (#11's approval card, #16's Seatbelt confinement) bounds the MCP server's blast radius to read + scoped-write. Revisit once elicitation adoption matures across major MCP clients — this is a v1 decision, not a permanent one.

### Transport: stdio, standalone executable

**Decision:** stdio only, as a standalone launchable executable that a client's own MCP config spawns directly — independent of whether the mindstew GUI app is running.

**Rejected options:**
- *stdio, but only runnable while the mindstew app is running (app-managed subprocess)* — Rejected: couples the MCP server's availability to the GUI app's lifecycle for no real benefit, and blocks the useful case of querying the vault from an editor/IDE while mindstew.app itself is closed.
- *HTTP/SSE (persistent local server), local-only bind* — Rejected: adds a real surface (bind address, port conflicts, local auth) that nothing in the destination's stated scope asks for; every major MCP client (Claude Desktop, Claude Code, IDE integrations) defaults to spawning a stdio subprocess per its own config anyway.
- *Both stdio and HTTP/SSE* — Rejected for the same reason as HTTP/SSE alone, plus the added cost of maintaining two transports for one v1 use case.

**Why A won:** Matches what every major MCP client expects out of the box with zero extra surface (no bind address, no port, no multi-client story), and decouples the server's availability from the GUI app.

### vault_write is renamed wiki_write on the MCP surface, scope carried in name + schema

**Decision:** The MCP-facing tool is named `wiki_write` (not `vault_write`), and its JSON Schema description states the writable scope in prose (paths relative to `wiki/`, or `purpose.md`/`schema.md`); the server rejects out-of-scope paths with a clear error.

**Rejected options:**
- *Rely on schema + description alone, keep the internal name `vault_write`* — Rejected: an external MCP client's model only ever sees the tool name, its description, and its schema — there's no shared app chrome to lean on the way the in-app chat agent has. A generic name like `vault_write` doesn't itself signal the restriction; the rename does the work the description alone would otherwise have to carry unaided.
- *Add a dedicated MCP resource/prompt listing the writable scope, separate from the tool description* — Rejected: introduces a second artifact that has to stay in sync with the tool's own schema description, for no real gain over just writing the restriction into the description once.

**Why the chosen option won:** A precise name (`wiki_write`) plus a schema-level description puts the entire scope restriction in the two places any MCP client actually surfaces to a human or model before calling the tool — no extra artifact to keep in sync.

## Routine choices

- Bind address / configurable-vs-local-only is moot: stdio has no bind address, so this question was dropped once transport was settled.
- `wiki_search`, `vault_read`, and `enqueue_ingest` cross over to the MCP surface unchanged (same names, same schemas) — only `vault_write` needed MCP-specific framing, since it's the one mutating tool.

## Verified facts

From background research into the MCP spec (see sources below), established rather than asked:

- MCP's **elicitation** capability (spec 2025-06-18) is the only spec-level primitive for mid-call human-in-the-loop interaction; it is general-purpose (flat JSON Schema input, accept/decline/cancel), not approval-specific, and the spec itself says it must not be used for sensitive information.
- **roots** and **sampling** are unrelated to approval gating: roots scopes filesystem/URI boundaries, sampling lets a server request an LLM completion via the client.
- Claude Desktop and Claude Code both already gate MCP tool calls with their own native per-call approval UX, independent of anything the server does; MCP tool annotations (`readOnlyHint`, `destructiveHint`, etc., spec 2025-03-26) are explicitly disclaimed by the spec as untrusted hints, not an authorization substitute.
- No single dominant convention exists yet among MCP shell/exec servers for gating dangerous commands — approaches split between static allowlisting, a required `confirm: true` param, delegating to a separate confirmation MCP server, or relying on elicitation itself.

Sources: [MCP elicitation spec](https://modelcontextprotocol.io/specification/2025-06-18/client/elicitation), [MCP tool annotations blog post](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/), [mcp-exec](https://github.com/bensons/mcp-exec), [mcp-confirm](https://github.com/mako10k/mcp-confirm), [mcp-shell](https://github.com/sonirico/mcp-shell), [mcp-shell-server](https://github.com/tumf/mcp-shell-server).

## Risks

- Excluding `shell_exec` from the MCP surface means external MCP clients can't drive shell commands through mindstew at all in v1 — acceptable given the destination's stated scope, but a real capability gap if a future use case needs it.
- Elicitation adoption is genuinely new and uneven; if a common, well-supported approval pattern emerges across major MCP clients, the shell_exec-exclusion decision is a natural candidate to revisit (not a scope change, just a v2 reconsideration).

## Deferred

None — every sub-question this ticket raised was resolved this session.

## Open threads

None.
