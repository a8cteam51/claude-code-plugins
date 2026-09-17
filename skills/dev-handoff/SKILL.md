---
name: dev-handoff
description: Distill a chosen design direction plus research context into structured design decisions — a DESIGN.md token/prose spec and a decisions.md notes file — ready for a separate WordPress block-theme build agent to consume. Phase 3 (Dev Handoff) of the sp-site-design-harness pipeline. Use once a direction from create-design (Phase 2) has been chosen and needs to be turned into a developer-ready handoff. Does not build the theme itself.
allowed-tools:
  - Read
  - Write
  - Bash
---

# Dev Handoff

Phase 3 of the sp-site-design-harness pipeline (Research → Design → **Dev
Handoff**). Distills the *chosen* direction plus the full research context
into structured design decisions an AI agent can use to build a matching
WordPress block theme — including pages/interactions beyond the homepage
mock. **This phase produces documents, not code.**

**Explicitly out of scope — do not do these here:** authoring `theme.json`,
`style.css`, block templates or patterns, or handing off directly to any
WordPress build tool (`claude-code-wordpress.com`, `wp-site-creator`, or any
other). Output stops at `DESIGN.md` + `decisions.md`. Those documents are
what a separate, external build system consumes — this skill does not invoke
that system, does not know its interface, and is not responsible for it.

See `../../references/instruction-priority.md` for the harness-wide priority
order. This phase uses it when gap-filling `DESIGN.md`: anything neither the
chosen direction nor the brief specifies falls back to this plugin's forked
`references/design-standards.md` — never an untethered aesthetic call at
this stage. The `[Development]`-tagged accessibility gate (Step 3 below) is
the highest-priority item in that order and is a hard stop regardless of
what any lower-priority source prefers.

## Input

- The chosen `directions/NN-<slug>.html` + its `directions/NN-<slug>.tokens.md`
  (both produced by Phase 2's `create-design` skill)
- `research/brief.md` (produced by Phase 1's `research-intake` skill, if it
  ran)

## Forked references — read, don't fetch live

This skill's `design-standards.md` and `accessibility-standards.md` are
**forked copies**, not live references into `sp-design-system`. They were
copied deliberately (see `../../ARCHITECTURE.md` §1) rather than pointed at
that skill's originals, trading a manual re-sync burden for not repeating a
"one skill living in two places" bug that has already caused real problems.
Treat them as this plugin's own team standards going forward.

## Process

### Step 1 — Draft `handoff/DESIGN.md`

Draft `handoff/DESIGN.md` from the chosen direction's `.tokens.md` file, in
the schema documented in `references/design-md-schema.md`: YAML frontmatter
tokens, then the markdown body in this fixed section order — Overview,
Colors, Typography, Layout, Elevation & Depth, Shapes, Components, Do's and
Don'ts.

Sections with nothing to say get an explicit `omitted` key in the
frontmatter rather than being silently dropped. Prose must explain the *why*
behind each token, not just restate the value.

### Step 2 — Gap-fill against team standards

Anything `DESIGN.md` needs that neither the chosen direction's tokens nor
`research/brief.md` specifies falls back to this plugin's forked
`references/design-standards.md` — its Typography, Color Palette, Status &
Semantic Colors, Type-Rendering Baseline, Layout, and Components sections in
particular. Name the fallback explicitly in the relevant section's prose
(e.g. "no brand spacing scale specified; using the team default 4px-based
scale from design-standards.md") so a reader can tell a real design decision
from a team-default fill-in.

Never apply untethered aesthetic judgment at this stage — every remaining
gap resolves to either the chosen direction's tokens, the brief, or a named
team default.

### Step 3 — Accessibility gate (`[Development]`-tagged criteria only) — hard stop

Read `references/accessibility-standards.md`. Run **only** the criteria
tagged `[Development]` against the drafted `DESIGN.md` and the described
interactions/pages: ARIA/alt-text expectations, motion/reduced-motion
behavior, heading order, focus order across pages, link-text specificity,
navigation/search findability, and the rest of that file's
`[Development]`-tagged list.

**Do not re-run the `[Design]`-tagged criteria.** Those — contrast, sizing,
rendered interactive states, touch target size — were already effectively
checked during Phase 2's polish and accessibility passes
(`create-design/references/polish.md`). Re-litigating them here duplicates
work Phase 2 already did and isn't this phase's job; this gate exists
specifically to cover what only shows up once real markup/interaction is
*described*, which a static HTML mock and its token file cannot fully show.

This is a **hard stop**. `DESIGN.md` does not proceed to Step 4 until every
applicable `[Development]`-tagged criterion passes or is logged as a
deliberate, explained exception.

### Step 4 — Write `handoff/decisions.md`

Write the structured, agent-readable notes the separate downstream build
system will consume:

- **Implied pages/templates/patterns beyond the homepage** — anything the
  brief or the chosen direction implies but the static mock couldn't show
  (blog index, single post, archive/taxonomy, search results, 404, etc. —
  see `design-standards.md`'s Process Rules for the standard WordPress view
  set as a checklist of what to consider, not a mandate to design them here).
- **Interactions described in the brief that the static mock couldn't
  show** — anything from `research/brief.md` or conversation about behavior
  (menus, form flows, animation, state changes) that a single static HTML
  file cannot demonstrate.
- **Explicit deferrals** — anything intentionally left for the build phase
  to decide, named plainly rather than left implicit.

## Output (`handoff/`)

- `DESIGN.md` — token + prose spec, ready to feed a theme-build agent
- `decisions.md` — structured notes: implied pages, interactions, deferrals

**Explicitly not produced here:** `theme.json`, `style.css`, block
templates/patterns, or anything else the separate WP-build system is
responsible for.

## Exit condition

`DESIGN.md` passes the Development-phase accessibility gate (Step 3) and
`decisions.md` is complete enough for a build agent to start from it without
re-deriving decisions already made.
