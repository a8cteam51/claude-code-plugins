# The handoff package

What fig-to-html writes, file by file. It is the same package `sp-site-design-harness` writes with `/prep-handoff`, so that html-to-block-theme reads either without knowing which made it: three documents, and beside them a `source/` folder of plain HTML.

```text
<out>/
  handoff/
    DESIGN.md      rules, tokens, reasoning
    decisions.md   what the build must do that the HTML does not show
    annotations.md every annotation in the frames read, as the reader found it
    views.md       sitemap, each view, what it builds as, content status
    source/        the pages as HTML, one stylesheet, local fonts, assets
  extract/         what the reader wrote, per frame; beside the package, not in it
```

`handoff/` is the package. Paths below are inside it.

Where the two packages differ, and why:

- **This one can be partial.** The harness designs every view of a site. fig-to-html converts the frames it was given and designs nothing the file lacks. `views.md` says which destinations have no file yet, and the next run adds to the same package.
- **Its authority is the designer's file.** The harness fills a gap from team standards. Here a gap is recorded as inferred or as an open item, never filled by taste.
- **It has a fourth document, `annotations.md`.** The harness has no designer's file to read notes from. html-to-block-theme reads it when a package has one.
- **Its palette uses the team's slot names** for the colours that play those roles, and the designer's Figma names for everything else, with the Figma variable recorded beside each (`standards.md` § Token names).

## `source/`

### File names

A view is named for what it builds as, which follows the WordPress template hierarchy except for the homepage.

| The frame is | File | Builds as |
|---|---|---|
| The homepage | `home.html` | A page set as the front page |
| A named page (About, Contact, Keynotes) | `<slug>.html` | A WordPress page with that slug |
| A generic page layout with sample prose | `page.html` | `templates/page.html` |
| A blog post | `single.html` | `templates/single.html` |
| The blog index, or an archive of the same layout | `index.html` | `templates/index.html` |
| Search results | `search.html` | `templates/search.html` |
| Not found | `404.html` | `templates/404.html` |
| A second state of a view (no results, comments closed, an open cart, an error) | `<view>--<state>.html` | Folded into its parent, never a template of its own |

Slugs are lower case with hyphens, taken from the page's name in the menu, not from the frame's name: a frame called "Bio" behind a menu link "about" is `about.html`.

A state file differs from its parent only in the region that changes.

### One stylesheet, one script

- `assets/site.css` is the only stylesheet, linked from every file. It has one `:root` block holding the tokens. Rules for a view added after the first go at the end, under a comment naming the view (`/* view: keynotes */`).
- `assets/site.js` is the only script, when there is any.
- No `<style>` block in a page, no inline `style` attribute carrying layout, no framework, no build step, no script or stylesheet from another host.

### Local fonts

The build needs the font files in the theme and has no step to fetch them, so no page loads a font from another host.

- Each font file the pages use goes in `assets/fonts/`, with the family's licence beside it (`OFL-<family>.txt`).
- For a family served by a font host, fetch that host's stylesheet with a current browser User-Agent and take the files it serves, for the latin subsets the content needs. When it serves one variable file for several weights, keep it as one file.
- One `@font-face` rule per file at the top of `site.css`, with the `font-family`, `font-style`, `font-weight` (a range for a variable file), `font-stretch`, `font-display` and `unicode-range` the host's stylesheet declared.
- A family that is not freely licensed does not go into `source/` without the user confirming the licence. Stop and ask. Until then, use the closest open family and record the substitution.

### Shared chrome

The header markup is identical, byte for byte, in every file, and so is the footer, so the build takes each as one template part. The one exception is a design that draws two headers (one over a hero, a solid one for inner pages): each is identical wherever it is used, and `views.md` names both and says which view uses which.

When a run adds pages to an existing package, the header and footer already in `source/` are the ones to use. A new frame that draws them differently is a second header or an open item, not a silent change.

### Links and content

- A link to a page that has a file points at that file (`about.html`).
- A link whose page has no file yet, or whose address the file does not hold, is `href="#"` and is listed in the content status with what it should point to.
- An external link whose address is known is the real address.
- **Nothing on a page is labelled as placeholder.** No "placeholder" text, badge or outline. The record is the content status.
- No fact is invented. A phone number, price, date or name the file does not hold is left out, not made up.
- No path in `source/` reaches outside it: no `../` leaving the folder, no `file://`, no absolute path from the machine it was made on.

