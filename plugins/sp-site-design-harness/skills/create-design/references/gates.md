# Quality Gates

Do not advance until the current gate passes. State which gate you are at when
reporting progress.

**When a run builds several options, Gates 2-5 apply to each one separately.**
They are alternatives the user will choose between, so a weak one is not a
lesser option — it is a wasted slot, and it makes the set look worse than the
work behind it. Gate 1 runs once, over the selected set: the test there is that
the directions are distinct from each other, not just individually sound.

## Gate 1 — Direction (before detailed implementation)

- A clear visual thesis exists, written down.
- The concept fits the product's purpose, audience, and emotional goal.
- The concept is meaningfully differentiated from generic defaults — not a
  recolor of a conventional layout.

Fail → return to DISCOVER and generate new directions.

## Gate 2 — Composition (before polishing anything)

- Primary hierarchy works: the first, second, and third things seen are the
  intended ones.
- The interface has a recognizable visual identity at a glance.
- No major section has regressed into a generic pattern (run the DEFINE
  pattern-regression check).

Fail → fix structure. Do not proceed to polish or effects.

## Gate 3 — Critique (before final refinement)

- Independent visual critique has run where tooling allows.
- The highest-impact issues it named have been addressed, not deferred.
- The critic's pass weighed the accumulated principles in
  `references/craft-corrections.md` where relevant (see `critique.md`).
- A post-revision re-validation screenshot pass has run (SKILL.md DELIVER 3).

Fail → run or re-run the critic per `critique.md`.

## Gate 4 — Reduction (before declaring completion)

- A deliberate deletion pass has happened and removed something.
- Every remaining decorative element has a stated purpose.
- Nothing deleted was replaced with different decoration.
- A post-deletion re-validation screenshot pass has run (SKILL.md DELIVER 5).

Fail → run the deletion pass again.

## Gate 5 — Production polish

Verified, not assumed:

- Responsive behavior at wide desktop, laptop, tablet, small mobile
- Accessibility checklist
- Interaction and component states
- Browser rendering (actually screenshotted)
- Typography, spacing, image quality, motion
- Edge cases: empty, loading, error, long content, missing image
- Final screenshots checked against `references/craft-corrections.md` — does
  anything here risk reading as an accident rather than an intentional choice?
- `directions/NN-<slug>.tokens.md` exists alongside every shipped
  `NN-<slug>.html`, and its contents match what the HTML actually renders
  (type scale, palette with roles, spacing, radius, border/shadow strategy)
- `directions/index.html` exists and links every built direction

Fail → return to the relevant polish pass in `polish.md`, or (for the last two
items) write the missing file before declaring the run complete.
