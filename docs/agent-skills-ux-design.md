# Agent Skills (SKILL.md) scanning & /skill selection UX

Skills are folders with a `SKILL.md`, scanned from two sources (global and vault-local, vault shadowing global), parsed per the Agent Skills convention, and reachable by the chat agent through one read-only `load_skill` tool. The user triggers a skill with `/` (the app pre-fills the same tool call); the model can also discover skills from a name+description list in the system prompt. Skills are chat-agent-only and do not cross to the MCP surface. Wayfinder ticket #22, map #1.

## Terms

- **Skill** — a folder containing a `SKILL.md` (YAML frontmatter with `name` and `description`, plus Markdown instructions) that the chat agent can be told to follow. _Avoid_: plugin, command, prompt template.
- **Skill source** — a directory root scanned for Skills: the global one in Application Support, or the vault-local one under `.mindstew/skills/`. A vault-local Skill shadows a global Skill of the same name. _Avoid_: skill library, skill repo.

## Why

The map lists "agent skills (SKILL.md)" and a `/skill` selection UX as in-scope but unspecified. Needed: where skills live, what format is accepted, how they are invoked and delivered to the agent (#4, #11), and whether they touch the MCP surface (#18).

## Locked decisions

- **Sources (q1):** two sources: global `~/Library/Application Support/mindstew/skills/` and vault-local `<vault>/.mindstew/skills/`; vault shadows global on name collision. Rejected: bundled app skills as a third source (nothing to ship yet; add later as lowest precedence); scanning `~/.claude/skills` (couples to another tool, and those skills assume Claude Code's tools).
- **Format (q2):** follow the Agent Skills convention: `name` and `description` required, other frontmatter keys ignored. Scripts are never auto-run; a skill body may instruct the agent to run one via `shell_exec`, which keeps #11's approval gate and #16's sandbox. Rejected: ignoring everything but `SKILL.md` (loses skills with helper files); a mindstew-specific format (nobody else produces it).
- **Delivery (q4):** one path for both triggers. Names+descriptions of valid skills are listed in the system prompt; a new read-only `load_skill(name, file=None)` tool returns the `SKILL.md` body or a file inside that skill's folder (this is how reference files outside the vault are read, since `vault_read` is vault-scoped). A `/skill` selection makes the app execute that same tool call and pre-fill the result before the turn starts, shown as a normal tool-call card. Rejected: pasting the body into the user message (second injection mechanism, possible duplicates); appending to the system prompt for the turn (same).
- **MCP (q5):** `load_skill` is chat-agent-only; the MCP surface stays at #18's four tools. Rejected: exposing `load_skill`/`list_skills` over MCP (skills assume mindstew's own tool names; no known consumer). Revisit if an external client wants it.

## Routine choices

- **Triggering (q3):** hybrid. `/` in the chat input opens an autocomplete of skills and forces one explicitly; the model may also discover and load skills itself.
- **Scanning (q6):** scan lazily each time the `/` popup opens or a turn starts; no file-system watcher. Invalid skills (missing/malformed frontmatter, missing name or description) are skipped, with a lightweight "N skills skipped" footer row in the popup that opens the error details.

## Verified facts

- `CONTEXT.md` did not exist; created with the two terms above.
- #11's shared tool set has five tools and #18 exposes four; `load_skill` is a sixth chat-only tool, so #11's tool inventory is extended by this decision.
- #3's rule applies: frontmatter parsing must tolerate absent/null/scalar/non-mapping values.

## Risks

- System-prompt listing grows with skill count; no cap or truncation rule was decided.
- `load_skill`'s `file` argument must be confined to the skill's own folder (no `..`, no symlink escape); this is an implementation requirement, not yet specified further.
- Pre-filled tool results rely on Pydantic AI message-history behavior; verify at implementation.
- Silent skip of invalid skills makes mistakes easy to miss; the footer row is the only signal.

## Deferred

- Bundled skills shipped inside the app — reopen when there is a skill worth shipping.
- MCP exposure of skills — reopen if an external client has a use for it.
- Description-list cap/truncation for large skill counts.

## Open threads

- None.
