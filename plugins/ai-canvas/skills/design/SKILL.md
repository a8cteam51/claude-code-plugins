---
name: design
description: Design a WordPress page with the user on this computer, as one full-width Custom HTML block (markup, CSS, and JS) kept in a local folder, previewed in the browser, checked, and changed on their feedback, without touching any website. Use when the user asks to "build a landing page", "make me a page for my event", "design a page", "vibe a page", "change the photo/text/colors on my page", "undo that", or wants to work on a page before it goes on their WordPress site. Putting the page on the site is the publish skill; this skill never does it.
---

# Design a page locally

You and the user design a page here, on this computer. You write it as one Custom HTML block in a folder, show it in a local preview, and change it until the user is happy. Nothing in this skill touches a website. When the user wants the page on their site, that is the `ai-canvas:publish` skill, and only on their word.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/canvas.sh" <command> DIR
```

`DIR` is the page's folder. The script lints, builds previews, serves them, snapshots, and checks color contrast. It needs only bash and the system's standard tools.

## Where a page lives

One folder per page, inside an `ai-canvas` folder in a place the user picks:

```text
<where the user said>/ai-canvas/<page-slug>/
├── block.html    the page: one complete Custom HTML block. The only file you edit.
├── preview/      built by `canvas.sh preview`. Never edit.
├── history/      snapshots from `canvas.sh keep`
└── site.txt      written by the publish skill once the page is on a site
```

**Ask the user where to save it**, in the same round as the brief: "Where on your computer should I keep this page's files? Your Desktop is fine." The Desktop gives `~/Desktop/ai-canvas/<page-slug>/`. If they leave it to you, use the Desktop and say so. Never default to the folder Claude Code happens to be running in, and never write into this plugin's own folder: a session can be started from anywhere, and that place is often somewhere you are not allowed to write.

Ask once. The user's next page goes in the same `ai-canvas` folder without asking. In a later session, when you do not know where their pages are, look for an `ai-canvas` folder on the Desktop and in Documents before asking again.

The slug is short, lowercase, and hyphenated (`spring-launch`). If `site.txt` exists the page is already on a site: your changes stay local until it is published again, so say "this is your local copy; your site still shows the earlier version" when you show one.

A page that is on the site but has no folder here: bring it down first with the publish skill's "Bring a page down".

## The loop

1. **Brief.** One round of questions at most: what the page is for, must-have sections, brand colors, and where to save the page's files (above). Then build. A first draft the user can see beats a questionnaire. When the brief needs no other question, where to save is still asked, unless the user has already said or their `ai-canvas` folder is known.
2. **Write `block.html`** in the shape below. For a new page, load a frontend design skill first if one is listed (`frontend-design`) and follow its direction; the rules here are about what WordPress needs, not about taste.
3. **`canvas.sh preview DIR`.** It lints, then builds the preview pages. Fix every `error`; read every `warning`.
4. **`canvas.sh serve DIR`**, run in the background, once per session. The preview is at `http://127.0.0.1:4173/`.
5. **Check your work** (below) before showing anything.
6. **Show the user.** Give them the address to open in their own browser and a screenshot. Say what you built and which specifics you invented. Ask what to change.
7. **Each round of feedback:** `canvas.sh keep DIR` first, then edit, preview, check, show. "Undo that" is `canvas.sh undo DIR`, then preview again.
8. **Stop at the user's word.** Never publish on your own. Offer it once the page is right: "Want me to put this on your site?"

## The block

`block.html` is exactly this shape. The lint enforces the first and last lines and the two tags.

```html
<!-- wp:html {"align":"full"} -->
<style data-wp-block-html="css">
/* all CSS, every selector starting with the root class */
/* states only JS can leave (hidden until revealed) under .is-js */
</style>
<script data-wp-block-html="js">
(function () {
  function init() {
    var root = document.querySelector('.canvas-spring-launch');
    if (!root) return;
    root.classList.add('is-js');
    /* behaviour here, queried from root */
  }
  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', init); } else { init(); }
})();
</script>
<div class="canvas-spring-launch">
  <!-- markup -->
</div>
<!-- /wp:html -->
```

On the site the block sits inside the page template's `<main>`, at full width, with no page title printed. The user decides when publishing whether the site's own header and footer surround it or the page stands alone, so the same block has to work both ways. That fixes most of what follows.

