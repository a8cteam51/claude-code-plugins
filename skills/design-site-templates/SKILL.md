---
name: design-site-templates
description: Design the rest of a website from one approved homepage — blog index, single post with comments, page, search results and 404 — as static HTML in the homepage's exact design language, ready for review and for html-to-block-theme to build into a WordPress block theme. Use when a homepage design is settled and the site's other views need designing ("design the other templates", "extend this homepage to a full site", "make the blog and post pages"). Works on any homepage HTML; DESIGN.md, a tokens file and a brief sharpen it when present. Inside sp-site-design-harness, /prep-handoff runs this for you.
argument-hint: "<homepage.html> [output folder]"
---

# Design site templates

Takes one approved homepage and designs the site's other views in its
language. The direction is already decided, so this is not exploration: no
seeds, no risk ladder, no new concepts. The job is translation. Every view
should read as the same site, designed by the same hand, at the same level
of care.

This skill works on its own. Anything specific to a project is an input
it's given, never an assumption about where it's running.

## Inputs

**Required**
- `homepage`: one HTML file. Its `:root` and CSS are the authoritative
  values.
- `out`: the folder to write the set into. If not given, use a `site/`
  folder next to the homepage and say so. Never write into the homepage's
  own folder, and never edit the homepage file itself.

**Optional, read when present**
- `DESIGN.md`: the rules, the reasoning, the do's and don'ts, the
  components. When it's there, design **from it**. The homepage shows the
  rules applied once; DESIGN.md says what they are.
- The homepage's `.tokens.md`: rationale for type, color and spacing roles.
- A brief (`research/brief.md` or similar): the real site structure (IA),
  the voice, the content, whether there's a blog and comments, tools that
  affect forms.
- A change log (`*.changes.md`): partner decisions. Don't undo any of them.
- `notes`: where to write the views notes. Default `<out>/views.md`.

## Step 0 — Settle the facts (one batched question at most)

You need these facts. Take each from the inputs if it's there, otherwise
use the default. Ask **once**, in a single batched message, only for the
facts you can't find and whose default would be wrong to assume:

| Fact | Default |
|---|---|
| Site name | The homepage's wordmark/`<title>` |
| Real main nav: labels and what each is | The homepage's nav labels, if they're real pages and not `#anchors`. Anchor-only nav has no default: ask. |
| Blog name (what the index is called) | "Journal" or the homepage's posts section heading |
| Comments on posts | On |
| Search | On |

If the user doesn't answer, go with the defaults and list them in the notes
as assumptions.

## Step 1 — Read the system

1. Read the homepage completely: `:root`, every CSS rule, the markup.
2. Read DESIGN.md, `.tokens.md`, the brief and any change log if given.
3. Write the concept down in one sentence (from DESIGN.md's Overview, or the
   tokens file's opening, or your reading of the homepage). Then write one
   sentence on how it should behave on reading-focused views, where the
   homepage's composition moves would get in the way of content. For example: a
   concept built on bold color fields might carry over as section bands and
   dividers rather than a full composition per screen. Both sentences go at
   the top of the notes.

## Step 2 — Inventory before inventing

List what the homepage already gives you, in the notes, under "Inventory":
header, footer, nav (desktop and mobile), buttons and their states, link
styles, the post card or list item if there is one, heading treatments,
small-text/meta style, form fields, section spacing, content measure,
image treatments, dividers, icons.

Every view is assembled from the inventory first. When a view needs
something the homepage doesn't have (pagination, a comment, a table, an
error message), derive it from the nearest inventory item and DESIGN.md's
rules, and record it under "New components" with one line on what it was
derived from. A new component with no ancestor in the inventory is a
warning sign: rethink it before you build it.

## Step 3 — Shared foundation

Do this once, before any view. If DESIGN.md is still being written (inside
the harness it can run in parallel), this step is the only work that's safe
to start: it moves the homepage, it doesn't design anything. Don't write
view CSS until DESIGN.md exists, or you'll design from the homepage alone
and redo it when the rules arrive.

1. **Copy, don't edit.** Copy the homepage to `<out>/home.html`.
2. **Assets.** Copy every local image, font and script the homepage uses into
   `<out>/assets/` and rewrite the paths **in the copy** so everything
   resolves inside `<out>` (no `../` escaping it). Remote font CDN links stay
   as they are for now. Give images descriptive, space-free names, but
   **look at each image before naming it or writing its alt text**: source
   filenames lie (an "Office-Pic" can be a statue).
3. **One stylesheet.** Move the homepage's `<style>` content into
   `<out>/assets/site.css`, unchanged and in order, and link it from
   `home.html`. All views link the same file. Rules for other views are
   added to the end of `site.css` under a comment per view
   (`/* view: single */`). This gives the set one `:root`, so a token change
   is one edit, never six.
4. **Verify the move changed nothing.** Serve `<out>` and the original
   homepage's folder over loopback HTTP (see "Browser checks"), load both at
   1440 and 375, and compare page height and the bounding boxes of each
   top-level section. Any difference over 1px means the move broke
   something: find out why before going on.
5. **Real nav.** Replace anchor-only nav items with the real IA from Step 0,
   linking per `references/view-specs.md` § Everywhere. If the homepage's
   nav was already real, leave it alone.
6. **Shared chrome is byte-identical.** The header and footer markup must be
   identical in every view so a builder extracts each one as a single
   template part. The one allowed exception: if the homepage header sits
   over a hero (transparent, inverted, absolutely positioned), inner views
   need a solid header. Design it once as a second header, identical across
   all inner views, and name both headers in the notes.

