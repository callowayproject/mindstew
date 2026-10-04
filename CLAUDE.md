## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (uses the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Implement each slice as a single PR

Each slice of the agent should be implemented as a single pull request.
This makes it easier to review and test the changes.

Implement tickets as a branch from the slice branch. PRs for each ticket should be merged into the slice branch.

## Use grill-with-ui

When you want to use the `grilling` skill, use the `grill-with-ui` skill instead. It provides a UI to the grilling skill. This includes wayfinder tickets labelled `wayfinder:grilling` (see `docs/agents/issue-tracker.md`) — open them with `grill-with-ui`, not the plain terminal `grilling` skill.