## `DESIGN.md`

YAML frontmatter holding the tokens, then prose in a fixed order. The prose says what each token is for, not just its value: the build agent was not there when the design was made.

**Frontmatter keys:** `name`; `source` (the file, its export date, the hand-off page, the frames read); `modes` (the width of each frame, e.g. `desktop: 1440`, `mobile: 390`); `colors`; `pairs`; `typography` (`families`, `styles`); `spacing`; `layout`; `elevation`; `rounded`; `omitted`.

- **`colors`**: one line per palette token, keyed by its slug, which is the theme's palette slug and `--color-<slug>` in `site.css`: `canvas: { value: "#58d0fc", figma: ["Background Colors/blue"] }`. `figma` lists every Figma variable that holds the value; a colour with no variable has an empty list and a `from` saying where it was read. The slots and the naming rule are in `standards.md` § Token names.
- **`pairs`**: every pairing of a text or icon colour with the background it sits on, as the pages use them, one per line: `- [ink, canvas]`. Add `large` or `ui` as a third item where the 3:1 threshold applies. `check-package.mjs` computes each ratio. A pairing used for decoration only is left out and named in the Colors prose.
- Every other key is the Figma variable or style name, lower case with hyphens (`font-sizes-3xl`), and is the same name `site.css` uses for its custom property.
- A value that differs between frames or variable modes is written per mode: `{ desktop: 46, mobile: 32 }`.
- A value the page uses that has no variable or style in the file still goes in, under a plain name, with `style: none`.
- A section with nothing to say is listed under `omitted`, not dropped.

**Sections, in this order:** Overview; Colors; Typography; Layout; Elevation & Depth; Shapes; Components; Do's and Don'ts.

- Take the reasoning from the designer where the file gives it: annotations, the style guide's text, presentation slides. Quote it.
- Mark with *inferred* anything the file does not say and no team default covers: a breakpoint, a narrow layout with no mobile frame. Mark with *team default* anything filled from `standards.md` § Named defaults: a focus indicator, a hover with no variant, a pause control.
- Colors: say which colour took each of the four slots, and why, where two could have.
- Components: each component the pages use, its variants and states as the file draws them.
- Do's and Don'ts always carries these three: placeholder content is recorded and never labelled on the page; hover, focus and error states never change a control's size; reduced motion stops what moves.

The colour values in the frontmatter must equal the ones in `site.css`'s `:root`. If they differ, `site.css` is right, because it was checked against the exports.

## `views.md`

Sections, in this order.

1. **Concept**: two sentences on what the design is. Then, for a partial set, one line saying so.
2. **Sitemap**: one row per destination the design links to, from the menu, the footer and every call to action. Columns: label; kind (page, template view, store page, external); file, or "not converted", or "address not in the file"; slug; where the link is; the frame that designs it, with its node id, when the file has one.
3. **Views**: one row per file in `source/`: file, purpose, what it builds as, a note. Then what the set lacks.
4. **Shared chrome**: the header or headers and the footer, and which views use which.
5. **Components**: the file's components the pages use.
6. **Content status**: the record of what is not final.
   - First "On every page": what the header and footer repeat.
   - Then one entry per file, state files included, each listing the exact placeholder strings on it, each placeholder image by file name, and every `#` link with what it should point to. An entry with nothing to list says so.
   - Then what the client needs to supply.
   - Every `href="#"` in a file is in that file's entry or in "On every page". The build copies this list into its report, so a string missing here looks finished on the built site.
7. **Assumptions**: defaults taken without asking.
8. **Differences from the exports**: where a page knowingly differs from its PNG, with the size of the difference and the reason.
9. **Open items**: what needs a decision; behaviour with no frame; theme assets on the hand-off page (site icon, share image, thumbnail) with their node ids; that Figma comment threads are not in a `.fig` export, and whether the user supplied any.

## `decisions.md`

Sections, in this order.

