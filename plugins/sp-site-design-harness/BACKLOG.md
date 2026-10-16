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
  WP-build system's expected input format. The consumer is now known
  (html-to-block-theme); this is milestone M2 of the integration plan
  (DECISIONS 2026-10-08), so it's planned work rather than backlog.
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
- Motion tiers in the handoff contract (T0 transitions, T1 keyframes and
  scroll-driven CSS, T2 script module / Interactivity API, T3 libraries via a
  monorepo block). Deferred until the concept-driven-motion experiment merges;
  trunk has no motion tooling to hand off yet.
- A handoff package validator (tokens match `:root`, files exist, fonts have
  licenses). Deferred until a real handoff fails in a way it would catch.
- A separate h2bt build ledger. Deferred in favour of extending h2bt's
  existing report (drift, custom CSS, TODOs) with which handoff items were
  applied.
