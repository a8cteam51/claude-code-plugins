# STATUS

**Current version:** 0.2.0 (per `.claude-plugin/plugin.json`)

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

**Iteration — `iterate` skill** (added 2026-09-25): applies feedback at three
levels (L0 direct edit, L1 local revision, L2 routed to create-design). It
works on the HTML directions before handoff and on the built theme after, and
the HTML is frozen once handed off. create-design now writes two-layer role
tokens in `:root` so L0 swaps are one line. See DECISIONS.md 2026-09-25.

Supporting skills are in place: `/find-font`, `/scan-font-sources`,
`/publish-design-options` (the last depends on the separately-installed
`publish-to-spacefast` skill).

Documentation (`README.md`, `ARCHITECTURE.md`, `references/instruction-priority.md`)
describes the pipeline, the shared `projects/<slug>/` contract between phases, and
the instruction-priority order used when sources conflict.

## Testing so far

One full pipeline dry run completed (2026-09-17) in a throwaway test project
(`harness-test-1`, symlinked to this plugin's `skills/` rather
than a formal plugin install): research-intake → create-design → dev-handoff,
end to end, timed. Result: three complete, correctly risk-tiered homepage
directions, each functionally sound, each with its own subtle "reads as
unintentional" craft issue (not an a11y or responsive-rule violation) that
prompted the craft-corrections work above.

**Not yet done:** re-running that same test (or an equivalent one) to check
whether the craft-corrections log and the new re-validation steps actually
reduce this class of issue. This is the immediate next step.

## What's next

- **html-to-block-theme integration (started 2026-10-08)**, on branch
  `h2bt-integration` (worktree `../sp-site-design-harness-h2bt`). Plan and
  milestones live outside the repo in `../sp-site-design-harness-plans/`
  (`h2bt-integration.md`). **M0 baseline done** (`h2bt-m0-baseline.md` there): h2bt's mechanics are strong, but nothing in
  DESIGN.md/decisions.md reaches it, so a11y fixes, real IA and content status
  were all lost. Next: GitHub issues for h2bt's maintainer (TommusRhodus): a comment on
  claude-code-plugins#11 with standalone bugs, plus a new integration issue.
  Then M1 (standards).

- `/iterate` behavior tests passed 2026-09-25: L0 swap, mixed batch, frozen-HTML
  guard, theme-phase preset swap. They ran as isolated subagents following
  SKILL.md on scratch copies of `harness-test-1`, because the headless `claude`
  CLI login had expired. Their friction notes (contrast scope, screenshot
  setup, before-shots, color names, reporting heads-ups) are folded into the
  skill. **Still untested:** the trigger check, i.e. whether in a fresh
  session "change the hero border color in option 2" loads `iterate` rather
  than `create-design`. It needs a real session (re-login, then `claude -p` in
  a project with the skills symlinked).
- On the next full create-design run, also check that the output uses role
  aliases and has no hex outside `:root`.
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
- Done: `find-font`/`scan-font-sources`/`publish-design-options` migrated from
  the flat `commands/` layout into `skills/` (2026-09-17) — see BACKLOG.md.

## Known blockers

None.
