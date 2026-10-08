# BACKLOG

Deferred ideas and future-phase features deliberately not built yet.

- WordPress theme-build phase (theme.json, style.css, block templates/patterns)
  is explicitly out of scope for this plugin by design — not deferred, not
  planned here. See README "Out of scope, by design." Listed here only so it
  isn't mistaken for an oversight. (Applying feedback to an already-built theme via
  `/iterate` is the one exception; see DECISIONS 2026-09-25.)
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
- `/iterate` could use the WordPress Studio annotation tools
  (`open_annotation_browser` / `wait_for_annotations`) so a designer or
  partner clicks an element and leaves a note that becomes a targeted edit.
  Not yet evaluated.
- Consider a `model:` override in `iterate`'s frontmatter (a smaller, faster
  model for L0-heavy sessions) once it's confirmed skills support it and
  it's clear L1 quality holds up.
