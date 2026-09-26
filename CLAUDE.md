## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (uses the `gh` CLI). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context — `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

## Use grill-with-ui

When you want to use the `grilling` skill, use the `grill-with-ui` skill instead. It provides a UI to the grilling skill. This includes wayfinder tickets labelled `wayfinder:grilling` (see `docs/agents/issue-tracker.md`) — open them with `grill-with-ui`, not the plain terminal `grilling` skill.
