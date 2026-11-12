# Standards

What a conversion must meet beyond matching the designer's picture. These are the team's standards as `sp-site-design-harness` holds them (from the Special Projects designer handbook), cut down to what applies when a designer's file is turned into HTML. They are kept here until the standards move to one shared place.

## What wins when two things disagree

```text
Accessibility > the designer's file > the designer's notes and what the user supplied
> a named team default (below) > your own judgement
```

- **Accessibility is never traded for fidelity.** When the file draws something that fails a criterion below, the page still has to pass.
- **The file beats a default.** A default is only for what the file leaves open.
- **Judgement comes last, and is always recorded** as inferred.

How a conflict between accessibility and the file is settled depends on which kind of criterion it is.

## Two kinds of criterion

**Development criteria** are about how the page is built: markup, labels, keyboard, motion. fig-to-html writes the first real markup, so these are its own to meet. A page that fails one is not finished.

**Design criteria** are about what was drawn: contrast, sizes, which states exist. They are the designer's. For each one the file fails:

1. Fix it where the fix cannot be seen: a larger hit area around a small icon, a focus outline where none was drawn, a pause control beside something that moves.
2. Where the fix would change the look (a colour, a type size, the spacing between controls), build what was drawn, and record the failure in `decisions.md` § Standards for the designer, with the measured value and the value needed.

Never change a designer's colour, size or spacing silently, and never leave a failure unrecorded.

## Development criteria: the page must meet these

**Structure**
- One `h1` per page. Heading levels never skip, and are chosen for structure, not size.
- Landmarks: `header`, `nav` (with an `aria-label` when there is more than one), `main`, `footer`, and `search` around a search form.
- A skip link to the main content, as the first focusable element, styled.
- Reading order in the markup matches the visual order. A heading comes before the image or video it belongs to.
- `lang` on `html`. A viewport meta tag that does not block zoom.

**Links and controls**
- Link text says where it goes. No "click here" or "read more" on its own. Two links with the same text go to the same place.
- A link that opens a new tab says so.
- A control that does something on the page is a `button`. A control that goes somewhere is a link.
- Everything that works with a mouse works with a keyboard, in a sensible order, with no trap.
- A visible focus indicator on every focusable element, on every background it sits on. The default is in § Named defaults.
- The menu shows which page is current (`aria-current="page"`, styled).
- A hover state covers exactly what is clickable.

**Forms**
- Every field has a `label` tied to it. A placeholder is never the only label.
- An error message is text, tied to its field (`aria-describedby`), and not shown by colour alone.

**Images and media**
- Informative images have `alt` text written after looking at the image. Decorative ones have `alt=""`.
- Text is text, never a picture of text, except in a logo.
- No video or audio plays by itself.

**Motion**
- Anything that moves by itself for more than five seconds has a control that pauses it, reachable by keyboard and by touch. Pausing on hover is not enough.
- `prefers-reduced-motion: reduce` stops every animation and transition that is not essential.
- Nothing flashes. Nothing repeats a bounce or pulse more than three times. No parallax.

**Layout**
- No sideways scroll at any width in § Widths to check: the document is never wider than the window.
- Content reflows at 320px and survives 200% zoom with nothing lost.
- No information is available only on hover.

## The type-rendering baseline

Applied on every build, whatever the design. It goes in `site.css` as written.

```css
html {
	scroll-behavior: smooth;
}

body {
	font-synthesis: none;
	text-rendering: geometricPrecision;
	-webkit-font-smoothing: antialiased;
	-moz-osx-font-smoothing: grayscale;
}

h1, h2, h3, h4, h5, h6, p, blockquote, caption, figcaption, li {
	text-wrap: pretty;
}

@media (prefers-reduced-motion: reduce) {
	html {
		scroll-behavior: auto;
	}
}
```

`font-synthesis: none` means a weight or style with no font file renders in the nearest real one, not a faked bold or italic. So every weight and style the pages use needs its file in `assets/fonts/`.

`text-wrap: pretty` moves a line break wherever a paragraph would end on one word, so a page built with it differs from the export by a word here and there, with no change in height. Keep the baseline and record the differences: the theme built from the package will set text the same way.

## Design criteria: check what was drawn

Target: WCAG 2.1 AA, unless the user says AAA.

| Criterion | Pass |
|---|---|
| Text contrast | 4.5:1; 3:1 for text of 24px and up, or 18.66px and up when bold |
| Contrast of a control's boundary, an icon that is the only label, a focus indicator | 3:1 against what it sits on |
| Body text size | 16px or more |
| Smallest text anywhere | above 12px |
| Line height of body text | 1.5 or more |
| Line length of body text | about 50 to 80 characters |
| Touch target | 44 × 44px |
| Space between touch targets | 8px |
| Meaning carried by colour alone | never: a second cue is needed (underline, weight, icon, border) |
| A state shown by bold on hover | never: it moves the text around it |
| Hover and focus on a form field | never change its size |
| Text over an image | only when ornamental, or with the contrast still passing |
| Justified text | never |
| Capitals | short interface labels only |

