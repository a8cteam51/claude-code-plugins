# sp-site-design-harness

A Claude Code plugin that takes a client/partner site engagement from raw
brand material to a developer-ready design system for a WordPress block
theme.

**This plugin stops at design decisions.** It produces a brief, a set of
designed HTML directions, and a `DESIGN.md` + `decisions.md` handoff — it
does **not** author `theme.json`, `style.css`, block templates, or otherwise
build the WordPress theme itself. Actual theme building happens in a
separate, external system this harness hands off to.

## The three phases

```
Research  →  Design  →  Dev Handoff
```

Each phase is its own skill, independently usable, sharing one
`projects/<slug>/` folder as the contract between them. Any phase can be run
standalone against an existing folder — e.g. run Dev Handoff against a
direction that was hand-picked without ever running Research or Design
through this plugin.

### Phase 1 — Research (`research-intake` skill)

Gathers whatever brand material exists — PDFs, style guides, copy docs,
existing graphics/photography/fonts, reference URLs, an existing
`theme.json`, or nothing at all — and turns it into a confidence-tagged
brief. Every input file gets a disposition (`Used` / `Dismissed` /
`Deferred` / `Unaccounted`); an unexamined file blocks progress, but sparse
or empty input never does. Invoke it by describing a new engagement, or by
asking Claude to run intake/research on dropped-in material.

**Output:** `research/ledger.md`, `research/brief.md`.

### Phase 2 — Design (`create-design` skill)

The design engine — DISCOVER → DEFINE → DELIVER, with a seed/risk-ladder
variety mechanism, independent critique pass, deletion pass, and anti-slop
audit. Produces N distinct, responsive, HTML-only homepage directions with
real creative variety, avoiding generic AI-default interfaces. If
`research/brief.md` exists it's consumed directly; otherwise this skill runs
its own short conversational intake. Invoke it by asking Claude to design or
improve the visual design of a site, landing page, or similar.

**Output:** `directions/NN-<slug>.html`, `directions/NN-<slug>.tokens.md`,
`directions/index.html`.

The user picks a direction outside the harness, in conversation — this
plugin never auto-selects one.

### Phase 3 — Dev Handoff (`dev-handoff` skill)

Distills the chosen direction's tokens plus the research brief into
`DESIGN.md` (the google-labs-code/design.md schema) and `decisions.md`
(implied pages/templates beyond the homepage, interactions the static mock
couldn't show, explicit deferrals). Gap-fills against this plugin's forked
team design standards, then runs a hard-stop accessibility gate — only the
`[Development]`-tagged criteria, since `[Design]`-tagged criteria were
already checked during Phase 2's polish pass. Invoke it once a direction has
been chosen and needs to be handed to a build agent.

**Output:** `handoff/DESIGN.md`, `handoff/decisions.md`.

## Commands

- `/find-font` — browse the local font catalog (`~/.claude/local-font-sources/`)
  for a family matching a mood/use-case description
- `/scan-font-sources` — refresh the local font catalog's index
- `/publish-design-options` — package a session's built directions behind one
  private Spacefast share link for partner review (requires the
  `publish-to-spacefast` skill, installed separately — see below)

## The shared project folder

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
  .design-template        template id chosen for this project's index page (see commands/templates/MANIFEST.md)
  .spacefast/             created by publish-to-spacefast when directions are shared
```

## Instruction priority

One priority order applies across all three phases when sources conflict:

```
Accessibility standards > Explicit brand rules > Project brief
> team design-standards defaults > Claude's own generalist judgment
```

See `references/instruction-priority.md` for the full explanation and how
each phase applies it.

## Dependencies

`publish-to-spacefast` is a separate, independently-installed skill this
plugin depends on for `/publish-design-options` — it is a general-purpose
publishing tool with no design-harness-specific logic, so it's not vendored
into this plugin. Install it separately if you want that command to work.

`local-font-library`'s catalog (`~/.claude/local-font-sources/`) is external
and shared across projects and plugins — only the `/find-font` and
`/scan-font-sources` commands are bundled here; the catalog itself lives
outside this plugin, same as before.

## Out of scope, by design

Building the actual WordPress block theme — `theme.json`, `style.css`,
block templates/patterns, and handing off to a build tool
(`claude-code-wordpress.com`, `wp-site-creator`, or similar) — is
deliberately not part of this plugin. It ends at `handoff/DESIGN.md` and
`handoff/decisions.md`; a separate, external system is responsible for
turning those into a built theme.