1. **Designed views**: a short summary of `views.md`'s Views and Shared chrome, how each state file folds into its parent, and then the **content status in full**, copied, not summarised.
2. **The designer's notes**: every annotation, component description and note from the file, in the designer's words, grouped by view and section, with duplicates merged. Anything the user supplied from outside the file (comments, a brief) goes here too, marked with where it came from.
3. **Interactions**: a table of each behaviour: what it is, the note or variant it comes from, how `source/` shows it, and what the build should make of it. Include what was added without a note (reduced motion) and what was not exercised.
4. **Implied pages and templates not designed here**: first what the file designs that has no file yet, with node ids; then what a site of this kind needs that the file does not show (a blog index, a single post, search, 404).
5. **Explicit deferrals**: each thing left for the designer, the client or the build to decide, named plainly.
6. **Standards**: the result of the check against `standards.md`, under five headings.
   - *Met in the HTML*: the Development criteria, in a few lines, saying how each was checked and what was not.
   - *Fixed without changing the look*: a table of what the file draws and what was done.
   - *For the designer*: a table of each Design criterion the design fails and `source/` reproduces: what, the measured value, the standard.
   - *Is the design complete?*: the hand-off checklist as a table, with what this file holds for each row, by node id where it has one.
   - *Team defaults used*: what was filled from a named default.
7. **Feedback applied**: changes made after a review, so the build does not "correct" them back. "None" on a first conversion.

## `annotations.md`

The log of what the designer wrote on the frames. `scripts/fig.mjs annotations <out>/extract --out <out>/handoff/annotations.md` writes it from each extract's `notes.json`. It is never written or edited by hand, and it is written again whenever a frame is extracted.

Sections, in this order.

1. **Annotations**: each annotation once, numbered, with its text in a fenced block exactly as written, its category and pinned properties when it has them, and under "On" every frame it is on (name, node id, size) with the layers. The same note on several frames or layers is one entry.
2. **Note layers inside the design**: layers the designer used as notes, which are not built. Left out when there are none.
3. **Component and style descriptions**: what is written in a component's or a style's description field. Left out when there are none.
4. **Frames read**: one row per folder in `extract/`, with the frame's node id, page, size and how many annotations are on it. A frame with none is still listed, so a reader can tell "no notes" from "not read".

It holds only what is in the file. Notes from outside it (Figma comments, a brief) go in `decisions.md` § The designer's notes, marked with where they came from. Text the designer placed on the page around a frame stays in that frame's `notes.md`.

How it sits with `decisions.md`: § The designer's notes there groups the notes by view and § Interactions says what was done with each. `annotations.md` is the complete record. A note in the log for a frame that has no file in `source/` belongs to a page still to come.

## Check the package

`scripts/check-package.mjs <out>/handoff` runs the checks marked ✓ below and exits non-zero when one fails. The rest need a browser. Read each result; assume none.

- Every `.html` file in `source/` loads over loopback HTTP with no request failing and no console error.
- ✓ Nothing is loaded from another host: no font host, script host or image host in any `href`, `src`, `@import` or `url()`.
- ✓ No path reaches outside `source/`.
- ✓ Every file an `.html` or `site.css` refers to exists, and nothing in `assets/` is unused.
- ✓ Every `@font-face` file is in `assets/fonts/` with a licence beside it.
- ✓ Every file in `source/` is named in `views.md`, and every file `views.md` names exists.
- ✓ Every internal link resolves to a file, or is `#`. The checker prints the number of `#` links per file: match it against that file's content status entry plus "On every page".
- ✓ The header is byte-identical in every file that uses it, and so is the footer.
- ✓ `DESIGN.md`'s colours equal `--color-<slug>` in `site.css`, and every pairing under `pairs` reaches its contrast.
- ✓ `decisions.md` has its content status, designer's notes and Standards sections.
- ✓ `annotations.md` exists, lists every frame in `extract/`, and holds the text of every annotation found in them.
- ✓ Nothing visible on any page says "placeholder".
- ✓ The type-rendering baseline, a reduced-motion rule and a focus style are in `site.css`, and it never uses the `text-wrap` shorthand.
- ✓ No palette slug is `border`, `text` or `link`.
- ✓ Each page has one `h1`, no skipped heading level, its landmarks, a skip link, `lang`, a viewport that allows zoom, alt text and labelled fields.
- `page-audit.js` returns no sideways scroll at any width, and every small target, small text and tight line it lists is fixed or recorded for the designer.
- Everything that moves can be paused, by keyboard and by touch.
- `decisions.md` carries the content status in full, not summarised.

Then say what the next step is: run html-to-block-theme 0.10.0 or later on `<out>/handoff/source/`. It reads the three documents from `<out>/handoff/`, the folder above `source/`.
