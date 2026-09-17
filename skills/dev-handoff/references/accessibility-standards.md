# Accessibility Standards
Source: WP Special Projects Designer Handbook — "Accessibility Best Practices for
Designers – At a Glance" (wpspecialprojectsp2.wordpress.com/designer-handbook/accessibility-guidelines/)
and "QA Checklist and Performance Guidelines"
(wpspecialprojectsp2.wordpress.com/developer-handbook/qa-checklist-and-performance-guidelines/).

Note: the handbook references a deeper internal document, "Special Projects
Accessibility Standards: Defining What Success Means" (Google Doc), as the comprehensive
source of a11y success criteria beyond design. This file is built from the handbook's
public quick-reference page only — treat it as the baseline, not the exhaustive source.

## Phase Labels

Every criterion below is tagged **[Design]** or **[Development]** — which phase of the
`sp-design-system` pipeline gates it, per `SKILL.md` Step 6 (design-criteria check,
against the style tile) and Step 8/11 (accessibility lint plus manual review, against
the built theme). The split is by *what kind of thing the criterion is*, not by
importance — nothing here is optional at either phase.

- **[Design]** — a design decision: contrast, sizing, spacing, whether a state is
  visually distinct. Decidable by looking at the style tile, before any markup exists,
  and cheap to fix there.
- **[Development]** — a matter of implementation: semantic markup, ARIA, keyboard
  behavior, programmatic labeling, alt text, motion. Not checkable against a static tile
  because it depends on how the thing is actually built.

Every criterion carries exactly one tag. If you find one that seems to need both, split
it into its design half and its implementation half rather than leaving it ambiguous —
an unlabeled or double-labeled criterion is the failure mode this section exists to
prevent (see `SKILL.md`'s note on `omfest`'s two findability gaps).

## Target Level (configurable per project)

Default target: **WCAG 2.1 Level AA**.
Level AAA is the occasional opt-in for specific projects whose audience benefits from the
higher, stricter standard — not the default. Whichever level is chosen must be an
explicit, logged decision, not a silent assumption. If the project's DESIGN.md or brief
does not state a level, assume AA and note that AAA is available as an opt-in.

| Criterion                        | AA (default)        | AAA (opt-in)        |
|-----------------------------------|----------------------|------------------------|
| Large text contrast (>18.66px bold / >24px regular) | 3:1  | 4.5:1        |
| Normal text contrast              | 4.5:1                | 7:1                    |
| UI component contrast (against adjacent colors) | 3:1     | 3:1 (no stricter AAA value defined) |
| Smallest body font size           | above 12px           | above 16px             |
| Minimum touch/click target size   | 44px × 44px          | 44px × 44px            |

`npx @google/design.md lint` enforces the AA contrast minimum automatically as part of
the build gate. Everything else in this file — including the AAA-only rules — must be
checked manually, since the linter does not know which level a given project targets.

## Content Structure

- **[Development]** Navigation and section-identification system must be consistent
  across pages.
- **[Development]** Consider whether the site benefits from breadcrumbs or other "where
  am I" mechanisms.
- **[Development]** Create a clear, hierarchical heading structure (H1, H2, etc. used in
  logical order, not chosen for visual size alone).
- **[Development]** Ensure a logical reading order for both screen-reader users and
  visual users.
- **[Design]** All necessary information must be visible/accessible on devices that
  don't support hover states — nothing critical hidden behind hover-only. This is a
  design decision (does anything on the tile depend on hover to be understood?), checked
  against the tile itself.
- **[Development]** Link text must convey its purpose on its own. Eliminate generic link
  text ("read more," "click here," "previous/next") — prefer linking the actual title or
  image. Depends on real content and real links, neither of which exist at tile stage.
- **[Development]** Avoid abbreviations (e.g. "N/A") in hard-coded site text.

## Color

- **[Design]** Run every color pairing through a contrast checker before locking the
  palette (Figma: Stark or Contrast plugin) — or the style tile itself, once one exists.
- **[Design]** UI components need a minimum 3:1 contrast ratio against adjacent colors —
  this is separate from text contrast and applies to borders, icons, and control
  boundaries.
- **[Design]** Never convey content or important information using color alone.
- **[Design]** State changes (hover, active, visited, error) can never be signaled by
  color alone — pair with a second cue: font-weight/style change, underline or border,
  background color (contrast-checked), or an icon. Checkable on the tile as long as the
  state is actually rendered there, per `SKILL.md` Step 5 — not merely described.
- **[Design]** Borders on/around links, buttons, and form fields: minimum 2px (stark
  borders, or reversed foreground/background, are the recommended approach for focus
  states).

## Typography

- **[Design]** Body font size: 16px or greater.
- **[Design]** Smallest font anywhere in the design: above 12px (AA) / above 16px (AAA).
- **[Design]** Text block width: ~50–80 characters per line.
- **[Design]** Line height: minimum 1.5 (150%). Paragraph spacing: at least 2x the font
  size. (AA)
