# BACKLOG

Deferred ideas and future-phase features deliberately not built yet.

- WordPress theme-build phase (theme.json, style.css, block templates/patterns)
  is explicitly out of scope for this plugin by design — not deferred, not
  planned here. See README "Out of scope, by design." Listed here only so it
  isn't mistaken for an oversight.
- Formalize `directions/index.html`'s risk-badge/nav format as part of
  Phase 2's output contract — it's been produced inconsistently across past
  (pre-harness) runs of the underlying design skill.
- Finalize `handoff/decisions.md`'s structure against the actual downstream
  WP-build system's expected input format, once that system's interface is
  known. Current structure is a reasonable best guess, not confirmed against
  a real consumer.
- Consider a standing font-licensing check in Phase 1's Input Ledger (e.g.
  EULA restrictions that block adding a public git remote) — a recurring
  hazard in past engagements, currently handled ad hoc rather than
  systematically.
- Migrate `commands/find-font.md`, `commands/scan-font-sources.md`,
  `commands/publish-design-options.md` from the flat `commands/` layout into
  `skills/` — current Claude Code plugin conventions favor `skills/` for
  everything; `commands/` still works but is the older pattern.
