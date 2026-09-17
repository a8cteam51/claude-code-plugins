---
name: vibe
description: Build and edit pages and posts on a connected WordPress site by writing a single full-width Custom HTML block (markup, CSS, and JS) through the site's REST API, then checking the result in the browser. Use when the user asks to "build a landing page on my site", "add a page to my website", "make me a page for my event", "write a post about", "change the photo/text/colors on my page", "undo that change to my page", "vibe a page", "update the hero on <page>", or any request to create or change page or post content on their WordPress site. Not for editing existing block-editor layouts — this skill owns pages it built as one HTML block.
---

# Build pages and posts

You write one Custom HTML block per page or post and send it to the site with `scripts/wp.sh`. WordPress stores it as a normal page on one of two page templates (with the site header and footer, or blank), and the site owner can click text and images in wp-admin to tweak them later.

All site access goes through the script:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/wp.sh" <command> SITE ...
```

`SITE` is the host or any unique part of the address as listed by `wp.sh sites`. The script needs only bash and curl, reads the saved credentials itself, and sends content as a file, so you never handle the password or escape anything.

## Preflight

1. `wp.sh sites`. **No sites** → do not build anything. Tell the user "your site isn't connected yet — let's set that up first", invoke the `ai-canvas:setup` skill with the Skill tool, and come back here only after it reports `missing: none`. Nothing in memory or earlier conversation counts as a connection; only a saved site listed by this command does. **Several sites** and the user has not named one → ask which. **One site** → confirm it is the site the user means (say its address) before the first write, since a saved test site is easy to mistake for the real one.
2. On the first request of a session, `wp.sh me SITE` to confirm the connection still works. A rejected-credentials error means the Application Password was revoked or changed; route to setup.
3. If the browser tools (`mcp__claude-in-chrome__*`) are available, plan to verify in the browser (below). Otherwise you will verify with `wp.sh check`, and say so when reporting.

## The block

Every page or post body is exactly this shape, saved to a file and sent with `--content-file`:

```html
<!-- wp:html {"align":"full"} -->
<style data-wp-block-html="css">
/* all CSS, every selector prefixed with the root class */
/* JS-driven states (hidden until revealed, inactive tab panels) only under .is-js */
</style>