- **[Design]** Letter spacing may be adjusted for readability — don't over-tighten or
  over-loosen; follow standard letter-spacing best practices for the chosen typeface.
- **[Design]** Choose fonts that are simple, unembellished, and clear. Avoid display,
  cursive, or novelty faces for body/UI text (decorative fonts are fine for
  logos/wordmarks only). AAA: also consider fonts that are easier to read for people with
  dyslexia.
- **[Design]** Do not justify text.
- **[Design]** Except for logos, never render text as an image.
- **[Design]** Exclude or minimize uppercase text treatments. If used at all, limit to
  short, non-user-editable UI text ("Next," "Previous") — uppercase hurts readability at
  length and some screen readers may read uppercase words as acronyms.
- **[Design]** AAA: don't center text longer than 3 lines; avoid centering headings
  other than page titles.
- **[Design]** Choose typefaces whose real italic and bold weights will actually be
  used — decide this before the tile, since the weight ladder shown on the tile is what
  gets contrast- and weight-checked in Step 6.
- **[Development]** Import the real italic/bold weight files chosen above into the theme
  build — don't rely on the browser's synthetic ("faux") italic or bold. Verify by
  disabling `font-synthesis` and confirming the real weight/style still loads. This is
  the implementation half of the criterion directly above: the tile settles *which*
  weights are wanted; the build verifies the *real files* for them actually shipped.

**Font smoothing and text-rendering baseline: see the Type-Rendering Baseline section of
`design-standards.md`.** These rules used to be duplicated here. They are typographic
rendering conventions rather than accessibility success criteria, and keeping the only
copy in this file meant a build looking for type conventions in `design-standards.md`
found nothing there and reinvented them — which is exactly what happened on `omfest`.
The baseline now lives in one place, with `font-synthesis: none` added to it, and
`design-standards.md` owns it.

## Links, Hover & Focus States

- **[Design]** Inline link, hover, and focus state changes must never rely on color
  alone — pair with a font-style/weight change, underline or border, background color
  (contrast-checked), or icon. Checkable on the tile if the states are rendered there.
- **[Design]** Avoid using bold as an inline :hover state — it changes the space the
  text occupies and can trigger layout reflow.
- **[Development]** Identify links that open in a new tab or window — programmatic
  labeling (`aria-label` or visible text), not a visual concern.
- **[Design]** Focus states must be clear and evident for keyboard navigation. Use stark
  borders (min. 2px) or reversed foreground/background colors. The tile check verifies
  the state is visually distinct; whether it actually appears on `:focus-visible` for
  every real keyboard-focusable element is a Development-phase concern (see Forms below).
- **[Design]** Navigation bars should include a style that shows the visitor's current
  location.
- **[Design]** Hover-state scope must match click-target scope — never render a hover
  state across an entire card, row, or container when only part of it (e.g. the title)
  is actually clickable. If the whole element is meant to be a single click target, style
  and build it that way; otherwise scope the hover to just the clickable part. Checkable
  on the tile once the component's interactive states are rendered.
- **[Development]** WP block-editor-only builds (no custom JS/plugin) are often limited in
  how far the click target can be expanded — e.g. making an entire card a single link may
  not be achievable without added code. When that's the case, implement the fallback from
  the criterion above: scope the hover state down to match whatever is truly clickable
  rather than leaving a full-card hover that overstates the interaction.
- **[Design]** AAA: include styles for focus states across all major page sections and
  situations (headers, footers, body content, buttons, on-light, on-dark, etc.) — not
  just the default link/button state.

## Forms & Clickable Areas

- **[Design]** Minimum target size for touch/mouse: 44px × 44px.
- **[Design]** Minimum spacing between clickable elements: 8px.
- **[Design]** Form field labels should reside outside the field itself, not inside as
  the only cue — a layout decision, checkable on the tile.
- **[Development]** Labels must be programmatically associated with their field (`<label
  for>` or equivalent) — the implementation half of the criterion above. A label that
  sits outside the field visually but isn't associated in markup passes the tile check
  and fails this one.
- **[Design]** Placeholder text is supplementary only — never the sole carrier of
  necessary information (formatting hints are fine).
- **[Design]** Ensure the contrast between placeholder text and background is visibly
  lower than the contrast between real input value and background, so it's clear which
  is which.
- **[Design]** Required fields must be clearly labeled; if using an asterisk, define
  what it means somewhere on the page ("* = Required").
- **[Design]** Design and show explicit error/validation message states on the tile —
  don't leave error handling to be improvised at build time. This is exactly the status-
  color gap `design-standards.md`'s Status & Semantic Colors section now covers.
- **[Development]** Wire the error state to real validation and associate the message
  with its field programmatically (`aria-describedby` or equivalent) — the tile shows
  what the state looks like; the build makes it actually fire and be announced.
