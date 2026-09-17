# sp-site-design-harness — Architecture

A three-phase pipeline that takes a client engagement from raw brand material to a
developer-ready design system for a WordPress block theme. Each phase is an
independently usable skill; together they're packaged as one Claude Code plugin.

**Phases:** Research → Design → Dev Handoff
**Out of scope:** actually building the WordPress block theme. That happens in a
separate, TBD system this harness hands off to. This harness produces design
decisions, not code.

---

## 1. Guiding decisions (from prior discussion)

- **Packaging:** a Claude Code plugin, not a single monolith skill and not loose
  unpackaged commands. Each phase stays its own skill (matches how the working
  pieces already function, avoids the monolith failure mode seen in
  `quick-site-poc`), but they ship together, versioned, with one shared project
  folder as the contract between them.
- **`consistent-high-quality-design` is Phase 2, kept close to as-is, renamed
  `create-design` in this plugin for simplicity.** Its
  DISCOVER→DEFINE→DELIVER engine, seed/risk-ladder variety mechanism, critique
  pass, and anti-slop audit are the actual "quality" differentiator in this whole
  system and nothing else reproduces them. It gets one addition: persisting its
  token output to disk (see §4).
- **`sp-design-system` and `quick-site-poc` are *not* adopted wholesale.** Both
  are earlier, single-direction pipelines whose own internal phase names
  (Research/Design/Development) collide with this harness's phases but mean
  something narrower. They're mined for mechanisms, not reused as pipelines:
  - Input Ledger (Used/Dismissed/Deferred/Unaccounted per input file)
  - Explicit/Inferred/Gap confidence tagging
  - `[Design]`/`[Development]`-tagged accessibility split
  - DESIGN.md schema (google-labs-code/design.md spec)
  - The hard-won lesson: author tokens straight into their destination file,
    never a `build/`/`handoff/` intermediate (caused divergence on a real
    engagement).
  - Their actual theme-building steps (authoring `theme.json`, block templates,
    WP handoff) are **not** carried into this harness — out of scope per above.
- **Standards docs are forked, not referenced live.** `design-standards.md` and
  `accessibility-standards.md` get copied into this plugin rather than pointed
  at `sp-design-system`'s copies. Accepted tradeoff: the two can drift over time
  and need manual re-sync, in exchange for not repeating the exact "one skill
  living in two places" bug that already bit a real engagement in
  `special-projects-quick-site-build-tool`.
- **Instruction Priority Order applies harness-wide**, not just at Dev Handoff:

  ```
  Accessibility standards > Explicit brand rules > Project brief
  > team design-standards defaults > Claude's own generalist judgment
  ```

  Phase 1 uses it to resolve conflicting inputs during normalization. Phase 2
  uses it when reconciling brief constraints against its own creative
  judgment. Phase 3 uses it (as it already did) for gap-filling DESIGN.md.
- **Phase 1 has no strict completion requirement.** More input produces more
  specific decisions later, but sparse or empty input must not block the
  pipeline — it proceeds with a fallback strategy (see §2) and surfaces what it
  had to guess at, rather than halting.

---

## 2. Phase 1 — Research (new skill)

**Goal:** gather everything that could meaningfully inform the build, and turn
it into a brief specific enough that Phase 2 makes project-specific decisions
instead of guessing — while still producing *something usable* when the input
is thin.

**Input:** whatever the user drops into `research/inputs/` — brand PDFs, style
guides, copy docs, existing graphics/photography/fonts, reference URLs,
moodboards, an existing `theme.json`, or nothing at all.