<script data-wp-block-html="js">
/* all JS: one IIFE that waits for the DOM, then queries from the root element */
(function () {
  function init() {
    var root = document.querySelector('.canvas-spring-launch');
    if (!root) return;
    root.classList.add('is-js');
    /* behaviour here */
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
</script>

<div class="canvas-spring-launch">
  <!-- markup -->
</div>
<!-- /wp:html -->
```

- `{"align":"full"}` makes the block span the full screen width. The site's visual HTML editor plugin turns it into the theme's full-width wrapper on the front end; without that plugin the page still works but sits inside the theme's content column.
- **It is a fragment, not a document.** No `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`, `<title>`, meta tags, or external `<link>`/`<script>` references. The theme supplies all of that.
- **One root element with a distinctive class**, and every CSS selector prefixed with it. Never style `body`, `html`, `:root`, or bare element selectors; that restyles the theme's header and footer and reads as a broken site. If the design fights the theme's content width, work inside the root instead of overriding theme layout classes.
- **JS runs same-origin and unsandboxed.** Keep it self-contained: DOM behavior, animation, small interactions. Never call authenticated site endpoints, embed third-party scripts, or send data anywhere. Wrap it in an IIFE and query from the root element so two blocks on one site cannot collide.
- **The script runs before the markup exists.** It sits above the root element in the block and WordPress prints it in place, so a top-level `querySelector` for the root returns null and the script silently does nothing: no console error, widgets that never respond. Keep the shape above: do the work in an `init` function that runs on `DOMContentLoaded`, or at once if the document has already loaded.
- **The script never runs in wp-admin's editor.** The visual HTML editor plugin renders the block in the "Edit content" view by injecting its markup, and injected `<script>` tags do not execute. So the page must be complete and readable with no JS at all: the CSS default state is fully visible, every section stacked in order. The script's first act is `root.classList.add('is-js')`, and every state that only JS can leave (`opacity: 0` awaiting a scroll reveal, hidden tab panels, one slide of a carousel, a fixed-height stage) is written under `.canvas-x.is-js …`. Without the class the editor shows everything, the owner can click any text to edit it, and visitors with JS blocked still get the page. `opacity: 0` on a plain root-prefixed selector is the classic mistake: the front end looks fine and the editor shows blank space where the sections should be.
- **Telling the editor from the front end.** There is no global to test: inside the editor iframe `window.wp`, `pagenow`, and `typenow` are undefined (they belong to the wp-admin parent document), and on the front end none of them exist either. The reliable signal is the DOM. WordPress wraps editor content in `.editor-styles-wrapper` (the iframe's `<body>` on block themes, a wrapper `<div>` otherwise) and names the iframe `editor-canvas`. For anything that should differ in the editor even when the no-JS default is right (a `100vh` hero, sticky or fixed positioning, autoplaying video, a full-screen overlay), write `.editor-styles-wrapper .canvas-x …` in CSS; in JS, if a future version of the plugin ever runs the script there, `root.closest('.editor-styles-wrapper')` is the check. Never gate the whole script on it; the front end must stay fully interactive.
- **Never write a bare `<` in the script, the style, or the text.** WordPress runs page content through `wptexturize` when it serves it; the stored content is untouched, so `wp.sh get` shows nothing wrong. That filter skips text inside `<script>` and `<style>`, but any `<` (`i < 10` in JS, `5 < 6` in a paragraph) is taken as the start of a tag running to the next `>`, however many lines later, and every `&` in that span becomes `&#038;`. `a && b` turns into `a &#038;&#038; b`, a syntax error that kills the whole script. Flip comparisons (`10 > i`, `n >= i`), use `!==` for loop bounds, keep `<` out of string literals, and write `&lt;` in text. A `>` on its own (`=>`, `.a > .b`) is harmless. `wp.sh check` reports `script_ampersand_rewritten: yes` when it has happened.
- **Restate what the theme styles on elements.** Block themes style `h1`–`h6`, `a`, `button`, and often `p` directly (font family, color, text-transform, letter-spacing), and an element rule beats anything the root class only passes down by inheritance. Set font-family, color, and text-transform explicitly on headings, links, and buttons with prefixed selectors, or the theme's display font and heading color leak into the page (white headings on a light section is the usual symptom).
- **Editable by humans.** Keep text in ordinary headings, paragraphs, list items, links, and buttons, and images as plain `<img>` tags with `src` and `alt`; that is what the site owner can click to edit later. Text assembled by JS or hidden in attributes is not editable. Hero backgrounds: set `background-image` inline on the element and add `data-vc-bg` so the owner can swap the photo.
- **Posts** get the same block. The theme shows the post title, date, and author around it, so keep a post's root narrower in spirit: readable column, less full-bleed decoration.
- **Pages show no title** on either AI Canvas template, so the block's first section must carry the page's heading.

## Workflow

1. **Find or create.** `wp.sh find SITE --type page --search "spring"` before creating anything the user may already have. `wp.sh create SITE --type page --title "…" --content-file page.html --template ai-canvas-framed` returns the id, public link, and wp-admin edit link, and records the first version as a revision. See "Choose the template" for `--template`.
2. **Read before you write.** `wp.sh get SITE ID --out current.html` before every update; the owner or another session may have edited it since you last looked. `update` replaces the whole block, so always send complete content.
3. **Update** with `wp.sh update SITE ID --content-file page.html`. WordPress records the new content as a revision, so the history is on the site, visible to the owner under Revisions in wp-admin.
4. **Undo.** `wp.sh revisions SITE ID` lists revisions newest first; the newest normally matches the current content, so "undo that" is `wp.sh restore SITE ID --revision <the one below it>`. Restoring records another revision, so a restore can itself be undone. For several steps back, pick the older revision. A page built by someone else in wp-admin also has revisions, so this works on pages this skill did not create.
5. **Images.** `wp.sh media SITE --search logo` to reuse what is already in the Media Library; `wp.sh upload SITE file.jpg --title "…" --alt "…"` for new files. Both return the image's dimensions and generated sizes; reference the URL of the right size verbatim, never a guessed path.
6. **Publish state.** Pages publish immediately by default; they are unlinked from menus, so visitors only reach them by address. For **posts**, ask once whether to publish now or save as a draft (`--status draft`), because publishing a post notifies subscribers and appears on the home page. Drafts cannot be checked with `wp.sh check` or a logged-out browser; verify them after publishing, or with the wp-admin preview if the user's browser is logged in.
7. **Verify** before reporting (next two sections). A successful `create` proves the content saved, not that the page works.
8. **Remove** with `wp.sh trash SITE ID` when asked; it goes to the Trash in wp-admin, where the owner can restore it.

## Choose the template (pages)

Setup creates two page templates on the site. Pick one for every new page; existing pages keep whatever they have unless the user asks.

- `--template ai-canvas-framed`: the site's own header and footer around the block, no page title. The default: a page that belongs to the site.
- `--template ai-canvas-blank`: nothing but the block. For a standalone landing page, a campaign page with its own navigation, or anything that should not look like the rest of the site.

Decide from the brief ("landing page", "standalone", "no menu", "just the page" → blank; otherwise framed). If it is a coin toss, ask in plain words: "Should this page have your site's usual header and footer, or stand on its own?" Never mention template names to the user.

If `create` fails with an invalid template error, the templates are missing: run `wp.sh template-ensure SITE` once and retry. Posts do not take these templates; the theme's single-post layout applies.

## Verify: script check

`wp.sh check SITE ID` fetches the public page and reports:

- `public` false → the page is a draft or private, or the site returned an error.
- `alignfull_wrapper` false → the visual HTML editor plugin is not active, or the theme is classic. The page still works; tell the user once and point them at setup step A2 if they want full width.
- `script_was_escaped` true → the connection user cannot publish scripts (no `unfiltered_html`). Interactivity is stripped; route to setup B2.
- `style_tag_present` / `script_tag_present` false when you sent them → something on the site is filtering content; report it.
- `script_ampersand_rewritten` true → a bare `<` somewhere in the block made WordPress rewrite `&` inside the script (see "The block"). Remove the `<`, update, re-check.

## Verify: check your own work in the browser

When `mcp__claude-in-chrome__*` tools are available, review every meaningful change as a visitor would.

- Invoke the `claude-in-chrome` skill before first use if it is listed. If the tools are deferred, load them in **one** `ToolSearch` call: `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `computer`, `read_page`, `read_console_messages`, plus `resize_window` for responsive checks.
- Call `tabs_context_mcp` once, open the page's link in a new tab, and reuse that tab: reload after each `update`.
- Screenshot and actually look. The content sits between the theme header and footer, your styles are applied, and the header and footer look untouched. A changed site header means a scoping violation, not a theme quirk.
- If the block has JS, exercise it (click the tabs, open the accordion, advance the slides) and read the console for errors. A widget that renders can still be one that never toggles.
- Resize to phone width for at least one check on layout-heavy pages: look for horizontal overflow and pixel-positioned decoration overlapping content.
- Check accessibility once per page and again after any change to colors, structure, or widgets (rules in "Build accessible pages"). Tab through the page from the top: every link and control is reached in reading order, the focus ring is visible on each one, including on dark sections, and every widget works with Enter, Space, and Escape. Read the page's accessibility tree with `read_page`: one `<h1>`, heading levels without gaps, every image and icon-only control named, no second `main`. Look at the phone-width screenshot for targets that are too small or too close together. If the session offers an automated audit (Lighthouse, axe), run its accessibility category and clear every error; it catches contrast and missing names, not reading order, link text, or motion, so it never replaces the pass above.
- Once per page with JS-driven states, open the wp-admin edit link too (the user's browser is normally logged in). Every section must be visible in the "Edit content" view with no JS running; blank space where a section belongs means a state was not gated on `.is-js`. Skip the editor check when the browser is not logged in, and say so.
- Fix → `update` → reload → re-screenshot. Stop when the screenshot matches what the user asked for, and report what you verified.

Without the browser tools, `wp.sh check` is the verification; say that it confirms the page is served correctly rather than how it looks, and that keyboard use and focus visibility were not tested. Contrast, headings, alt text, and link text can still be checked from the source; do that.

## Keep pages fast

Apply on the first write, not as an afterthought:

- **Right-size images.** `media` and `upload` return generated sizes; reference the smallest that covers the display area. A full-size photo in a 600px column is the most common way these pages balloon.
- **Explicit `width` and `height`** on every `<img>`, matching the size referenced, so layout does not shift as images load.
- **Lazy-load below the fold only.** `loading="lazy" decoding="async"` below the fold; the hero image stays eager with `fetchpriority="high"`.
- **Video is opt-in.** `preload="none"`, `muted playsinline` for ambient video, started and paused by an IntersectionObserver.
- **No frameworks, no client-side templating.** The markup in the block is what renders. Never read layout in a scroll handler; use IntersectionObserver for reveals and sticky states.
- **No data-URI images.** Put them in the Media Library.

## Build accessible pages

The target is WCAG 2.1 Level AA on every page, applied on the first write. You pick the palette, the type, and the markup in one pass, so there is no later design review to catch a miss. Go stricter (AAA: 7:1 text contrast, no text under 16px) only when the user asks or the audience calls for it, and say that you did.

**Color and contrast**

- **Check every pairing you choose** before writing it: 4.5:1 for normal text, 3:1 for large text (24px and up, or 18.66px and up when bold), 3:1 for UI boundaries against what they sit on (button and field borders, icons, focus rings). Run `wp.sh contrast FG BG [FG BG ...]` with the whole palette in one call (hex colors, no site argument) and fix every `FAIL` that applies to how the pair is used; never eyeball it. Flatten a transparent color onto its background first. Light-weight large text gets the 4.5:1 rule.
- **Never color alone**, for information or for state. Hover, focus, current, visited, and error each pair the color change with a second cue: underline, border, icon, or a contrast-checked background. Inline links in running text stay underlined. Not bold on `:hover`; it changes the text's width and reflows the line.
- **Text over a photo** only with a solid or gradient scrim behind it that holds the ratio across the whole image, since the owner can swap the photo (`data-vc-bg`) for a lighter one.

**Type**

- Body text 16px or larger, nothing anywhere at 12px or under, `line-height` 1.5 or more on body copy, paragraph spacing at least the font size twice over, text blocks held to about 50–80 characters (`max-width: 65ch`).
- No `text-align: justify`. Uppercase only on short UI labels, set with `text-transform` so the stored text stays in normal case. Never text baked into an image, logos aside.
- Plain, legible faces for body and UI text; display faces for headings only. The block takes no external references, so stay on the theme's fonts or a system stack, and use only the weights and italics that face really has: the browser fakes a missing one. When unsure, set `font-synthesis: none` on the root during the browser check and see whether the bold or italic survives.

**Structure**

- **One `<h1>` per page**, and it lives in the block because the AI Canvas templates print no title. In a **post** the theme normally prints the title as the `<h1>`, so the block starts at `<h2>`; confirm it in the browser check. Levels follow the outline, never the wanted size; size is CSS. A section's heading comes before its image or video in the markup even when it displays after it (`order`, grid placement).
- **Landmarks depend on the template.** Framed: the theme already wraps the block in `<main>` and supplies the header, footer, and skip link, so use `<section>` with headings inside the root and never a second `<main>`. Blank: nothing surrounds the block, so the root holds its own `<header>`, `<main id="…">`, and `<footer>`, a `<nav aria-label="…">` if the page has its own navigation, and a styled skip link to the `<main>` as the first element when there is anything to skip.
- **DOM order is reading order.** Do not rearrange content with `order`, absolute positioning, or `flex-direction: row-reverse` in a way that changes what comes first.
- **Links say where they go.** No "click here", "read more", or "learn more" on their own; link the title or name the destination. A link with `target="_blank"` says so in its text or in visually hidden text ("opens in a new tab").
- **Nothing essential behind hover.** Whatever hover reveals is also reachable by focus and visible on touch.

**Images and media**

- Every `<img>` has `alt`. Write what the image says in this context, not "image of"; `alt=""` only for decoration. Pass the same text to `wp.sh upload --alt` so the Media Library carries it. An image reused from `wp.sh media` with an empty `alt_text` still needs alt in the block.
- Icons are inline SVG: `aria-hidden="true"` beside a text label, or `role="img"` with `aria-label` when the icon is the only content of a control.
- Video never autoplays with sound. Ambient muted video gets a visible pause button; real video gets `controls` and, when it carries speech, captions or a transcript. Ask the user for them rather than skipping it.

**Motion**

- Every animation and transition sits behind `@media (prefers-reduced-motion: no-preference)`, or is cancelled under `reduce`; JS reveals and auto-advancing check `matchMedia('(prefers-reduced-motion: reduce)')` and show the end state at once.
- No flashing, no parallax, no looping attention effects: a bounce or pulse repeats three times at most. Anything that moves on its own for more than five seconds (carousel, ticker) has a pause control and does not advance while focused or hovered.

**Controls and forms**

- **Targets at least 44 × 44px with 8px between them**, on phone width too. Pad small icon buttons and inline nav links up to size.
- **A visible focus style on every focusable element**: `:focus-visible` with a 2px or thicker outline that holds 3:1 against its background, drawn with `outline` and `outline-offset` so nothing shifts. Restate it on light and dark sections. Never `outline: none` without a replacement; block themes differ, so do not count on the theme's.
- **Interactive widgets are `<button>`-based** (`type="button"`), never a clickable `<div>` or an `<a>` without `href`, with matching ARIA state (`aria-expanded` plus `aria-controls`, `aria-selected`, `aria-current` on the active nav item) updated by the script, and keyboard behaviour to match: Enter and Space everywhere, arrow keys between tabs, Escape to close anything that opens. Write ARIA state in the no-JS default so it is true without the script (all panels shown means no `aria-expanded="false"` in the markup; the script sets it as it collapses them under `.is-js`).
- **Forms:** a visible `<label for>` outside every field, never a placeholder as the only label; required fields marked in text or with an asterisk the form explains; field borders 2px or at 3:1; placeholder visibly fainter than typed text but still readable. Errors appear as text next to the field, tied to it with `aria-describedby` and `aria-invalid`, and announced (`role="alert"` or an `aria-live` region), without moving the layout. The block's JS sends data nowhere, so a working form is normally the site's own form block or an embed; apply the same rules to whatever you place.

## Working with a non-technical user

Assume the user is non-technical unless they show otherwise. That changes how you talk, not what you build.

- **Report the page, not the mechanics.** A finished step is "The top section now shows your spring photo — take a look: <link>", with the screenshot when you have one. No file names, block markup, CSS scoping, REST, or script names in user-facing text.
- **Translate every error.** "unfiltered_html missing" becomes "the connection to your site isn't allowed to publish interactive pages — that's a WordPress setting; want me to walk you through it?" and routes to the setup skill.
- **Vague brief: one round of questions, then build.** Ask at most once — what the page is for, must-have sections, brand colors — after checking the Media Library for logos and photos. A visible first draft beats a questionnaire.
- **Infer content; never lorem ipsum.** Write real copy from the brief, the site's existing pages, and media titles. Flag invented specifics (prices, dates, addresses, quotes) as guesses for the user to correct.
- **A requested color that fails contrast: flag and ask, never quietly swap.** When the user's brand color or chosen pairing fails `wp.sh contrast` for how it would be used, say so in plain words before building with it ("your light green is hard to read as text on white for people with low vision") and offer the concrete options: the nearest shade that passes, shown next to theirs; keeping the brand color for large headings, backgrounds, and decoration with a darker shade for text; or using it as asked. It is their brand and their call. If they keep it, build it as asked and do not raise it again. Same for other accessibility needs only they can meet: ask once for captions or a transcript for a video with speech, and for what a photo shows when you cannot tell.
- **Say once, early:** changes go live right away, and "undo that" always brings the previous version back. Mention the wp-admin edit link so they know they can tweak text and images themselves.

## Failure modes

| Error | Meaning |
|---|---|
| "No sites are set up yet" | Nothing in `~/.claude/ai-canvas/sites/` — run the setup skill |
| "Ambiguous site" | Several saved sites match — pass the full host |
| "rejected the username or Application Password" | Password revoked or host now strips the Authorization header — setup B2 |
| `rest_cannot_create` / `rest_cannot_edit` | The connection user cannot edit this page |
| `rest_invalid_param` naming `template` | The AI Canvas templates are not on the site — `wp.sh template-ensure SITE`, then retry |
| "cannot manage templates" | Connection user is below Administrator — route to setup |
| `rest_post_invalid_id` | Wrong id or wrong `--type` (a post id passed as a page) |
| `rest_upload_*` | File type not allowed or too large for the host's upload limit |
| `script_was_escaped` true in `check` | Missing `unfiltered_html` — multisite or `DISALLOW_UNFILTERED_HTML` |
| `script_ampersand_rewritten` true in `check`, or `SyntaxError: Invalid or unexpected token` in the console | A bare `<` in the block; `wptexturize` turned `&` into `&#038;` inside the script — remove the `<` |
| Script present, no console error, widgets do nothing | It queried the root before the markup existed — use the DOM-ready `init` shape |
| Sections blank or missing in wp-admin's "Edit content" view, fine on the front end | CSS hides them until JS adds a class, and the script never runs in the editor — put the hidden state under `.canvas-x.is-js` |
| Page looks unstyled in wp-admin's editor | Expected in "Edit code" view; the front end and "Edit content" view render it |