- **[Design]** Hover & focus states on form fields must not cause layout shift (no
  jumping content).

## Media & Motion

- **[Development]** Avoid autoplaying video where possible; provide play/pause controls
  for any media.
- **[Development]** Give visitors an option to turn off or reduce motion.
- **[Development]** Any animation triggered by interaction must be able to be disabled,
  unless the motion itself is essential to the function or information being conveyed
  (respect `prefers-reduced-motion`).
- **[Development]** Avoid motion that distracts from content; avoid flashing elements
  entirely; limit any bounce/repeat effect to a maximum of 3 cycles.
- **[Development]** Avoid parallax scrolling or any effect where foreground/background
  move at different speeds.
- **[Development]** Use accessible media players.
- **[Development]** Headings must appear *structurally* before any related
  video/image/graphic in the markup, even if they render visually after it —
  non-visual users need the heading first. (AAA, but good practice generally.)
- **[Design]** Text overlaid on images is only acceptable if it's purely ornamental or
  truly essential — a design decision about the treatment, checkable on the tile's image
  treatment example.
- **[Development]** For audio/video, consider whether captions, subtitles, transcripts,
  or descriptions of visual information are needed (required at AAA).

## Images

- **[Development]** All images require appropriate, descriptive alt text (empty
  `alt=""` only for genuinely decorative images). Depends on real images and real
  content, neither of which exists at tile stage.
- **[Design]** Icons and graphics should be SVGs; all imagery should appear
  crisp/high-resolution at every viewport size — checkable against the tile's image
  treatment example.

## Navigation & Structure

- **[Design]** Main navigation must be easily identifiable; labels clear, concise, and
  consistent site-wide — this is the header/logo/nav treatment the tile is required to
  show.
- **[Development]** Keep the number of buttons/links per page or section reasonable —
  don't overload. Depends on the real page's real content.
- **[Development]** Site search must be easy to find and access if the site has one.
- **[Development]** URLs must be meaningful and user-friendly.
- **[Design]** Logo/site name should be prominent; site purpose should be clear
  alongside any tagline — part of the header treatment on the tile.
- **[Development]** Homepage should be digestible within roughly 5 seconds. Depends on
  the real homepage, not the tile.

## AAA-Only Additions (opt-in level)

- **[Development]** Include a "Skip to Content" mechanism to bypass repeated content
  blocks — style it, don't leave it as unstyled default.
- **[Development]** Include a sitemap.
- **[Development]** Include an accessibility statement.
- **[Development]** Consider a table of contents for longer pages.
- **[Development]** Include descriptive sub-headings under page titles.
- **[Design]** Use HTML/CSS that allows browser-level color overrides without breaking
  the distinction between page regions (header, section breaks, footer) — this was the
  team's actual resolution on a past project (Emily Ladau) in preference to building a
  custom color-selection tool. A design decision about how regions stay distinguishable
  under an override, checkable in principle against the tile's palette.

## Design-Phase Gate (Step 6 — checked against the style tile)

Before a style tile is approved, confirm every **[Design]**-tagged criterion above, plus:

- [ ] Color contrast checked and passes the target level (AA default, AAA if opted in)
- [ ] UI component contrast (borders, icons, controls) checked, not just text
- [ ] All interactive states are rendered on the tile — hover, focus, active, error —
      not merely described, and each is visually distinct without relying on color alone
- [ ] Touch/click targets meet 44×44px minimum with adequate spacing
- [ ] Hover-state scope matches click-target scope on every card/row/container pattern —
      no full-element hover over a partially-clickable component
- [ ] Type sizes and line-height meet the stated minimums, and any weight light enough to
      forfeit WCAG's relaxed large-text threshold has been rechecked against the
      stricter one

A tile that fails any of these is not an approvable direction. Fix it before presenting
it, per `SKILL.md` Step 6.

## Development-Phase Gate (Steps 8 & 11 — checked against the built theme)

Before the finished theme is considered accessibility-complete, confirm every
**[Development]**-tagged criterion above, plus:

- [ ] `npx @google/design.md lint DESIGN.md` exits 0 with no unresolved errors
- [ ] Forms include wired error/notification states and programmatically-associated
      labels
- [ ] Alt text policy defined and applied for every image type used
- [ ] Motion/animation has a disable path or is `prefers-reduced-motion`-safe
- [ ] Heading order is logical and structurally precedes related media
- [ ] Link text is specific and descriptive — no generic "click here" / "read more"
- [ ] If AAA is targeted: skip-to-content, sitemap, and accessibility statement present

This gate verifies implementation of decisions already made and approved at the tile —
it should not be discovering new design problems this late. If it does, that is a
process failure in Step 6, worth noting the same way an unresolved Gap reaching Step 11
is a process failure in Step 3.