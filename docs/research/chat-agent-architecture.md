# Research: Python architecture for the local tool-using chat agent

Resolves issue #4. Question: what should power mindstew's Python runtime for the
tool-using chat agent, given (1) a cloud-API-only, provider-agnostic LLM backend
requirement, (2) custom tools (wiki search, source read, graph traversal,
workspace file generation), (3) streaming, (4) cancellation, and (5) a
shell-command approval gate?

## A. Claude Agent SDK (Python) — `claude-agent-sdk-python`

**Provider lock-in: confirmed.** The official docs state the SDK supports only
the **Anthropic API, AWS Bedrock, and Google Vertex AI** as model backends,
configured via `model=` / `fallback_model=` on `ClaudeAgentOptions` — there is
no documented path to a generic OpenAI-compatible or arbitrary third-party
endpoint. (<https://code.claude.com/docs/en/agent-sdk/python>)

This is corroborated by a primary-source GitHub issue:
**anthropics/claude-agent-sdk-python#410**, "Question: Is it possible to use
Non-Anthropic models with Claude Agent SDK?" (opened Dec 11, 2025) — **closed
as "not planned."** No maintainer path to a LiteLLM-proxy workaround or
multi-provider support is offered in the thread.
(<https://github.com/anthropics/claude-agent-sdk-python/issues/410>) This
disqualifies A against requirement 1: the "LiteLLM-proxy workaround" (running
a LiteLLM proxy that impersonates the Anthropic API so the SDK's
Bedrock/Vertex-shaped client talks to it) is an indirection layer bolted onto
an SDK not designed for it, not a supported integration point.

Mechanics, for completeness (solid, but moot given the lock-in):

- **Tools**: `@tool(name, description, schema)` decorator, registered via
  `create_sdk_mcp_server(...)`, exposed through `mcp_servers=` /
  `allowed_tools=` on `ClaudeAgentOptions`.
- **Streaming**: `query()` (stateless, `AsyncIterator[Message]`, no interrupts)
  vs. `ClaudeSDKClient` (stateful session, supports interrupts).
- **Cancellation**: `ClaudeSDKClient.interrupt()` sends a stop signal but does
  not clear the buffer — the caller must drain `receive_response()` afterward
  (`ResultMessage.terminal_reason` of `"aborted_streaming"` /
  `"aborted_tools"`) before the next `query()`.
- **Shell approval gate**: `can_use_tool` callback on `ClaudeAgentOptions`,
  returning `PermissionResultAllow(updated_input=...)` (approve, optionally
  after editing the command) or `PermissionResultDeny(message=...,
  interrupt=True)`. This is the best-designed piece of A, but is disqualified
  along with the rest of the SDK by requirement 1.

## B. Hand-rolled tool-calling loop over LiteLLM

- **Universal call surface**: `litellm.completion()` / `acompletion()` take an
  OpenAI-style `messages=` + `tools=[{"type": "function", "function": {...}}]`
  payload and route to whichever provider string is in `model=` — this is the
  provider-agnostic surface requirement 1 needs.
  (<https://docs.litellm.ai/docs/completion/function_call>)
- **Capability probing**: `litellm.supports_function_calling(model=...)` and
  `litellm.supports_parallel_function_calling(model=...)` let the app validate
  a configured endpoint before enabling tool-calling.
- **Streaming**: `stream=True` returns a `CustomStreamWrapper` yielding
  `ModelResponseStream` chunks (partial content + partial tool-call deltas),
  confirmed provider-agnostic.
  (<https://docs.litellm.ai/docs/completion/stream>, <https://docs.litellm.ai/stream>)
- **Cancellation / approval: confirmed absent.** Nothing in LiteLLM's docs
  describes a cancellation token or an approval-gate primitive — it is a
  call-and-stream library, not an agent harness. The whole loop, cancellation
  (cancel your own `asyncio.Task`, which propagates into the HTTP stream), and
  approval gate (a plain `if tool_name == "shell": await ui_confirm(...)`
  check between "model requested tool" and "execute tool") are 100% yours to
  build.

## C. Pydantic AI

- **Multi-provider, confirmed broad**: native model classes for OpenAI,
  Anthropic, Gemini, xAI, Bedrock, Cerebras, Cohere, Groq, Mistral,
  OpenRouter, Hugging Face, and others, plus first-class "OpenAI-compatible"
  support — `OpenAIChatModel` with a custom `base_url`/`Provider` covers
  DeepSeek, Fireworks, Ollama, vLLM, Together, Azure AI Foundry, or a LiteLLM
  proxy backend — without a custom model class.
  (<https://pydantic.dev/docs/ai/models/overview/>)
- **Deferred tools / approval gate, confirmed and well-specified**: a tool
  decorated with `requires_approval=True` doesn't execute; the run ends early
  with `result.output` as a `DeferredToolRequests` (pending calls). The caller
  builds `DeferredToolResults` (approve / deny / override-args, keyed by
  tool-call id) and resumes via a follow-up run with `deferred_tool_results=`.
  An inline `HandleDeferredToolCalls` handler can also resolve calls without
  pausing the run entirely.
  (<https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/>) This maps
  directly onto requirement 5, including the "edit the command before
  approving" case (override args).
- **Streaming + approval interaction: confirmed still evolving.**
  `run_stream()` supports inline approvals and emits
  `DeferredToolRequestsEvent` / `DeferredToolResultsEvent`, but the docs
  describe the current pattern as working "well for batch/review workflows"
  (collect → review externally → resume with a new `run()`) — a pause/resume/
  restart cycle, not a live duplex channel. Corroborated by an open, recent
  GitHub issue, **pydantic/pydantic-ai#7301**, "Interactive human-in-the-loop
  tool approval in realtime sessions" (Aug 2026), which names exactly this
  gap. (<https://github.com/pydantic/pydantic-ai/issues/7301>) The mechanism
  is usable for mindstew's case (pause, prompt the human, resume) but is not
  yet a seamless "approve without breaking the stream" experience.
- **Cancellation**: no bespoke protocol beyond asyncio — `agent.run()` /
  `iter()` honor external `asyncio.Task.cancel()` (surfaces as
  `CancelledError`, wrapped into a catchable `RunCancelled` with partial-run
  state), plus first-party `AgentRun.cancel()` / `RunContext.cancel()` for
  self-initiated cancellation. In-flight tool tasks are cancelled and drained.
  An open issue, pydantic/pydantic-ai#6460 ("Cancellation semantics: a
  level-triggered contract for agent runs, streams, tools, and durable
  execution"), shows edge cases in this contract are still being hardened —
  similar caveat to the streaming/approval gap above.

## Sanity check: LangGraph / CrewAI / smolagents

- **LangGraph** — graph/state-machine orchestration for branching,
  multi-node workflows; a single ReAct-style agent runs noticeably more
  boilerplate than the equivalent in a lighter framework. Justified for
  complex control flow, not for one chat agent with a handful of tools.
  Confirmed heavier than needed.
- **CrewAI** — role-based multi-agent crews; no advantage for a single agent,
  and no built-in shell-approval-gate primitive comparable to B/C. Confirmed
  overkill.
- **smolagents** — genuinely lightweight and provider-agnostic (LiteLLM/
  transformers/local models under the hood). But its default action format is
  code-writing-and-executing (the model emits Python the framework runs), not
  discrete JSON-schema tool calls with a natural per-call approval hook —
  retrofitting a shell-approval gate onto "the agent writes arbitrary code" is
  a worse fit for requirement 5 than B or C's discrete tool-call boundaries.
  Confirmed unsuitable, for a different reason than "heavyweight."

## Recommendation: Option C — Pydantic AI

Pydantic AI is the only option that satisfies all five requirements natively
in a single library: broad, confirmed multi-provider support including
generic OpenAI-compatible endpoints (no provider lock-in, no proxy
indirection); ordinary Python function tools for wiki search / file read /
graph traversal / file generation; `run_stream()` for UI streaming;
asyncio-native cancellation with a documented `RunCancelled` contract; and —
the deciding factor over hand-rolling (Option B) — a built-in, typed
`requires_approval` / `DeferredToolRequests` / `DeferredToolResults`
mechanism that maps directly onto the shell-approval-with-edit requirement,
instead of requiring mindstew to build that gate and its state machine
(pending-call bookkeeping, resume-with-edited-args, deny messaging) from
scratch as Option B would. The one real cost is that streaming and approval
don't yet compose as smoothly as a fully custom loop would allow (per
pydantic-ai#7301) — mindstew's UI will need to model tool-approval as a
"stream pauses, prompt user, resume" cycle rather than a live in-stream
interrupt — but that's a UX accommodation, not a blocker, and a smaller gap to
close than building the entire approval/deferred-tool machinery from scratch
in Option B. Option A is disqualified outright by requirement 1 (confirmed
via claude-agent-sdk-python#410, closed not-planned).

## Sources

- <https://code.claude.com/docs/en/agent-sdk/python>
- <https://github.com/anthropics/claude-agent-sdk-python/issues/410>
- <https://docs.litellm.ai/docs/completion/function_call>
- <https://docs.litellm.ai/docs/completion/stream>
- <https://docs.litellm.ai/stream>
- <https://pydantic.dev/docs/ai/models/overview/>
- <https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/>
- <https://github.com/pydantic/pydantic-ai/issues/7301>
- <https://github.com/pydantic/pydantic-ai/issues/6460>
