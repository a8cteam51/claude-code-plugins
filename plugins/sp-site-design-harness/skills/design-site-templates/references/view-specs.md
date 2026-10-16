# View specs

What each view must show. Filenames follow the WordPress template hierarchy
so html-to-block-theme (or any builder) classifies them without guessing.
The "Builds as" column is a hint for the builder, not markup to write: the
HTML stays plain, semantic HTML.

Every view shares the homepage's `assets/site.css`, header and footer (see
SKILL.md Step 3) and uses the same breakpoints.

## The set

| File | Purpose | Builds as |
|---|---|---|
| `home.html` | The chosen homepage, unchanged except for the shared stylesheet, asset paths and real nav | A page set as the front page |
| `page.html` | Generic page: title + prose | `templates/page.html`, content in `core/post-content` |
| `single.html` | Blog post with comments | `templates/single.html` |
| `index.html` | Blog index; the same layout serves archives, categories and tags | `templates/index.html` with `core/query` + `core/post-template` |
| `search.html` | Search results | `templates/search.html` |
| `404.html` | Not found | `templates/404.html` |

**State files** show a second state of a view. They're named
`<view>--<state>.html`, differ from the parent only in the region named, and
fold into the parent template at build time (they never become templates of
their own):

| File | State | Builds as |
|---|---|---|
| `single--no-comments.html` | No comments yet; the form shows a validation error after an empty submit | The parent's comments region with zero comments |
| `single--comments-closed.html` | Existing comments, no form, a closed notice | The parent's comments region with comments closed |
| `search--no-results.html` | No results: message, the search form again, a way onward | `core/query-no-results` inside the parent's query |

Design the order: `page` → `single` → `index` → `search` → `404`, then the
state files. Page builds the prose system that single reuses; single builds
the post meta and card language that index and search reuse.

## Prose system (page and single)

This is how editor content looks, so it carries most of the site's real
reading. Show every element below inside the content column, with sample text
that reads like the client's actual content:

- `h2`, `h3`, `h4`, each followed by a paragraph so the spacing above and
  below is visible
- paragraphs with an inline link, `strong`, `em`, and inline `code` only if
  the brief suggests technical content
- an unordered list with one nested level; an ordered list
- a `blockquote` with a `cite`
- an image with a `figcaption`
- one wide-aligned image (`alignwide`) and, if the homepage uses full-bleed
  bands, one full-width element (`alignfull`). These show the builder the
  content, wide and full widths (theme.json `contentSize` / `wideSize`).
- a simple table (3 columns, 3–4 rows) with a header row
- a separator (`hr`)
- a button using the homepage's button treatment

Measure: body text column 60–75 characters, unless DESIGN.md says otherwise.
Link styling in prose must be distinguishable without color alone.

## page.html

- Page title as the only `h1`. An optional lede paragraph if the homepage has
  a lede style.
- The full prose system above.
- No post meta, no comments, no featured image unless the homepage's
  language calls for a page hero (if so, a restrained version, and say why in
  the notes).

## single.html

- Header: `h1` title, post meta (date, author, category, comment count),
  featured image. The meta's order and separators come from the homepage's
  small-text treatment if it has one.
- The prose system (can be shorter than page's, but every element appears in
  at least one of page/single).
- After content: tags, and previous/next post links.
- **Comments**
  - Heading with the count ("3 comments on …" or the brand's voice).
  - Threaded list: at least three comments, one of them a nested reply. Each
    shows author, date as a link, text, and a reply link. Distinguish the
    post author's comment if the design has room for it.
  - The form: comment textarea, name, email, website (optional), a submit
    button. Every field has a visible `label`. Hover and focus states that
    don't shift layout (no border-width change on focus; use outline or
    box-shadow, or a border that's already there).
  - Required fields are marked in text, not by color alone.
- State files:
  - `single--no-comments.html`: no list; a heading that invites the first
    comment; the form after an empty submit, showing an error summary at the
    top of the form and an inline message on each failed field, linked by
    `aria-describedby`, and `aria-invalid="true"` on the field.
  - `single--comments-closed.html`: the list as in `single.html`, then a
    short closed notice in place of the form.

## index.html

- A heading for the blog ("Journal", or whatever the IA calls it), styled so
  the same slot can later hold an archive title with a short description.
  Record that in the notes.
- At least six posts, so the grid or list rhythm is visible. Each item:
  title as the link (never a separate generic "Read more" as the only link),
  date, category, excerpt, featured image if the homepage's post treatment
  uses one. If the homepage has a post/journal section, reuse its card.
  If not, derive one from the homepage's components and say so in the notes.
- Pagination: previous/next plus page numbers, with the current page
  marked with `aria-current="page"`.
- If plot types vary by position (a colour tile every third item, say),
  every item still has the same markup, since a query loop repeats one
  template. Position sets the look through CSS, and reading order must equal
  DOM order. When a plot type depends on content (a no-image tile), say in
  the notes what the build does when a post doesn't match: hide the image,
  or fall back to another plot type.

## search.html

- `h1` that echoes the query: "Results for 'acupuncture'" with a count.
- The search form again, prefilled with the query, with a visible label (or
  a visually hidden one if the design has a clear icon button, and the button
  has an accessible name).
- Results: a compact version of the index item (title, type or date,
  excerpt). Show at least four, mixing posts and pages if the site has both.
- Pagination as in index.
- `search--no-results.html`: a plain message, the form, and one way onward
  (popular posts, the blog index, or the main nav sections).

## 404.html

- `h1` in the brand's voice, one or two sentences, the search form, and links
  to the key sections from the real IA.
- This is the one view allowed a little of the homepage's expressive moves
  (a display treatment, an illustration already in the asset set), because
  it's short and seldom seen. Keep it inside the design language.

## Everywhere

- One `h1` per view; heading levels never skip.
- Landmarks: `header`, `nav` (with an `aria-label` when there's more than
  one), `main`, `footer`, and `search` (or `role="search"`) around search
  forms.
- Skip link if the homepage has one (and add one if it doesn't; it's an
  accessibility fix, log it in the notes).
- Sample content is realistic for this client: real-sounding post titles,
  plausible dates, excerpts in the brand's voice. No lorem ipsum. No visible
  "placeholder" labels. All sample content is recorded as placeholder in the
  notes' content status, never marked in the HTML.
- Images: reuse the homepage's images or the project's supplied images
  before generating anything. Informative images get real `alt`; decorative
  ones get `alt=""`.
- Links between views are relative and work: nav → views, post titles →
  `single.html`, search forms → `search.html` (`action="search.html"`),
  pagination → `index.html`, footer links where they apply. Nav items for
  pages that aren't designed (About, FAQ, Contact) point at `page.html`.
