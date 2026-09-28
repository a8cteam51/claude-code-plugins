# DESIGN.md Schema (google-labs-code/design.md spec)

Documents the YAML-frontmatter-plus-prose-sections schema used to draft
`handoff/DESIGN.md`, as used in `sp-design-system`'s Step 7. This file
describes the *shape*; `SKILL.md` describes the *process* that fills it.

## Structure

A `design.md`-spec file is:

1. YAML frontmatter — the design tokens, machine-readable
2. Markdown body — prose sections, in a fixed order, explaining the *why*
   behind each token, not just restating the value

## Section order (fixed)

1. **Overview** — aka Brand & Style. Project/brand name, personality/voice,
   industry/audience context.
2. **Colors** — palette with roles (not just hex values — which token plays
   which role), status/semantic colors, dark-mode variants if applicable.
3. **Typography** — font family per role (heading, body, label/caption,
   display), size per role, weight and letter-spacing intent.
4. **Layout** — aka Layout & Spacing. Spacing scale, grid/column system,
   content width/max-width.
5. **Elevation & Depth** — aka Elevation. Shadow style, or the border-based
   alternative if that's the convention instead.
6. **Shapes** — border-radius convention, signature shape motifs.
7. **Components** — button variants and states, card/container conventions,
   input/form field conventions, navigation conventions.
8. **Do's and Don'ts** — explicit negative constraints, explicit positive
   non-negotiables.

Sections may be omitted only when genuinely not applicable — and any
omission must be listed explicitly via the frontmatter `omitted` key rather
than silently dropped. Never omit a section just because a token was hard to
derive; that's a gap-fill problem (see `SKILL.md`), not an omission.

## Prose requirement

Each section's prose must explain the *why* behind each token, not just
restate the value — e.g. "the sole interaction driver, used at full
saturation only on primary CTAs" rather than a hex code with no context.
This is what makes DESIGN.md usable by a build agent that wasn't present for
the design decisions: the reasoning has to travel with the token.

## Confidence carries forward

Tokens drafted from the chosen direction's `.tokens.md` file are effectively
`Explicit` (they were rendered and validated in Phase 2). Tokens gap-filled
from `design-standards.md` should say so in the prose (e.g. "no brand
spacing scale was specified; using the team default 4px-based scale"), the
same way `research/brief.md` tags fields — so a reader of DESIGN.md can tell
a real design decision from a team-default fallback.

## What this schema is not

This is the schema for the *document*, not a build tool. Nothing here
implies running `npx @google/design.md lint` or `export` — those are
`sp-design-system`'s Development-phase tooling, tied to a WordPress
block-theme build this harness does not perform. `dev-handoff`'s own
accessibility gate (see `SKILL.md`) is a manual review against the forked
`accessibility-standards.md`'s `[Development]`-tagged criteria, not an
automated lint run.
