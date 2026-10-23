---
name: prep-handoff
description: Take the partner's chosen homepage direction through to a complete handoff — confirm the choice, write DESIGN.md, design the rest of the site (blog index, single post with comments, page, search, 404), publish a site preview for partner review, then package everything for html-to-block-theme. The step after create-design and partner review in sp-site-design-harness. Use when a direction has been chosen ("they picked option 2", "go with Terraced Garden", "prep the handoff", "/prep-handoff"). Resumable: re-run it after partner review to continue where it left off.
argument-hint: "[chosen direction file or name]"
---

# Prep for handoff

The harness step after a partner picks a direction. It runs other skills in
order and keeps track of where the project is; the work itself lives in
those skills:

| Stage | Done by |
|---|---|
| 1. Confirm the choice | this skill |
| 2. `handoff/DESIGN.md` | `dev-handoff` Steps 1–3 |
| 3. The rest of the site | `design-site-templates` |
| 4. Partner review | `/publish-design-options` (site preview) and `/iterate` |
| 5. Package | `dev-handoff` Step 4, then a package check here |

It ends where html-to-block-theme begins. It never builds the theme.

## Step 0 — Where are we?

Scope root: an explicit path in the arguments, else `git rev-parse
--show-toplevel`, else `$PWD` (same as `/publish-design-options`). The
project folder holds `directions/`, and maybe `research/` and `handoff/`.

Work out the stage from what's on disk, say it in one line, and continue
from there. Don't redo a finished stage unless asked.

| On disk | Next stage |
|---|---|
| No `.chosen-direction` | 1 |
| `.chosen-direction`, no `handoff/DESIGN.md` | 2 |
| `DESIGN.md`, no `handoff/source/home.html` | 3 |
| `handoff/source/` with views, no `handoff/decisions.md` | 4 (or 5 if the user says the partner signed off) |
| `decisions.md` newer than every file in `handoff/source/` | Done: report the package and stop |
| `decisions.md` older than something in `handoff/source/` | 5 again: the set changed after packaging |

## Step 1 — Confirm the chosen direction

This is a hard gate. Nothing after it is cheap to undo, and the choice
freezes `directions/`.

1. Identify the direction from the arguments or the conversation. If it
   isn't clear, list the directions (number, name, file) and ask.
2. Confirm it back in one short block: the direction's name, its file, its
   last-modified time, and the number of entries in its `.changes.md` if
   there is one, so a stale or wrong file is visible. Ask for an explicit
   yes.
3. On yes, write the path, relative to the scope root, to `.chosen-direction`
   (one line, e.g. `directions/02-terraced-garden.html`).

From here on `directions/` is frozen. `/iterate` works on
`handoff/source/` instead.

## Step 2 — DESIGN.md

Read `../dev-handoff/SKILL.md` and run its Steps 1–3 against the chosen
direction: draft `handoff/DESIGN.md`, gap-fill against team standards, and
pass the `[Development]` accessibility gate. Don't write `decisions.md` yet;
that's Stage 5, once the whole site exists.

This can run in a background agent. While it does, start Stage 3's shared
foundation (`design-site-templates` Step 3: copy, assets, stylesheet move,
verify), which doesn't depend on DESIGN.md. Don't design any view until
DESIGN.md is back.

## Step 3 — Design the rest of the site

Read `../design-site-templates/SKILL.md` and follow it with:

| Input | Value |
|---|---|
| `homepage` | the file in `.chosen-direction` |
| `out` | `handoff/source/` |
| `notes` | `handoff/views.md` |
| `DESIGN.md` | `handoff/DESIGN.md` |
| tokens | the chosen direction's `.tokens.md` |
| brief | `research/brief.md`, if it exists |
| change log | the chosen direction's `.changes.md`, if it exists |

The templates are written straight into `handoff/source/`, not designed
somewhere else and copied in. One copy means one source of truth (the same
lesson as authoring tokens straight into their destination file).

## Step 4 — Partner review

Offer to publish the site preview: `/publish-design-options handoff/source/`
runs in site-preview mode and updates the project's existing Spacefast space
as a new version, so the partner's link stays the same. Publish only when
the user says to.

Then stop and wait. Feedback goes through `/iterate`, which edits
`handoff/source/` in this stage. After a batch of changes, offer to
republish. When the user says the partner has signed off, continue to Step 5
(or they re-run `/prep-handoff`, and Step 0 resumes here).

## Step 5 — Package

1. Read `../dev-handoff/SKILL.md` and run its Step 4 to write
   `handoff/decisions.md`. It folds in `handoff/views.md` and the change logs.
2. Check the package, reading the results rather than assuming:
   - Every `*.html` in `handoff/source/` loads over loopback HTTP with no
     same-origin request failing and no console errors.
   - No path in `handoff/source/` reaches outside it (`grep` for `../` and
     absolute `file://` or `/Users/` paths in `href`, `src` and `url()`).
   - Every file `views.md` lists exists, and every view file is listed.
   - `DESIGN.md`'s color values match `:root` in `handoff/source/assets/site.css`.
     If they differ, `site.css` wins; update DESIGN.md and say so.
3. Report what's in the package and the next step:

```
handoff/
  DESIGN.md     rules, tokens, reasoning
  decisions.md  what the build must do that the HTML doesn't show
  views.md      the views, shared chrome, content status
  source/       the site as HTML (home + views + states + assets)
```

Next: run html-to-block-theme on `handoff/source/`.

## Reporting

At each stopping point, a few lines: the stage reached, what was written,
and what happens next. Don't recap the work the called skills already
reported.