Check contrast by number, from the colours the pages use, never by eye. List each pairing of text or icon colour and background under `pairs` in `DESIGN.md`; `check-package.mjs` computes the ratios.

## Is the design complete?

The designer's handbook says what a hand-off must contain. Check the file against it in step 2, with `frames` on the hand-off page and `find` for the names below, and report what is missing in `decisions.md` § Standards. Look before saying something is missing: search the whole file, and print the whole list of the hand-off page, not its first screen.

| The hand-off should hold | Look for |
|---|---|
| Every standard view: homepage, blog index, single post, page, archive, search results, 404 | frames by those names |
| A mobile frame for the homepage, the open menu, and any layout that does not obviously scale down | narrow frames; "menu", "overlay", "mobile" |
| Hover, focus, active and disabled states for links, buttons and form fields | component variants; "hover", "focus", "active", "disabled" |
| Form error and success messages | "error", "success", "validation" |
| Pagination | "pagination" |
| Comments, if the site has a blog | "comment" |
| Loading states, if anything loads in place | "loading" |
| Site icon, 512 × 512 | "icon", "favicon" |
| Social share image, 1200 × 675 | "share", "sharecard", "social" |
| Theme thumbnail, 1200 × 900 | "thumbnail", "preview" |
| One or two typefaces, three or four fonts in each | the fonts named in `tokens.json` |
| Fonts, icons and images free to use, or a named licence holder | ask the user about any that is not open |
| A credit to WordPress in the footer | the footer's text |

A frame that exists is a frame to use. When the file designs the open menu, a hover state or a 404, build from it, and never from a default.

## Named defaults

For what the file leaves open. Use the default, and say in `DESIGN.md` and `decisions.md` that it is the team default, not the designer's choice.

| Left open | Default |
|---|---|
| Focus indicator | A 2px solid outline, 3px off the element, in the text colour; on a dark background, in the lightest colour of the palette. It must reach 3:1 against the background |
| Hover on a text link | Underline, 2px. Never bold |
| Current page in the menu | The same underline, always on |
| Skip link | Hidden until focused, then top left, on the page background with the text colour |
| Pause control for moving content | A button of 44px beside the moving content, labelled with what it pauses |
| Target smaller than 44px | Grow the element's own box with padding and an equal negative margin, so nothing moves |
| Narrow layout with no mobile frame | One column, in the reading order of the desktop frame, with the mobile values of any variable that has them |
| Width at which a layout changes | Where the content stops fitting, found by narrowing the page, not a device width |
| Open menu on small screens, when no frame draws it | A full-width panel under the header: the links stacked, each at least 44px tall, the page behind inert |
| Reduced motion | Animations and transitions off; moving rows become rows that scroll |
| Body text measure on a page with no column width | 680px |

## Token names

Names for the palette follow the team's project template, so a theme built from the package starts with the names every team site uses.

**Palette slots.** Four roles, each filled by one colour of the design:

| Slug | Role |
|---|---|
| `canvas` | The page background: what shows behind everything |
| `surface` | The background most reading sits on, when it differs from the canvas |
| `ink` | The default text colour |
| `accent` | The colour of things that can be pressed |

- Fill a slot only with a colour that plays that role. A design with one background has no `surface`.
- When two roles could claim a slot (a page whose body is blue but whose reading is on white), choose by the definitions above, and say which way it went in `DESIGN.md`.
- Every other colour keeps a slug from its Figma name: the last part of the variable's path, lower case with hyphens (`Background Colors/yellow-2` → `yellow-2`), with the part before it added when two would collide.
- Colours with the same value are one token. List every Figma variable that holds it.
- A colour the pages use that has no variable gets a plain name for what it does (`button-gradient-shade`).

In `site.css` a palette token is `--color-<slug>`. In `DESIGN.md` the colour key is the slug, with the Figma variable beside it, so the name can always be traced to the designer's file.

**Everything else** (font sizes, spacing, radii, shadows) keeps its Figma name, lower case with hyphens, as `--<name>`. The team has no settled names for these yet.

## Widths to check

The frames' own widths, and: 320, 375, 414, 768, 1024, 1366, 1440 and 1600 or more. At each, the document is no wider than the window, nothing overlaps or is cut off, and the header's controls stay on one line.

## An independent look

The one who built a page sees what they meant to build. After your own check passes, have the page looked at once by a reviewer who knows nothing of how it was made:

- Start one subagent. Give it the export and the page's screenshot side by side, cut into screen-sized pieces and scaled to about 800px wide, at each frame width; one sentence on what the page is; and the list in `views.md` § Differences from the exports, so it does not report what is already settled.
- Tell it only what its pictures show. A capture taken at rest has no control that a script adds, so do not list one as a known difference.
- Do not explain a difference away before it reports. Told that text sets 1% narrower, a reviewer still found line breaks that had another cause.
- Ask it for every visible difference between the two, by section, each with where it is and how large, and for anything on the page that looks broken at either width. Ask for nothing else: not praise, not a score.
- Fix what it finds and check the changed sections again. A finding that asks for something the file does not draw is not yours to act on: record it as an open item.
- Two rounds at most. What is left goes in `views.md`.
