# sp-site-design-harness

A Claude Code plugin that takes a client/partner site engagement from raw
brand material to a developer-ready design system for a WordPress block
theme.

**This plugin stops at design.** It produces a brief, a set of designed
HTML homepage directions, and, once one is chosen, the whole site designed
as HTML plus a `DESIGN.md` + `decisions.md` handoff. It does **not** author
`theme.json`, `style.css`, block templates, or otherwise build the WordPress
theme itself. html-to-block-theme builds the theme from the handoff.

## The phases

```
Research  →  Design  →  (partner picks, /iterate)  →  Prep for Handoff
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

### Phase 3 — Prep for Handoff (`/prep-handoff`)

Run once the partner has chosen a direction. It confirms the choice with
you, then works in stages and can be re-run to resume:

1. **Confirm** the chosen direction (recorded in `.chosen-direction`;
   `directions/` is frozen from here).
2. **DESIGN.md** via `dev-handoff` Steps 1–3.
3. **The rest of the site** via `design-site-templates`: blog index (also
   used for archives and taxonomies), single post with comments, page,
   search results and 404, plus state files (no comments yet, comments
   closed, no search results). Designed in the chosen direction's language
   from DESIGN.md, sharing one stylesheet and identical header and footer.
4. **Partner review**: `/publish-design-options` publishes a click-through
   site preview to the same Spacefast link; feedback goes through
   `/iterate`.
5. **Package**: `decisions.md` via `dev-handoff` Step 4, then a package
   check.

**Output:** `handoff/DESIGN.md`, `handoff/decisions.md`, `handoff/views.md`,
`handoff/source/` (the site as HTML, ready for html-to-block-theme).

`design-site-templates` also works on its own, outside this harness: give
it any homepage HTML file and an output folder.

**Known gaps (as of 0.3.0).** Tested end to end once, on one project.
- html-to-block-theme builds from the HTML in `handoff/source/`, but it
  doesn't read `DESIGN.md` or `decisions.md` yet. That's milestone M2 of
  the integration plan. Until then, anything that lives only in those docs
  (required build fixes, real IA, content status) has to be applied by
  hand.
- State files (`single--no-comments.html` and the like) are meant to fold
  into their parent templates. Whether h2bt does that without help hasn't
  been tested.
- The site-preview publish (`/publish-design-options handoff/source/`)
  hasn't been run yet.

#### `dev-handoff` skill

Distills the chosen direction's tokens plus the research brief into
`DESIGN.md` (the google-labs-code/design.md schema) and `decisions.md`
(implied pages/templates beyond the homepage, interactions the static mock
couldn't show, explicit deferrals). Gap-fills against this plugin's forked
team design standards, then runs a hard-stop accessibility gate — only the
`[Development]`-tagged criteria, since `[Design]`-tagged criteria were
already checked during Phase 2's polish pass. `/prep-handoff` runs it for you;
it can also be run on its own.

**Output:** `handoff/DESIGN.md`, `handoff/decisions.md`.

## Supporting skills

- `/find-font` — browse the local font catalog (`~/.claude/local-font-sources/`)
  for a family matching a mood/use-case description
- `/scan-font-sources` — refresh the local font catalog's index
- `/iterate` — apply feedback fast: token swaps, copy, one-section revisions,
  or a pasted list of partner notes, each classified L0/L1/L2 so small changes
  skip the full design engine. Works on the HTML directions until one is
  chosen, then on the site views in `handoff/source/`, then on the built
  block theme (each earlier stage freezes when the next begins)
- `/publish-design-options` — package a session's built directions, or a
  full site preview, behind one private Spacefast share link for partner
  review (requires the
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
    NN-<slug>.changes.md  /iterate change log, pre-handoff
    index.html
  handoff/
    DESIGN.md
    decisions.md
    views.md              the designed views, shared chrome, content status
    source/               the site as HTML: home, views, state files, assets/site.css
    changes.md            /iterate change log, after a direction is chosen
  .chosen-direction       the confirmed direction, recorded by /prep-handoff
  .theme-path             built theme location, recorded by /iterate
  .design-template        template id chosen for this project's index page (see skills/publish-design-options/templates/MANIFEST.md)
  .spacefast/             created by publish-to-spacefast when directions are shared
```

## Instruction priority

One priority order applies across every phase when sources conflict:

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
`/scan-font-sources` skills are bundled here; the catalog itself lives
outside this plugin, same as before.

## Out of scope, by design

Building the actual WordPress block theme — `theme.json`, `style.css`,
block templates/patterns, and handing off to a build tool
(`claude-code-wordpress.com`, `wp-site-creator`, or similar) — is
deliberately not part of this plugin. It ends at the `handoff/` package;
html-to-block-theme turns that into a built theme. The one exception is `/iterate`, which can
apply partner feedback to that built theme afterward.
