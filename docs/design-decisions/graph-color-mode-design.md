# Knowledge-graph color-mode toggle (type vs. community)

Wayfinder ticket #23 (map #1). The graph view (#9) gains a **color mode** toggle between **Community** (default, as #9 shipped) and **Type** (the page's frontmatter `type`). The control is a segmented control in the graph view's toolbar overlay; the choice is a machine-global UI preference (QSettings). Type mode shows a fixed 6-entry legend; Community mode shows no legend list, only an "N communities" count. No visual was drawn for this grill.

## Terms

- **color mode** — which node attribute (page type or Louvain community) drives node fill color in the graph view. Avoid: theme, palette.
- **community** — a Louvain cluster of pages, recomputed globally each pass (#9). Avoid: group, cluster (as a noun for the data).

## Why

#9 deferred this: "Should the graph view offer a toggle between coloring nodes by page type and by Louvain community, or stay community-only? Covers the control's placement/persistence and legend behavior." Community-only was the v1 default.

## Locked decisions

None met the durable bar (all are cheap to reverse); see routine choices.

## Routine choices

- **Toggle exists (q1: A).** Type answers "what kind of knowledge is where"; community answers "what clusters together". Type data is already in frontmatter (#3) and feeds typeAffinity. Rejected: community-only (forfeits the only at-a-glance type distribution).
- **Placement and default (q2: A).** Segmented control in the graph view's toolbar overlay; default Community. Rejected: View-menu-only (less discoverable; may be added later as a mirror), Settings-only (too far for a frequently flipped, view-local choice).
- **Persistence (q3: B).** Machine-global UI preference via QSettings, applies to all vaults. Rejected: per-vault `.mindstew/config.yaml` (a viewing preference shouldn't ride in a vault config that may be synced or shared), not persisted (annoying for Type users).
- **Legend (q4: A).** Type mode: 6 swatch+label entries. Community mode: no legend list, only an "N communities" count; hovering highlights the cluster (per #9). Rationale: community colors carry no meaning beyond "belongs together" and ids shift between global recomputes, so a labelled legend would mislead or churn. Rejected: top-8 labelled communities + "Other"; clickable legend filtering (a new graph feature, not part of this toggle).
- **Type colors (q5: A).** Fixed hand-picked 6-color palette keyed by type, with light and dark variants. Missing, malformed, or unknown `type` renders neutral gray, listed as "Other" in the Type legend only when such pages exist (honors #3's tolerate-malformed rule). Rejected: hashing the type string to a color (can clash or fail contrast).

## Verified facts

- `CONTEXT.md` has no existing entries for color mode/community; terms above are new.
- #9's decision is community-colored nodes, with hover highlighting neighbors and dimming the rest.

## Risks

- The 6-color palette must stay distinguishable from community colors in both appearances so users can tell which mode is active; the segmented control state is the primary cue.

## Deferred

- Clickable legend entries that filter/dim by type or community. Reopen if graph filtering becomes a requested feature.
- View-menu mirror of the toggle. Reopen if keyboard access is wanted.

## Open threads

None.