- **A fragment, not a document.** No `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`, meta tags, `<link>`, `@import`, or script `src`. No external references at all: fonts are the theme's or a system stack, using only the weights and italics that face has.
- **One `<h1>`, no `<main>`.** Neither template prints a title, so the block's first section carries the page's heading. Both supply `<main>`; inside the root use `<section>` with headings. Never assume the block starts at the top of the screen (the site header may sit above it), and never assume a site menu is there to navigate with.
- **A page meant to stand alone brings its own way around.** If the user wants no site header or footer, give the root what the site would have supplied: a top bar with the name or logo, a `<nav aria-label="…">` if the page has sections to jump to, and a closing footer line. With a nav, the root's first element is a skip link to the first section, visible on focus.
- **One root element, `canvas-<slug>`, and every selector starts with it.** Never style `body`, `html`, `:root`, or a bare element; that restyles the site's header and footer. Custom properties go on the root class.
- **The root sets every inherited text property**: color, background, font-family, font-size, font-weight, font-style, line-height, letter-spacing, text-transform, text-align. Whatever it leaves out, the theme fills in.
- **Restate what themes style directly.** Themes put rules on `h1`–`h6`, `a`, `button`, and form fields, and an element rule beats anything the root only passes down. On each of those set font-family, font-size, font-weight, font-style, line-height, letter-spacing, text-transform, color, and margin; on buttons and fields also background, border, border-radius, box-shadow, and padding. `theme.html` shows what you missed.
- **The script runs before the markup exists.** It sits above the root and WordPress prints it in place, so a top-level `querySelector` returns null and the script silently does nothing. Keep the `init` shape above.
- **The script never runs in wp-admin's editor.** The site owner edits the page there, so it must be complete with no JS: every section visible and stacked. Anything only JS can undo (`opacity: 0` awaiting a reveal, hidden tab panels, one slide of a carousel) goes under `.canvas-x.is-js`, the class the script adds. `editor.html` is that view. For what must differ in the editor even then (a `100vh` hero, sticky or fixed positioning, autoplaying video), write `.editor-styles-wrapper .canvas-x …`.
- **No `<` in the style or the script, and none bare in text.** WordPress treats any `<` as the start of a tag running to the next `>` and rewrites every `&` in between to `&#038;`; `a && b` becomes a syntax error that kills the script, and the stored page looks fine. Write `b > a`, `!==` for loop bounds, and `&lt;` in text. The lint catches it in style and script.
- **Never depend on how the source is written.** When the owner edits the page, the site's editor rewrites the block from the live document: `<path/>` becomes `<path></path>`, `data-open` becomes `data-open=""`, an empty `style=""` appears on what they touched. Test attributes with `hasAttribute`, never against an exact value or their absence; do not rely on `:empty` or on whitespace between tags.
- **JS is self-contained.** DOM behaviour, animation, small interactions. It runs unsandboxed on the site, so it never calls site endpoints, loads third-party scripts, or sends data anywhere. One IIFE, everything queried from the root.
- **Editable by humans.** Text stays in ordinary headings, paragraphs, list items, links, and buttons, and images are plain `<img>` tags; those are what the owner can click to edit. Text assembled by JS is not editable, so build labels from elements that are (tab buttons made from each panel's heading). A hero background is `background-image` inline on the element plus `data-vc-bg`, so the owner can swap the photo.
- **Images come from the site's Media Library**, referenced by the full address of the right size, never a guessed path. To see what is there, use the publish skill's "Media Library". For new photos, ask the user to add them in wp-admin (Media → Add New Media File) and tell you when they are up. With no image to hand, draw with inline SVG and CSS rather than leaving a hole.

## Check your work

`canvas.sh preview` builds five pages. Each has `aiCanvasReport()`, which returns one line of JSON about the page as rendered.

| Page | Shows |
|---|---|
| `index.html` | The page between a stand-in site header and footer |
| `alone.html` | The page with nothing around it |
| `editor.html` | The page with its script never run: what wp-admin's editor shows |
| `theme.html` | The page under a deliberately hostile theme stylesheet |
| `phone.html` | `index.html` in a 390px-wide frame |

With the browser tools (`mcp__claude-in-chrome__*`; load `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `computer`, `javascript_tool`, `browser_batch`, and `tabs_close_mcp` in one `ToolSearch`), open the preview in a new tab and, for each page, run `aiCanvasReport()` and take a screenshot. Fix, preview, and reload until all of this holds:

| Report field | Must be |
|---|---|
| `errors` | `[]`. Anything listed is a script error. |
| `scriptRan` | `true`, except `editor.html` where it is `false` |
| `h1`, `headingJumps` | `1` and `[]` |
| `mainElements` | `1` (the preview's own; `2` means the block added one) |
| `overflowX`, `pastEdge` | `0` and `[]`, on `phone.html` above all |
| `imagesWithoutAlt`, `imagesWithoutSize`, `imagesNotLoaded` | `[]` |
| `smallTargets` | `[]`: every control is at least 44 by 44 pixels |
| `unnamedControls`, `smallText`, `duplicateIds` | `[]` |
| `themeLeaks` (`theme.html`) | `[]`. Each entry names an element and the property the theme reached. |

The report cannot see what a person sees, so also look:

- **`index.html`**: screenshot the top, then scroll through every section. It matches what the user asked for.
- **`alone.html`**: when the page may stand alone, look at its top and bottom. It reads as a complete page with nothing above or below it.
- **`editor.html`**: every section is visible and readable. Blank space where a section belongs is a state not gated on `.is-js`.
- **`theme.html`**: it looks like `index.html`. Pink, spaced-out, slanted, or oversized anything is a leak.
- **`phone.html`**: zoom the screenshot into the frame. Nothing overlaps, nothing is cut off, and controls are not crowded.
- **Widgets**: click each one and use it by keyboard (Tab, Enter, Space, arrows, Escape). Take a screenshot before sending keys to a tab; keys sent before one go nowhere. The focus ring is visible on every stop, on light and dark sections alike.

Close the tab when the session's design work is done.

Without the browser tools you cannot see the page. Say so, give the user the address, and rely on the lint, the contrast check, and what they tell you.

## Keep pages fast

- **Right-size images.** Reference the smallest Media Library size that covers the display area. A full-size photo in a 600px column is the usual way these pages balloon.
- **`width` and `height` on every `<img>`**, matching the size referenced, so nothing shifts as images load.
- **Lazy-load below the fold only**: `loading="lazy" decoding="async"` there; the hero stays eager with `fetchpriority="high"`.
- **Video is opt-in**: `preload="none"`, `muted playsinline` for ambient video, started and paused by an IntersectionObserver.
- **No frameworks, no client-side templating.** The markup in the block is what renders. Never read layout in a scroll handler; use IntersectionObserver.
- **No data-URI images.**

## Build accessible pages

The target is WCAG 2.1 AA on the first draft; you choose the palette, type, and markup in one pass, and nobody reviews it after you. Go to AAA (7:1 text, no text under 16px) only when the user asks, and say that you did.

**Color**

- **Check every pairing before you write it**: `canvas.sh contrast FG BG [FG BG ...]` with the whole palette in one call. 4.5:1 for text, 3:1 for large text (24px, or 18.66px bold) and for UI boundaries (field borders, icons, focus rings). Flatten transparent colors onto their background first. Never eyeball it.
- **Never color alone.** Hover, focus, selected, and error each add a second cue: underline, border, thickness, icon. Links in running text stay underlined. Not bold on hover; it reflows the line.
- **Text over a photo** sits on a solid or gradient scrim that holds the ratio across the whole image, because the owner can swap the photo.

**Type**

- Body text 16px or larger, nothing at 12px or under, line height 1.5 or more, lines of 50 to 80 characters (`max-width: 65ch`).
- No justified text. Uppercase only on short labels, set with `text-transform`. No text baked into an image, logos aside.

**Structure**

- Heading levels follow the outline, never the wanted size. A section's heading comes before its image in the markup even when it displays after it.
- DOM order is reading order. Do not move content with `order`, absolute positioning, or reversed flex directions.
- Links say where they go: no "click here" or "read more" alone. A link that opens a new tab says so.
- Nothing essential behind hover; whatever hover shows, focus and touch show too.

**Images and motion**

- Every `<img>` has `alt` that says what the image means here; `alt=""` only for decoration. Icons are inline SVG with `aria-hidden="true"` beside a label, or `role="img"` with `aria-label` when the icon is the whole control.
- Video never autoplays with sound. Ambient video gets a visible pause button; video with speech gets captions or a transcript, so ask the user for them.
- Every animation sits behind `@media (prefers-reduced-motion: no-preference)`. No flashing, no parallax. Anything that moves on its own for more than five seconds has a pause control.

**Controls and forms**

- Targets at least 44 by 44 pixels with 8px between them, at phone width too.
- A visible `:focus-visible` outline, 2px or more, holding 3:1 against its background, on every focusable element. Never `outline: none` without a replacement.
- Widgets are `<button type="button">`, never a clickable `<div>`, with ARIA state the script keeps true (`aria-expanded`, `aria-selected`, `aria-controls`) and matching keys: Enter and Space everywhere, arrows between tabs, Escape to close. Write the no-JS markup so its ARIA is true without the script.
- Every field has a visible `<label for>`. Errors are text next to the field, tied with `aria-describedby` and `aria-invalid` and announced with `role="alert"`, without moving the layout. The block's JS sends data nowhere, so a working form is the site's own form block or an embed.

## Working with a non-technical user

Assume the user is non-technical unless they show otherwise. That changes how you talk, not what you build.

- **Report the page, not the mechanics.** "The top section now shows your spring photo. Take a look: <address>", with the screenshot. No file names, markup, CSS, or script names.
- **Never lorem ipsum.** Write real copy from the brief and flag invented specifics (prices, dates, names, quotes) as guesses to correct.
- **A requested color that fails contrast: say so and ask, never quietly swap.** "Your light green is hard to read as text on white for people with low vision." Offer the nearest shade that passes, the brand color kept for large headings and decoration, or as asked. It is their brand and their call; once they choose, do not raise it again.
- **Say once, early:** this is a draft on their computer, nothing is on their site yet, and "undo that" always brings the last version back.