## Step 4 — Design the views

Read `references/view-specs.md` and build each view in the order it gives,
writing into `<out>`. For each view:

- Start from `home.html`'s skeleton (head, header, footer), so chrome stays
  identical. Change only `<title>`, the `<meta name="description">`, and
  `main`. The reliable way is a small builder script in your scratchpad
  (not in `<out>`) that slices the chrome out of `home.html` and writes each
  view around its own `main`. Identical chrome is then automatic, a chrome
  change is one rebuild, and the check in Step 5 is a string compare.
- **Watch for homepage selectors leaking into new markup.** Most bugs in the
  first test run came from this: a descendant rule like `.main-nav a`
  overriding a button inside the nav, a prose `ol` rule indenting a comment
  list, a `margin` shorthand wiping out a column offset. Before adding a
  component, check which existing rules will also match it. Set only the
  sides you mean (`margin-block`, not `margin`) on anything that inherits a
  layout offset.
- Use the inventory and `site.css`. Write new CSS only for what's new, using
  only role tokens from `:root` (no hex or raw values outside `:root`, same
  rule as the homepage). If a new value is genuinely needed (say, a
  comment-thread indent), add it to `:root` as a token first.
- Use the homepage's breakpoints. Don't add new ones unless a view truly
  needs one, and say why.
- Write sample content per view-specs § Everywhere.
- Apply DESIGN.md's accessibility-gate fixes in the HTML itself, in every
  view and the homepage copy (DOM order, heading levels, link text), not
  just in the notes. A fix that only lives in prose becomes a build-time
  exception the builder has to remember.
- Add one line per view to the notes: how the concept shows up there.

`../create-design/references/craft-corrections.md` applies to every view
(if this skill runs outside the harness and the file isn't there, skip it).
Read it before the first view.

## Step 5 — Check the set

**Per view**, in the browser at 375×812 and 1440×900 (plus any homepage
breakpoint between them):
- No horizontal scroll, no clipped text, no overlaps.
- No console errors, no same-origin request that fails (check network
  requests; a missing stylesheet renders a plain page that a screenshot can
  mistake for a design choice).
- Every relative link in the view resolves to a file in `<out>`.
- The accessibility pass in `../create-design/references/polish.md` § 3,
  with contrast checked numerically for any new color pairing.
- Headings, landmarks and form labels per view-specs § Everywhere.

**Then one critic pass across the set.** Spawn one subagent with no
knowledge of how the views were made (same isolation rule as
`../create-design/references/critique.md`). Give it screenshots of
`home.html` and every view at 1440 and 375, scaled to about 800px wide (it
reads every image; 18 full-size captures took 43 minutes), and state files
only where they differ from their parent. Give it the concept sentence, the
rules from DESIGN.md that are fixed (so it doesn't re-argue settled
decisions as findings), and the critic prompt from critique.md with one
question added before scoring:

> 8. Do these read as one site designed by one hand? Name any view, or any
>    element on a view, that looks like it came from a different system:
>    different spacing logic, type treatment, component style, or level of
>    craft.

Fix what it finds, then re-check the views you changed. A finding that
contradicts DESIGN.md or the approved homepage isn't yours to act on: record
it in the notes under Open items as a decision for the user. Two critic
rounds at most. After that, record what's left in the notes rather than
looping.

## Browser checks

Serve the folder: `python3 -m http.server <port> --bind 127.0.0.1 --directory <out>`
(in the background) and open `http://127.0.0.1:<port>/<file>`. `file://`
hides failed requests and can't be resized. Use explicit viewport sizes, and
reset to the desktop preset and stop the server when done.

Measure rather than eyeball where you can: load each view in a hidden
`iframe` of the target width and read `scrollWidth`, image `naturalWidth`,
heading levels, unlabelled fields, text below the minimum size and small
targets. Run one width per call; a hidden browser pane is slow.

**Full-page captures for the critic.** Headless Chrome
(`--headless=new --screenshot --window-size=W,H`) works at desktop widths
but won't make a window narrower than about 500px, so a "375" capture is
really a wider layout cropped. For phone captures, write a wrapper page
holding the view in a 375px-wide `iframe` (served from a second port),
capture the wrapper, and crop to 375. Check one capture by eye before
trusting the rest. Reload with `fetch(url, {cache: 'reload'})` after CSS
edits; the pane caches stylesheets.

## Output

```
<out>/
  home.html  page.html  single.html  index.html  search.html  404.html
  single--no-comments.html  single--comments-closed.html  search--no-results.html
  assets/site.css  assets/…        images and any local fonts or scripts
<notes>  (default <out>/views.md)
```

The notes file has these sections, in order:

1. **Concept**: the two sentences from Step 1.
2. **Views**: a table with file, purpose, how it builds (from view-specs),
   and the one-line concept note.
3. **Shared chrome**: the header(s) and footer, and which views use which.
4. **Inventory** and **New components** (Step 2).
5. **Content status**: every piece of sample content is placeholder; list
   what the client needs to supply (post content, author names, images).
6. **Assumptions**: defaults used in Step 0 without confirmation.
7. **Fixes to the homepage**: anything changed in `home.html` beyond the
   stylesheet move and asset paths (real nav, a skip link), and why.
8. **Open items**: critic findings not resolved, anything that needs a
   decision.

## Report

A few lines: the views written, the critic's final score and any open
items, assumptions made, and the serve command to look at the set. Don't
publish anything. Sharing is the caller's decision.
