---
name: iterate
description: Apply feedback to an existing design direction or built block theme fast — swap a token, fix copy, adjust a property, rework one section, or work through a pasted list of partner notes. Use whenever the user asks to change, fix, tweak, or revise something in an existing `directions/NN-<slug>.html` or a block theme built from this harness's handoff. Does not run the create-design engine (no critic, no gates, no re-exploration); requests that need a new direction or a new concept are routed back to `create-design`.
argument-hint: "[direction file or theme path] <change request or pasted feedback>"
---

# Iterate

Fast revision path for the sp-site-design-harness. `create-design` makes
designs; this skill changes them. The whole point is speed: **read as little as
possible, edit directly, verify only what changed.**

Do **not** load `create-design`'s references, re-read `research/brief.md`,
spawn critic subagents, re-run the deletion pass, or narrate CSS reasoning.
The user is a designer who codes. When they name a variable, a selector, or a
value, do exactly that.

## Step 0 — Resolve the target (cheap)

Scope root: an explicit path in the arguments, else `git rev-parse
--show-toplevel`, else `$PWD` (same resolution as `/publish-design-options`).

| State | Target |
|---|---|
| No `handoff/DESIGN.md` | **HTML phase.** `directions/NN-<slug>.html`. Ask which one only if the request doesn't make it clear. |
| `handoff/DESIGN.md` exists and a theme path is known (arguments, or a `.theme-path` file at the scope root, absolute or relative to it) | **Theme phase.** The block theme. |
| `handoff/DESIGN.md` exists, no theme path | Ask once for the theme folder, then write it to `.theme-path` so nobody has to ask again. |

**After handoff, `directions/*.html` is frozen.** Never edit it. If asked to,
say it's frozen and make the change in the theme instead. Two live sources
drift apart. See `../../DECISIONS.md` (2026-09-25). If the request names a
direction other than the one `DESIGN.md` describes, say so and ask before doing
anything.

## Step 1 — Classify, say so in one line, then act

Give each request a level and state it in one line, e.g. `L0 — swapping
--color-border to --stone in 02-conditions.html`. The user can override ("just
do it", "treat this as L1"). If the level isn't obvious, read
`references/levels.md`.

### L0 — Direct edit

Token or variable swap, copy change, one property.

- HTML: read only the `:root` block and grep for the selector or variable. Theme:
  read only the relevant `theme.json` settings/styles key, or grep the
  pattern/template.
- A color named in words ("plum", "the terracotta") means the palette token of
  that name if one exists. Otherwise pick a value that fits the palette and
  report it.
- Edit. That's it: no screenshot unless asked, no references, no critique.
- **One exception, contrast.** Whenever a color changes (a token's value, or a
  usage switched to a different token), check numerically against the surface
  each usage sits on: text 4.5:1 (3:1 at large sizes); borders, separators,
  focus rings and other UI 3:1. Reading the rules that set those surfaces is
  part of the check. Accessibility outranks everything
  (`../../references/instruction-priority.md`). Report a failure and suggest
  the nearest passing value rather than silently shipping it. Also update
  anything derived from the old value, such as a hard-coded hover shade or a
  contrast ratio recorded in `.tokens.md`.
- If the file has no role alias for what was asked (e.g. no `--color-border`,
  so borders reference `--stone` directly), make the change at each usage and
  offer to add the alias so next time it's a one-line change.

### L1 — Local revision

Rework one section or component: a hero layout, card treatment, nav behavior.

- Read just that section's markup and CSS.
- For subjective notes ("cramped", "heavy"), take a **before** screenshot of
  the section first, so you fix what you see rather than guessing.
- Edit, then screenshot **that section** at 375px and 1440px. Check it for
  clipping, overflow, and alignment. See "Screenshots" below for setup.
- Weigh the screenshot against `../create-design/references/craft-corrections.md`
  **for that section only.** Does anything read as accidental rather than
  chosen?
- No critic subagent. No full-page validation unless the change reflowed
  the rest of the page.
- If the screenshot shows another problem nearby that the note didn't ask
  about, mention it in one line; don't fix it.

### L2 — New direction or concept change

"None of these feel right", "make it feel completely different", or anything
that changes the visual thesis. Stop and hand it to `create-design`: DISCOVER
if the concept or mood is wrong, DEFINE if the concept holds but the design
language (type, color, surface, shape) is wrong. Say which, and why, in one
line. Don't attempt it here.

## Batch mode — pasted partner feedback

1. Split the notes into individual items. Classify each one and show the list
   (item · level · target) in one compact table. Don't start until the list is
   shown. The user may re-level items.
2. Do all the L0s in one pass, then the L1s one at a time, each with its own
   before/after screenshots.
3. Route any L2s to `create-design` together, after the rest are done.
4. HTML phase: offer `/publish-design-options` to update the same Spacefast
   link so the partner can just refresh. Don't publish unless asked.

## Keep the token files in sync — same edit, every time

| Phase | Authoritative | Also update |
|---|---|---|
| HTML | the `:root` block in `NN-<slug>.html` | the matching line in `NN-<slug>.tokens.md` |
| Theme | `theme.json` | the matching token in `handoff/DESIGN.md` (frontmatter, and prose if it names the value) |

Update every line that names the changed value or role, including prose; if
the prose's description no longer fits ("quiet hairlines"), fix the wording
too. Point at another token where the format allows (`var(--stone)`,
`{colors.sage}`). Where it doesn't, as in `theme.json` palette entries, use
the literal value.

## Screenshots (L1, or when asked)

The browser pane shows `file://` pages as static snapshots that can't be
resized, so serve the folder: `python3 -m http.server 8765 --bind 127.0.0.1`
(in the background) and open `http://127.0.0.1:8765/<file>`. Use explicit
sizes, 375×812 and 1440×900, since the "desktop" preset only matches the
pane's width. Reset to the desktop preset and stop the server afterward. In
the theme phase, use WordPress Studio's screenshot tool if it's available.

## Change log

Append one line per change to `directions/NN-<slug>.changes.md` (HTML phase) or
`handoff/changes.md` (theme phase), creating it if needed:

```
- 2026-09-25 · L0 · "borders feel too heavy" (partner) · --color-border → var(--stone) · 02-conditions.html:31, 02-conditions.tokens.md
```

Date · level · feedback (quoted, with the source if known) · what changed ·
files, with lines comma-separated per file (`02-x.html:94,225,298`). `dev-handoff` pulls the HTML-phase log into `decisions.md`.

## Reporting

One to three lines: what changed and where (`file:line`), plus any contrast
result. No recap of the process. Two things are worth one extra clause each:
a request whose effect seems to contradict its own feedback ("borders feel
loud" → a *darker* border color), and a contrast failure you saw in passing
outside the change. Flag them; don't fix them unasked.
