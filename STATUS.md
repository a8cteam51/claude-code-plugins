# STATUS

**Current version:** 0.1.0 (per `.claude-plugin/plugin.json`)

## Where things are

The plugin's three-phase pipeline is built out:

- **Phase 1 — `research-intake` skill**: brand-material intake → confidence-tagged
  `research/ledger.md` + `research/brief.md`.
- **Phase 2 — `create-design` skill**: DISCOVER → DEFINE → DELIVER design engine →
  N distinct HTML homepage directions + tokens + index.
- **Phase 3 — `dev-handoff` skill**: chosen direction → `handoff/DESIGN.md` +
  `handoff/decisions.md`, gated on `[Development]`-tagged accessibility criteria.

Supporting commands are in place: `/find-font`, `/scan-font-sources`,
`/publish-design-options` (the last depends on the separately-installed
`publish-to-spacefast` skill).

Documentation (`README.md`, `ARCHITECTURE.md`, `references/instruction-priority.md`)
describes the pipeline, the shared `projects/<slug>/` contract between phases, and
the instruction-priority order used when sources conflict.

## What's next

- Git repo just initialized (2026-09-17) — no commits yet as of this writing.
- No theme-build phase exists or is planned in this plugin by design (see
  README "Out of scope, by design") — that's a separate, external system.

## Known blockers

None.
