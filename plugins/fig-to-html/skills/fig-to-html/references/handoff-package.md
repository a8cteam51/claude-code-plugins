# The handoff package

What fig-to-html writes, file by file. It is the same package `sp-site-design-harness` writes with `/prep-handoff`, so that html-to-block-theme reads either without knowing which made it: three documents, and beside them a `source/` folder of plain HTML.

```text
<out>/
  handoff/
    DESIGN.md      rules, tokens, reasoning
    decisions.md   what the build must do that the HTML does not show
    views.md       sitemap, each view, what it builds as, content status
    source/        the pages as HTML, one stylesheet, local fonts, assets
  extract/         what the reader wrote, per frame; beside the package, not in it
```

`handoff/` is the package. Paths below are inside it.

Where the two packages differ, and why:

- **This one can be partial.** The harness designs every view of a site. fig-to-html converts the frames it was given and designs nothing the file lacks. `views.md` says which destinations have no file yet, and the next run adds to the same package.
- **Its authority is the designer's file.** The harness fills a gap from team standards. Here a gap is recorded as inferred or as an open item, never filled by taste.
- **Its token names are the Figma variable names.** The build maps them to the theme's slugs.

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

**Frontmatter keys:** `name`; `source` (the file, its export date, the hand-off page, the frames read); `modes` (the width of each frame, e.g. `desktop: 1440`, `mobile: 390`); `colors`; `typography` (`families`, `styles`); `spacing`; `layout`; `elevation`; `rounded`; `omitted`.

- A key is the Figma variable or style name, lower case with hyphens (`background-colors-blue`), and is the same name `site.css` uses for its custom property.
- A value that differs between frames or variable modes is written per mode: `{ desktop: 46, mobile: 32 }`.
- A value the page uses that has no variable or style in the file still goes in, under a plain name, with `style: none`.
- A section with nothing to say is listed under `omitted`, not dropped.

**Sections, in this order:** Overview; Colors; Typography; Layout; Elevation & Depth; Shapes; Components; Do's and Don'ts.

- Take the reasoning from the designer where the file gives it: annotations, the style guide's text, presentation slides. Quote it.
- Mark with *inferred* anything the file does not say: a breakpoint, a hover with no variant, a narrow layout with no mobile frame.
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
6. **Feedback applied**: changes made after a review, so the build does not "correct" them back. "None" on a first conversion.

## Check the package

Read each result; assume none.

- Every `.html` file in `source/` loads over loopback HTTP with no request failing and no console error.
- No request leaves loopback. No font host, script host or image host appears in any `href`, `src`, `@import` or `url()`.
- No path reaches outside `source/`.
- Every file an `.html` or `site.css` refers to exists, and nothing in `assets/` is unused.
- Every `@font-face` file exists in `assets/fonts/` with its licence beside it.
- Every file in `source/` has a row in `views.md`'s Views, and every row's file exists.
- Every internal link resolves to a file, or is `#` and listed. Count the `href="#"` in each file and match the count against its entry plus "On every page".
- The header is byte-identical in every file that uses it, and so is the footer.
- `DESIGN.md`'s colours equal `site.css`'s `:root`.
- `decisions.md` carries the content status in full.
- Nothing visible on any page says "placeholder".

Then say what the next step is: run html-to-block-theme 0.10.0 or later on `<out>/handoff/source/`. It reads the three documents from `<out>/handoff/`, the folder above `source/`.
