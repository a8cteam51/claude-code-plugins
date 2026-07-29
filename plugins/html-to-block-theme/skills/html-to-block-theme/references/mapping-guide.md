# Mapping guide: HTML/CSS → WordPress blocks

This is the source of truth for how design markup becomes block markup. Walk the HTML depth-first so nested structures resolve inside-out, and apply the escalation ladder to every styling decision.

## The escalation ladder (apply per design detail)

Resolve every visual detail at the **lowest** rung that achieves it. Record the rung used for each non-trivial decision so the report can justify it.

1. **Core block + block supports.** Express the detail through a core block and its supported attributes (spacing, colour, typography, border, dimensions, layout), drawing values from `theme.json` presets. This is the default — WordPress block properties are the de-facto styling mechanism.
2. **Block style variation** — registered and shipped per `block-styles-guide.md`. Use when a recurring custom class adds styling that supports cannot express, but is still "a variant of a core block."
3. **Custom block** (build-less, see `custom-blocks-guide.md`). Use only for genuine behaviour or markup beyond core: JS interactions, dynamic/repeating structures, or markup core blocks cannot produce.
4. **Documented custom CSS.** Last resort. Block-targeting CSS follows the same per-block-file rule as rung 2 (`block-styles-guide.md`). Keep each rule minimal, scope it tightly, and flag it in the report with the reason rung 1–3 could not do it.

Never invent block attribute names. Use documented globals (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `fontFamily`, `align`, `layout`) plus the per-block attributes this guide spells out. The Studio validator catches drift after the fact, but every wrong name costs a fix round — get them right up front. Colour classes are `has-{slug}-background-color` / `has-{slug}-color`, **not** `has-background-color-{slug}`.

## Element → core block

| Design markup | Core block | Notes |
|---|---|---|
| `<section>` / outer `<div>` wrapper | `core/group` | `align:full` for full-bleed; constrained layout for centered content. The structural workhorse. |
| Horizontal flex row of items | `core/group` with `layout:{"type":"flex"}` or `core/columns` | Use `columns` when items are proportional content columns; flex group for nav/button rows/inline clusters. |
| Vertical stack with consistent gap | `core/group` with `layout:{"type":"flex","orientation":"vertical"}` | `blockGap` carries the gap. |
| CSS grid of cards | `core/columns` (fixed) or `core/group` `layout:{"type":"grid"}` | Grid layout for auto-fit/min-width card grids; `columns` for a fixed N-up. |
| `<h1>`–`<h6>` | `core/heading` | `level` attribute. |
| `<p>` / inline text | `core/paragraph` | |
| `<a class="button">` / CTA | `core/button` inside `core/buttons` | Style via button supports or a block style variation, not bespoke CSS. |
| `<img>` | `core/image` | Content images → media library; decorative → theme asset. |
| `<ul>`/`<ol>` | `core/list` + `core/list-item` | |
| Site nav | `core/navigation` | Lives in `parts/header.html`. |
| Logo | `core/site-logo` or `core/image` | |
| Icon / inline SVG | `core/html` (bare inline SVG only) or a custom block if interactive | An SVG wrapped in an `<a>`/`<div>` fails the core/html policy — icon *links* are `core/social-links` (restyled by a block style variation when the glyph is bespoke). Do not invent an "icon block." |
| Background media + overlay + content | `core/cover` | Maps cleanly to hero sections with a background image/colour and overlay. |
| Separator / `<hr>` | `core/separator` | |
| Spacer gap (no semantic content) | spacing supports first; `core/spacer` only if unavoidable | Prefer `blockGap`/padding over spacer blocks. |
| Repeating posts/cards from data | `core/query` + `core/post-template` | For anything that should be driven by WordPress content rather than hardcoded. |

## CSS → block supports

Translate computed CSS to attributes, pulling values from `theme.json` presets wherever a preset exists (use the `var:preset|...` form so styles stay token-driven):

