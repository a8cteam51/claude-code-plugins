---
name: research-intake
description: Gather brand material, project goals, and context for a new site engagement, normalize it into a confidence-tagged brief, and hand off to the design phase — without blocking on sparse or empty input. Phase 1 (Research) of the sp-site-design-harness pipeline. Use when starting a new client/partner site engagement, or whenever raw brand material (PDFs, style guides, copy docs, existing assets, reference URLs) needs to be turned into a usable project brief before design work begins.
allowed-tools:
  - Read
  - Write
  - Bash
  - WebFetch
---

# Research Intake

Phase 1 of the sp-site-design-harness pipeline (**Research** → Design → Dev
Handoff). Its job: gather everything that could meaningfully inform the
build, and turn it into a brief specific enough that Phase 2 (`create-design`)
makes project-specific decisions instead of guessing — while still producing
*something usable* when the input is thin.

**This skill has no strict completion requirement.** More input produces
more specific decisions later, but sparse or empty input must not block the
pipeline. It proceeds with a fallback strategy and surfaces what it had to
guess at, rather than halting. The only hard stop in this entire phase is an
**unexamined file** — see Step 1. An *empty* `inputs/` folder is never a stop
condition.

See `../../references/instruction-priority.md` for the harness-wide priority
order. This skill applies it during Step 2 (Normalize), to resolve
conflicting inputs — e.g. a brand PDF says one thing and a live URL shows
another, or two supplied files disagree.

## Mechanism borrowed from `sp-design-system`, adapted for this brief

This skill's Input Ledger and Explicit/Inferred/Gap confidence-tagging are
based on `sp-design-system`'s Steps 1–4 (Intake/Normalize/Gap-Check/Gap-Fill)
and its `brand-extraction-schema.md` — but the target schema is different.
That skill normalizes into a WordPress-build-specific DESIGN.md; this skill
normalizes into `research/brief.md`, whose fields are brand guidance, website
goals, content/copy, existing assets, things to avoid, and
references/context — the shape Phase 2 (`create-design`) and Phase 3
(`dev-handoff`) both consume. See `references/brief-schema.md` for the exact
field list and `references/ledger-schema.md` for the disposition mechanics.

## Input

Whatever the user drops into `research/inputs/` — brand PDFs, style guides,
copy docs, existing graphics/photography/fonts, reference URLs, moodboards,
an existing `theme.json`, or nothing at all.

## Process

### Step 1 — Ledger (hard stop on unexamined files only)

Enumerate every file in `research/inputs/`:

```bash
find "research/inputs" -type f | sort
```

Record each item in `research/ledger.md`, one line per item, with exactly
one disposition: `Used`, `Dismissed`, `Deferred`, or `Unaccounted`. Read
`references/ledger-schema.md` for the full definitions, the bundle-collapsing
rule, and the standing auto-dismiss list before building this.

**`Unaccounted` is a hard stop, at this gate only.** Nothing proceeds to
Step 2 with an unexamined file. **An empty `inputs/` folder is not a stop
condition** — there is simply nothing to enumerate, and the ledger records
that plainly (e.g. "no input files supplied") and moves on.

### Step 2 — Normalize

Map whatever was found (files, prose the user typed directly in
conversation, or nothing) into `research/brief.md`, covering:

- Brand guidance
- Website goals
- Content/copy
- Existing assets (graphics, photography, fonts)
- Things to avoid
- References/project context

Every field is tagged `Explicit` / `Inferred` / `Gap` — see
`references/brief-schema.md` for the tagging rules and field-by-field
extraction targets, adapted from `sp-design-system`'s
`brand-extraction-schema.md` to this brief's shape.

**Resolve conflicts per the harness-wide instruction priority order**
(`../../references/instruction-priority.md`): an explicit brand rule beats an
inferred one from a screenshot; a brief goal stated directly by the user
beats an assumption drawn from a reference URL. Record which source won and
why when a real conflict existed — don't silently pick one.

### Step 3 — Gap-check → questionnaire fallback

If material gaps remain after normalizing, ask **one batched set of
questions** — capped, never trickled one at a time — grouped by brief
section (mirroring `sp-design-system`'s Step 3 batching, grouped by
DESIGN.md section there; grouped by brief section here).

**Proceed regardless of how much gets answered.** If the user answers little,
some, or none of it, move on. For every `Gap` field still unresolved after
this round:

- If a team design-standards default exists (see
  `../dev-handoff/references/design-standards.md`), name it explicitly as
  the fallback in `brief.md`.
- Otherwise, flag it plainly in `brief.md`: *"no input — Phase 2 will use
  creative judgment here."* This is not a failure state — it is explicit
  license for Phase 2 to make a real creative call, not a silent guess.

Never leave a `Gap` field unresolved in `brief.md` without one of these two
outcomes attached.

## Output (`research/`)

- `inputs/` — the raw dropped-in files, untouched
- `ledger.md` — one line per input file, disposition + reason (see
  `references/ledger-schema.md`)
- `brief.md` — normalized brief: goals / audience / content / brand guidance
  / assets available / things to avoid / references, each field
  confidence-tagged (see `references/brief-schema.md`)

## Exit condition

`brief.md` exists, and every input file has a disposition other than
`Unaccounted`. Sparse content is allowed through; unexamined files are not.

## Handoff

Phase 2 (`create-design`) checks for `research/brief.md` at the start of its
own intake (see that skill's `references/intake.md`, Step 0) and consumes it
directly when present, only asking about fields this skill flagged as an
unresolved `Gap`.