**Process:**
1. **Ledger.** Enumerate every file in `research/inputs/`. Each gets exactly one
   disposition: `Used` (names where it fed the brief), `Dismissed` (reason),
   `Deferred` (must point to a `BACKLOG.md` line), or `Unaccounted` (default
   state — a file the pipeline hasn't looked at yet). `Unaccounted` items are a
   hard stop **at this gate only** — nothing proceeds to normalization with an
   unexamined file — but an *empty* `inputs/` folder is not a stop condition.
2. **Normalize.** Map whatever was found into `research/brief.md`, covering:
   brand guidance, website goals, content/copy, existing assets (graphics,
   photography, fonts), things to avoid, references/project context. Every
   field is tagged `Explicit` / `Inferred` / `Gap`, same confidence system as
   the mined schema.
3. **Gap-check → questionnaire fallback.** If material gaps remain, ask **one
   batched set of questions** (capped — never trickled one at a time),
   grouped by brief section. If the user answers little, some, or none of it:
   proceed anyway. Unresolved `Gap` fields get an explicit fallback: a team
   design-standards default where one exists, otherwise flagged clearly in
   `brief.md` as "no input — Phase 2 will use creative judgment here," so
   Phase 2 knows it has license to make a real creative call rather than
   silently guessing.

**Output (`projects/<slug>/research/`):**
- `inputs/` — the raw dropped-in files, untouched
- `ledger.md` — one line per input file, disposition + reason
- `brief.md` — normalized brief: goals / audience / content / brand guidance /
  assets available / things to avoid / references, each field confidence-tagged

**Exit condition:** `brief.md` exists and every input file has a disposition
other than `Unaccounted`. Sparse content is allowed through; unexamined files
are not.

---

## 3. Phase 2 — Design (existing skill, light modification)

**Goal:** unchanged — turn the brief into N responsive, HTML-only homepage
concepts with real creative variety, strictly avoiding generic defaults.

**Modification to `consistent-high-quality-design`** (ported into this plugin
as `create-design`)**:**
- Before running its own ~4-question conversational intake, check for
  `research/brief.md`. If present, consume it directly as the brief and only
  ask clarifying questions for gaps `brief.md` itself flagged as unresolved —
  don't re-ask what Phase 1 already answered.
- If no `research/brief.md` exists (harness invoked standalone, or Phase 1
  skipped), fall back to its current ad-hoc intake unchanged.
- **New output requirement:** alongside each `directions/NN-<slug>.html`, also
  write `directions/NN-<slug>.tokens.md` — the same token list (type scale,
  palette with roles, spacing, radius, border/shadow strategy) it already
  produces in its chat response today, just persisted to disk. This is the one
  concrete gap the audit surfaced: today the design language exists only in
  conversation, and Phase 3 has nothing machine-readable to read.

**Everything else — the seed/risk-ladder variety mechanism, DISCOVER→DEFINE→
DELIVER, the critique subagent pass, deletion pass, anti-slop audit, browser
validation — is unchanged.**

**Output (`projects/<slug>/directions/`):**
- `NN-<slug>.html` × N — unchanged
- `NN-<slug>.tokens.md` × N — new
- `index.html` — nav/overview page, filling the shared house template at
  `commands/templates/design-options-index.html` (see `commands/templates/
  MANIFEST.md`) — required output of every run, same template
  `/publish-design-options` fills for the packaged version

**Exit condition:** N directions built, validated in-browser, presented to the
user. The user (outside the harness, in conversation) picks one to carry
forward — the harness doesn't auto-select.

---

## 4. Phase 3 — Dev Handoff (new skill)

**Goal:** distill the *chosen* direction plus the full research context into
structured design decisions an AI agent can use to build a matching WordPress
block theme — including pages/interactions beyond the homepage mock. This
phase produces documents, not code.

**Input:** the chosen `directions/NN-<slug>.html` + its `.tokens.md`, plus
`research/brief.md`.

**Process:**
1. **Draft `handoff/DESIGN.md`** from the chosen direction's tokens file, in
   the google-labs-code/design.md schema (YAML frontmatter tokens + prose
   sections: Overview, Colors, Typography, Layout, Elevation & Depth, Shapes,
   Components, Do's and Don'ts). Sections with nothing to say get an explicit
   `omitted` key rather than being silently dropped.
2. **Gap-fill against team standards.** Anything DESIGN.md needs that neither
   the chosen direction nor the brief specifies falls back to this plugin's
   forked `design-standards.md` — never an untethered aesthetic call at this
   stage.
3. **Accessibility gate (`[Development]`-tagged criteria only).** The
   `[Design]`-tagged criteria (contrast, sizing, rendered interactive states)
   were already effectively checked during Phase 2's polish pass; this gate
   covers what only shows up once real markup/interaction is described —
   ARIA/alt-text expectations, motion/reduced-motion behavior, heading order,
   focus order across pages. Hard stop until it passes.
4. **Write `handoff/decisions.md`** — the structured, agent-readable notes the
   separate downstream build system consumes: which pages/templates/patterns
   are implied beyond the homepage, any interactions described in the brief
   that the static mock couldn't show, and anything explicitly deferred.

**Output (`projects/<slug>/handoff/`):**
- `DESIGN.md` — token + prose spec, ready to feed a theme-build agent
- `decisions.md` — structured notes: implied pages, interactions, deferrals

**Explicitly not produced here:** `theme.json`, `style.css`, block templates/
patterns, or anything else the separate WP-build system is responsible for.

**Exit condition:** `DESIGN.md` passes the Development a11y gate and
`decisions.md` is complete enough for a build agent to start from it without
re-deriving decisions already made.

---

## 5. Shared project folder (the contract between phases)

```
projects/<slug>/
  research/
    inputs/              raw dropped-in files
    ledger.md            Used / Dismissed / Deferred / Unaccounted per file
    brief.md             normalized brief, confidence-tagged fields
  directions/
    01-<slug>.html … NN-<slug>.html
    01-<slug>.tokens.md … NN-<slug>.tokens.md
    index.html
  handoff/
    DESIGN.md
    decisions.md
  .design-template        template id chosen from commands/templates/MANIFEST.md, so create-design and /publish-design-options agree without re-asking
  .spacefast/             created by publish-to-spacefast when directions are shared
```

Any phase can be entered independently against an existing `projects/<slug>/`
folder — e.g. re-running Phase 2 after Phase 1 already exists, or running
Phase 3 against a direction that was hand-picked without the harness at all.

---

## 6. Plugin layout

```
sp-site-design-harness/
  .claude-plugin/
    plugin.json
  skills/
    research-intake/          Phase 1 (new)
      SKILL.md
      references/
        ledger-schema.md
        brief-schema.md
    create-design/             Phase 2 (ported from consistent-high-quality-design, lightly modified)
      SKILL.md
      references/
        intake.md   gates.md   critique.md   typography.md
        polish.md   generated-media.md
    dev-handoff/               Phase 3 (new)
      SKILL.md
      references/
        design-standards.md          forked from sp-design-system
        accessibility-standards.md   forked from sp-design-system
        design-md-schema.md
  commands/
    find-font.md                ported from local-font-library
    scan-font-sources.md        ported from local-font-library
    publish-design-options.md   ported from create-design (née consistent-high-quality-design)
    templates/
      design-options-index.html  the `deck` template, shared by create-design and publish-design-options
      MANIFEST.md                 template registry + token contract
  references/
    instruction-priority.md     the harness-wide priority order (§1)
  README.md                     directive: what this is, phase-by-phase, for a
                                 new user or PM picking this up cold
```

`local-font-library`'s catalog (`~/.claude/local-font-sources/`) stays external
and shared across projects, same as today — only the commands are bundled.
`publish-to-spacefast` stays a separate, independently-installed skill this
plugin depends on rather than vendors, since it's a general-purpose publishing
tool with no design-harness-specific logic to fork.

---

## 7. Open items for a follow-up pass (not blocking, noted for later)

- Whether `decisions.md`'s structure should be finalized against the actual
  TBD downstream build system once that system's expected input format is
  known — right now it's necessarily a best guess.
- Whether font-licensing checks (a recurring hazard noted in past engagements,
  e.g. EULA restrictions blocking a public git remote) belong as a standing
  Phase 1 ledger check rather than something surfaced ad hoc.