- **padding / margin** → `style.spacing.padding` / `style.spacing.margin`. Prefer preset spacing: `"padding":{"top":"var:preset|spacing|40"}`.
- **gap** → `style.spacing.blockGap` (and the block's `layout`).
- **background-color / color** → `backgroundColor`/`textColor` (named preset) or `style.color.background`/`style.color.text` (raw). Prefer named presets.
- **background-image** → `core/cover` background, or `style.background.backgroundImage`.
- **font-size / line-height / weight / letter-spacing** → `fontSize` (preset) or `style.typography.*`.
- **font-family** → `fontFamily` (preset defined in `theme.json`).
- **border / radius** → `style.border.*` (`width`, `color`, `radius`, `style`).
- **max-width container** → constrained `layout` + `contentSize`/`wideSize` in `theme.json`, not a CSS `max-width`.
- **flex/grid alignment & direction** → the block's `layout` object (`justifyContent`, `orientation`, `flexWrap`, `minimumColumnWidth`).

If a declaration has no support and no preset path, escalate one rung — do not reach straight for custom CSS.

## Layout mapping cheatsheet

- **Centered content column** → `core/group` constrained layout; widths come from `theme.json` `settings.layout`.
- **Full-bleed band with inner content** → outer `core/group` `align:full` (background/padding) wrapping an inner constrained group.
- **Two/three/four column row** → `core/columns`; set per-column `width` only when the design is asymmetric.
- **Auto-fit card grid** → `core/group` `layout:{"type":"grid","minimumColumnWidth":"16rem"}`.
- **Hero** → `core/cover` (background) with heading/paragraph/buttons inside.

## File classification: template vs part vs page vs pattern

For each HTML file in the set, decide its home:

- **Core template** — the file represents a WordPress view: blog index → `templates/index.html` (or `home.html`); a single post layout → `single.html`; an archive → `archive.html`; a 404 → `404.html`; a generic page layout → `page.html`. **Never `front-page.html`** — see the homepage rule below.
- **Shared-wrapper page content** — the file is an inner page (About, Services, Contact) that shares the same header/footer/wrapper as others and differs only in body content. The wrapper becomes a template (often `page.html`); the body becomes a **WordPress page** whose `post_content` is block markup, assigned to that template. The content lives in WordPress, not hardcoded in the template.
- **Template part** — markup that repeats across files unchanged (header, footer, nav, a CTA banner) → `parts/*.html`, referenced via `core/template-part`.
- **Block pattern** — a repeated *section* (feature grid, testimonial row, pricing table) that recurs with varying content → a registered pattern in `patterns/*.php`, inserted where needed. Use synced patterns only when the user wants edit-once-update-everywhere.

When two files share chrome but differ in body, extract the chrome **once** into parts and a shared template; never duplicate it per file.

### The homepage rule: no front-page.html

Never create `templates/front-page.html`. The homepage is **content, not a view**: build it as a WordPress page whose `post_content` is the block markup, then point WordPress at it through the Reading settings (`wp option update show_on_front page` + `wp option update page_on_front <page-id>`). Choose its template by wrapper:

- Homepage shares the standard page chrome → the shared page template (`page.html` / `default`).
- Homepage has its own chrome (different or absent header/footer, full-viewport hero) → a **custom page template** (e.g. `templates/page-home.html`) registered in `theme.json` `customTemplates`, rendering the page's content via `core/post-content`.

This keeps the homepage editable in WordPress like every other page instead of hardcoding its content in a template that shadows the page.

## Asset routing

- **Fonts** → declare in `theme.json` `settings.typography.fontFamilies` with `fontFace` entries; copy the font files into `assets/fonts/`. Do not `@import` from a CDN.
- **Content images** (photos, illustrations that are page content) → import to the media library: `studio wp media import <path> --porcelain --path=<site>` → use the returned attachment in `core/image`.
- **Decorative / background images** (textures, hero backgrounds) → copy into the theme `assets/` and reference by theme-relative URL.
- **Linked CSS** → read it to extract tokens and per-class styling; it is design intent to be *translated*, not shipped. Do not enqueue the original stylesheet.
- **JS** → see below.

## JS / interactivity

Static JS in the design (sliders, accordions, mobile menus, scroll effects) has no home in static block markup. Route it by rung:

- **Core block already does it** (e.g. `core/navigation` mobile menu, `core/details` accordion) → use the core block; drop the bespoke JS.
- **Needs custom behaviour** → a build-less custom block whose `view.js` (or the Interactivity API) reproduces it (see `custom-blocks-guide.md`). This is the home the user wants for "functionality beyond core."
- **Purely decorative scroll/animation** → reproduce with CSS where cheap; otherwise drop it and note it in the report. Do not enqueue the original JS file wholesale.

## core/html policy (enforced by the validator)

The Studio validator statically rejects `core/html` blocks whose markup should be editable blocks — `core/html` is not a general-purpose escape hatch. It is allowed only for:

- **Bare inline SVG** — the `<svg>` element itself. Wrapping it in an `<a>` or `<div>` already fails; icon links belong in `core/social-links` with a block style variation for a bespoke glyph.
- **Third-party embed / interaction markup with no block equivalent** (a booking-widget snippet, a marquee), kept to the embed's own markup.
- **A single script block.**

Everything else — text, links, layout, images — must be rewritten as editable core blocks even when that costs a ladder rung. Plan mappings assuming this policy; a "downgrade to core/html" that violates it bounces off validation instead of shipping.

## Fidelity discipline

- Reproduce structure and spacing faithfully; accept sub-pixel/minor drift to stay on a lower ladder rung.
- Anything dropped (animation, effect, unsupported layout) goes in the report's residual-drift list with the reason.
- Long-tail markup with no clean mapping → decompose into core blocks plus tightly-scoped CSS where possible; `core/html` is a fallback only within the core/html policy above (embeds, bare SVG, scripts), flagged as a TODO. Do not invent block types.
