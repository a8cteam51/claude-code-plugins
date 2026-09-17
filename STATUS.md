# STATUS

**Current version:** 0.1.0 (per `.claude-plugin/plugin.json`)

## Where things are

The plugin's three-phase pipeline is built out:

- **Phase 1 — `research-intake` skill**: brand-material intake → confidence-tagged
  `research/ledger.md` + `research/brief.md`.
- **Phase 2 — `create-design` skill**: DISCOVER → DEFINE → DELIVER design engine →
  N distinct HTML homepage directions + tokens + index. Just extended with a
  craft-corrections log (`references/craft-corrections.md`) and two mandatory
  re-validation steps (post-critique, post-deletion) — see DECISIONS.md
  2026-09-17 entries for why.
- **Phase 3 — `dev-handoff` skill**: chosen direction → `handoff/DESIGN.md` +
  `handoff/decisions.md`, gated on `[Development]`-tagged accessibility criteria.

Supporting commands are in place: `/find-font`, `/scan-font-sources`,
`/publish-design-options` (the last depends on the separately-installed
`publish-to-spacefast` skill).

Documentation (`README.md`, `ARCHITECTURE.md`, `references/instruction-priority.md`)
describes the pipeline, the shared `projects/<slug>/` contract between phases, and
the instruction-priority order used when sources conflict.

## Testing so far

One full pipeline dry run completed (2026-09-17) in a throwaway test project
(`harness-test-1`, symlinked to this plugin's `skills/`/`commands/` rather
than a formal plugin install): research-intake → create-design → dev-handoff,
end to end, timed. Result: three complete, correctly risk-tiered homepage
directions, each functionally sound, each with its own subtle "reads as
unintentional" craft issue (not an a11y or responsive-rule violation) that
prompted the craft-corrections work above.

**Not yet done:** re-running that same test (or an equivalent one) to check
whether the craft-corrections log and the new re-validation steps actually
reduce this class of issue. This is the immediate next step.

## What's next

- Re-run a fresh end-to-end test and specifically check: does
  `craft-corrections.md` get consulted during the critic/craft passes
  (visible in the model's own narration)? Do the two new re-validation steps
  actually produce new screenshots at the right point, not just a mention of
  intent? Does a sticky-header-with-border case, if one comes up, get caught
  this time?
- Open items noted in `ARCHITECTURE.md` §7, not yet triaged into work:
  formalizing `directions/index.html`'s risk-badge/nav format (produced
  inconsistently in past non-harness runs); finalizing `decisions.md`'s
  structure once the downstream WP-build system's expected input format is
  known; whether font-licensing checks belong as a standing Phase 1 ledger
  check.
- `commands/` uses the older flat-file plugin layout; current Claude Code
  plugin docs recommend `skills/` for everything going forward. Not urgent,
  but worth migrating `find-font`/`scan-font-sources`/`publish-design-options`
  into `skills/` at some point.

## Known blockers

None.
