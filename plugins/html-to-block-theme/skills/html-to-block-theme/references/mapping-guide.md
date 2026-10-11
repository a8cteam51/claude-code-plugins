# Mapping guide: HTML/CSS → WordPress blocks

This is the source of truth for how design markup becomes block markup. Walk the HTML depth-first so nested structures resolve inside-out, and apply the escalation ladder to every styling decision.

## The escalation ladder (apply per design detail)

Resolve every visual detail at the **lowest** rung that achieves it. Record the rung used for each non-trivial decision so the report can justify it.

1. **Core block + block supports.** Express the detail through a core block and its supported attributes (spacing, colour, typography, border, dimensions, layout), drawing values from `theme.json` presets. This is the default — WordPress block properties are the de-facto styling mechanism.
2. **Block style variation** — registered and shipped per `block-styles-guide.md`. Use when a recurring custom class adds styling that supports cannot express, but is still "a variant of a core block."
3. **Custom behaviour** (`custom-blocks-guide.md`). Use only for genuine behaviour or markup beyond core supports: JS interactions, dynamic or repeating structures, or markup core blocks cannot produce. Core features come first (patterns, Block Bindings, the Interactivity API on existing blocks, variations and filters), then a block reused from the A8C Special Projects blocks monorepo, and only then a new block built in the monorepo. Never create a block in the theme.
4. **Documented custom CSS.** Last resort. Block-targeting CSS follows the same per-block-file rule as rung 2 (`block-styles-guide.md`). Keep each rule minimal, scope it tightly, and flag it in the report with the reason rung 1–3 could not do it.

Never invent block attribute names. Use documented globals (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `fontFamily`, `align`, `layout`) plus the per-block attributes this guide spells out. The Studio validator catches drift after the fact, but every wrong name costs a fix round — get them right up front. Colour classes are `has-{slug}-background-color` / `has-{slug}-color`, **not** `has-background-color-{slug}`.

### Read the installed core, then probe

Attribute forms move between WordPress versions. Markup written from memory of an older core fails validation or is silently rewritten. Two checks cost one call each:

- **Read the block's `block.json`** in the site's core (`wp-includes/blocks/<block>/block.json`) for its attributes and supports before writing a block you have not written on this core. On WordPress 7.1, for example, text alignment on a paragraph, heading or button is `style.typography.textAlign`, not an `align` or `textAlign` attribute.
- **Render a probe** to see what an attribute prints, with no page or database write (`<plugin-root>` is the plugin's directory, which the skill and the builder's instructions give):

  ```bash
  bash "<plugin-root>/scripts/render-probe.sh" --site-path <site-path> --markup <markup-file> [--post-id <id>]
  ```

  It prints the HTML and the block-supports CSS the markup produced, with the PHP and WordPress versions. Use it wherever this guide says a form depends on the core version, and before building a section on an attribute form you have not confirmed. The probe runs `do_blocks()`, so it does not texturise text as a real page does.

## Element → core block

| Design markup | Core block | Notes |
|---|---|---|
| `<section>` / outer `<div>` wrapper | `core/group` | `align:full` for full-bleed; constrained layout for centered content. The structural workhorse. |
| Horizontal flex row of items | `core/group` with `layout:{"type":"flex"}` or `core/columns` | Use `columns` when items are proportional content columns; flex group for nav/button rows/inline clusters. |
| Vertical stack with consistent gap | `core/group` with `layout:{"type":"flex","orientation":"vertical"}` | `blockGap` carries the gap. A vertical flex group wraps by default (§ Layout recipes). |
| CSS grid of cards | `core/columns` (fixed) or `core/group` `layout:{"type":"grid"}` | Grid layout for auto-fit/min-width card grids; `columns` for a fixed N-up. |
| `<h1>`–`<h6>` | `core/heading` | `level` attribute. |
| `<p>` / inline text | `core/paragraph` | |
| `<a class="button">` / CTA | `core/button` inside `core/buttons` | Style via button supports or a block style variation, not bespoke CSS. See § Buttons. |
| `<img>` | `core/image` | Design images go to the media library (§ Asset routing). See § Images. |
| `<ul>`/`<ol>` | `core/list` + `core/list-item` | A list without markers is a registered style (§ Links, headings and lists). |
| Site nav | `core/navigation` | Lives in `parts/header.html`. |
| Logo | `core/site-logo` | No part then carries an environment URL. Its duotone setting recolours a single-colour logo (§ Images). |
| Icon / inline SVG | `core/image` from the media library; a decorative icon inside a button or link is painted from the block's stylesheet (§ Buttons); `core/html` (bare inline SVG only) when the icon must inherit colour or animate; custom behaviour (`custom-blocks-guide.md`) if interactive | An SVG wrapped in an `<a>`/`<div>` fails the core/html policy — icon *links* are `core/social-links` (restyled by a block style variation when the glyph is bespoke). Do not invent an "icon block." |
| Background media + overlay + content | `core/cover` | Maps cleanly to hero sections with a background image/colour and overlay. |
| Separator / `<hr>` | `core/separator` | It has no thickness setting. A hairline between two sections is the next group's top border, with an eight-digit hex colour where the original used opacity. |
| Spacer gap (no semantic content) | spacing supports first; `core/spacer` only if unavoidable | Prefer `blockGap`/padding over spacer blocks. |
| Accordion; tabs | `core/accordion` or `core/details`; `core/tabs` | WordPress 7.1 ships the accordion and tabs blocks. See § JS / interactivity. |
| Repeating posts/cards from data | `core/query` + `core/post-template` | For anything that should be driven by WordPress content rather than hardcoded. See § Query loops, archives and pagination. |

## CSS → block supports

Translate computed CSS to attributes, pulling values from `theme.json` presets wherever a preset exists (use the `var:preset|...` form so styles stay token-driven):

- **padding / margin** → `style.spacing.padding` / `style.spacing.margin`. Prefer preset spacing: `"padding":{"top":"var:preset|spacing|40"}`. Raw custom-property vars are fine here (serialized inline verbatim). The margin support takes a negative length.
- **gap** → `style.spacing.blockGap` (and the block's `layout`). It accepts a preset reference (`var:preset|spacing|40`) or a raw length. **It drops any value that contains a parenthesis, backslash, ampersand, equals sign or closing brace**, so `calc()`, `clamp()` and raw `var(--wp--custom--*)` fall back silently to the 24px default. On a flex group it also accepts an object, `{"top": <row gap>, "left": <column gap>}`.
- **background-color / color** → `backgroundColor`/`textColor` (named preset) or `style.color.background`/`style.color.text` (raw). Prefer named presets. **Write a raw colour as hex, with eight digits for transparency.** WordPress compiles element styles (`style.elements.*`), state styles and viewport states on the server and drops a declaration whose value holds a colour function (`rgb()`, `rgba()`, `hsl()`): the class is still added and no rule is printed. A static block's own saved inline style keeps such a value, which hides the trap. A colour function inside a gradient is kept. The standards audit fails on a dropped colour.
- **background-image** → `core/cover` background, or `style.background.backgroundImage`.
- **font-size / line-height / weight / letter-spacing** → `fontSize` (preset) or `style.typography.*`. Letter spacing is written in `em`, never as a fraction of a pixel (§ Pixel values are whole pixels). With fluid typography off (`theme-json-guide.md`), a `clamp()` expression with viewport units is accepted as a block's own `style.typography.fontSize` and printed unchanged, so a design that writes its sizes as `clamp()` maps to attributes.
- **font-family** → `fontFamily` (preset defined in `theme.json`).
- **border / radius** → `style.border.*` (`width`, `color`, `radius`, `style`).
- **text-shadow** → valid in `theme.json` styles on WordPress 7.1, but no block has an attribute for it. A text shadow on one block is a rule in a block style.
- **min-height** → the `minHeight` dimension support prints an **inline style**. On WordPress 7.1 and later a `@mobile` or `@tablet` value overrides it (§ Per-viewport values). A height that changes at any other width, or on an older core, lives in the block's CSS file with every one of its values (§ A value that steps at another width).
- **max-width container** → constrained `layout` + `contentSize`/`wideSize` in `theme.json`, not a CSS `max-width`.
- **flex/grid alignment & direction** → the block's `layout` object (`justifyContent`, `orientation`, `flexWrap`, `minimumColumnWidth`).

If a declaration has no support and no preset path, escalate one rung — do not reach straight for custom CSS.

## Per-viewport values, states and visibility (WordPress 7.1 and later)

Checked on WordPress 7.1.3, on the front end and through the validator. The skill also runs on older cores: confirm each form with a render probe on the installed core before relying on it, and check the editor canvas on the first page that uses one, which was not checked.

- **Per-viewport values.** `style["@mobile"]` and `style["@tablet"]` on a block instance take any style subtree: spacing, typography, colour, border, dimensions. They print under a `wp-states-<hash>` class with `!important`, so they beat the inline style the base attribute prints.

  ```json
  "style": {
    "spacing": { "padding": { "top": "var:preset|spacing|80" } },
    "@tablet": { "spacing": { "padding": { "top": "var:preset|spacing|60" } } },
    "@mobile": { "spacing": { "padding": { "top": "var:preset|spacing|40" } } }
  }
  ```

- **Per-viewport layout.** `style["@mobile"].layout` (and `@tablet`) overrides a container's flex orientation, wrap, justification and alignment, and a child's `selfStretch`, `flexSize` and grid span. A row that stacks on phones needs no stylesheet.
- **A block's size in a flex row** is a child layout attribute, per viewport: `style.layout` with `selfStretch: "fixedNoShrink"` and a `flexSize`, and another `flexSize` under `@mobile`, prints the flex basis for each state on any child block. A site logo follows through its image's own `max-width`, so a logo that changes size at a viewport state needs no CSS.
- **Visibility.** `metadata.blockVisibility` hides a block: `false` hides it everywhere, `{"viewport":{"mobile":false}}` per viewport (`mobile`, `tablet`, `desktop`).
- **States.** `style[":hover"]` (also `:focus`, `:focus-visible`, `:active`) works per instance on `core/button` and `core/navigation-link` only. It accepts a gradient (`style[":hover"].color.gradient` prints the background on the link). A `filter: brightness(n)` hover on a filled button is the same fill with each channel multiplied by n, so it is a hover colour and not a rule. Transforms and filters themselves have no support.
- **The two breakpoints** come from `theme.json` `settings.viewport` (`theme-json-guide.md`). `@mobile` is `width <= mobile`. `@tablet` is the **range** between the two, so a value wanted everywhere below the tablet breakpoint is written in both states.
- **Each bound is inclusive, and a whole pixel.** A design rule written `max-width: N` wants the value `N`. One written `min-width: N` wants the last pixel below it, `N - 1`: `767px` for a design that changes at `min-width: 768px`. Never a fraction such as `767.98px` (§ Pixel values are whole pixels). A design that uses both forms at the same nominal breakpoint can match only one with states; the other is a stylesheet rule or a recorded normalisation.
- **There are only two breakpoints.** A change at any other width still needs a registered block style.

### A value that steps at another width

A block attribute for margin, padding, height or font size prints an inline style, and a media query in a block stylesheet cannot beat an inline style without `!important`. When a property changes at a width that is not one of the two viewport states, put **every** value of that property in the registered block style and leave the attribute unset. Mixing the two, with the base value as an attribute and the steps in CSS, is what forces `!important`.

- Block gap is the exception: it prints a class rule, which a stylesheet can override.
- `core/site-logo`'s `width` attribute has no per-viewport form. A logo that changes size at a viewport state uses the flex child attributes above. One that steps at another width needs a rule on its `img`.

### Pixel values are whole pixels

A value written in pixels is a whole number of pixels, everywhere: `theme.json`, block attributes, stylesheets. Never `767.98px`, `0.5px` or `-0.75px`. The standards audit fails on one.

- **A breakpoint is the last whole pixel of its range.** `settings.viewport` holds `767px` for "below 768px". A stylesheet rule that must switch together with a viewport state uses the state's own bound (`max-width: 767px`), because WordPress prints the state as `(width <= 767px)`.
- **The other side of a `min-width: N` rule is a range query,** `(width < N)`. It is exact at every width and holds a whole number, where `(max-width: N - 0.02px)` does not. WordPress prints range queries for the viewport states itself, so this asks nothing new of a browser.
- **What the whole pixel costs, so that it can be said:** at a fractional viewport width inside the last pixel below a breakpoint, which only browser zoom or fractional display scaling produces, a viewport state ends up to a pixel before a design rule written `min-width: N`. Whole-pixel widths are unaffected. Converting a build from fractional to whole breakpoints left its layout identical at every whole width measured.
- **Finer than a pixel means a relative unit.** Letter spacing is written in `em`. An original's sub-pixel tracking (`-0.75px` on a 36px heading) is usually one ratio of the font size (`-0.02em`) written out in pixels. Convert it, do not copy it, and record what the ratio changes where the same text is set at another size: the tracking then scales with the text, where the original's stayed fixed.

## Layout mapping cheatsheet

- **Centered content column** → `core/group` constrained layout; widths come from `theme.json` `settings.layout`.
- **Full-bleed band with inner content** → outer `core/group` `align:full` (background/padding) wrapping an inner constrained group.
- **Two/three/four column row** → `core/columns`; set per-column `width` only when the design is asymmetric.
- **Auto-fit card grid** → `core/group` `layout:{"type":"grid","minimumColumnWidth":"16rem"}`.
- **Hero** → `core/cover` (background) with heading/paragraph/buttons inside.

### Post content sits at content width, in every template

Every template gives `core/post-content` a constrained layout, landing-page templates included:

```html
<!-- wp:post-content {"layout":{"type":"constrained"}} /-->
```

- **A block in the content is then as wide as the content column** (`settings.layout.contentSize`) unless it is aligned: `alignwide` takes `wideSize`, `alignfull` the full width. That holds in the editor as on the page.
- **A full-bleed section of a page is an `alignfull` group in the page's content,** with its own inner constrained layout for its column. Write the alignment on every top-level block that is wider than the content column.
- **Never let post content fill the template to get full-bleed sections for free.** A design of full-width bands tempts it: a flow-layout post content and unaligned sections look right on the front end. In the editor every block is then full width, so is each new block an editor adds, and the wide and full alignment controls are gone.
- **Set `contentSize` and `wideSize` to the design's real text column and wide column.** They are what a new block gets.
- **Converting is layout-neutral.** Giving the template's post content a constrained layout and every existing top-level block `"align":"full"` left the front end identical at every width measured.
- **Check it in the editor,** on one page per template: the content's root is constrained, each section spans the canvas, and a paragraph inserted at the root is `contentSize` wide. The standards audit fails on a `core/post-content` without a constrained layout.

### Layout recipes that replace CSS

Each was checked by box measurements against an original.

- **Shrink a block to its content** (a pill, or a heading whose gradient must span only its text): put it alone in a `core/group` row with centred justification. No `width: fit-content` rule. A gradient written with a corner keyword (`to top right`) takes its angle from the box, so it only matches when the box is the text.
- **A narrow paragraph in a wider column:** one constrained group with `contentSize` for the narrow child, and `wideSize` plus `alignwide` on the wider one, in place of a nested group.
- **Separate row and column gaps:** `blockGap` as an object (above), inside `@mobile` and `@tablet` too. The editor shows one control for a group, but the attribute validates and the layout prints both. This covers a row that stacks at a width the states cannot express: both gaps are simply set.
- **A centred child wider than its column:** a vertical flex group wraps by default (`flex-wrap: wrap`). In a wrapping container the cross axis is aligned per line and the line is as wide as its widest child, so a centred child wider than the group overflows on one side only. `"flexWrap": "nowrap"` makes it overflow evenly.
- **An image that must not shrink in a row:** the child layout value `selfStretch: "fixedNoShrink"` prints `flex-shrink: 0` with the flex basis. The older value `fixed` still shrinks.
- **A gradient border:** two nested groups. The outer has the gradient background, padding of the ring's width, the radius and the shadow; the inner has the fill and a radius smaller by the ring's width. When the original draws its ring outside the box, take the ring's width off the surrounding padding, add twice the width to the content size, and give the shadow a negative spread of that width.
- **A decoration layer** needs rules on the container and the layer only: `isolation: isolate` on the container and `z-index: -1` on an absolutely positioned first child put the layer over the container's background and under its content. Give the layer group a block gap of 0, because the flow layout's top margin shifts absolutely positioned children.
- **A decorative marker hung outside a row** is an image with a negative left margin and a right margin that cancels the row's gap. No positioning CSS.

### Layout traps (defaults that fight the design)

WordPress applies a default 24px flow gap wherever `blockGap` is unset; at page scale it shows up as ~25–35px of drift in the shared chrome. Handle these up front:

- **Root layout:** theme.json root `blockGap` applies via `.wp-site-blocks > * + *`, inserting a gap between the header part, `main`, and the footer on every page. Zero it with `.wp-site-blocks > header.wp-block-template-part + *, .wp-site-blocks > * + footer.wp-block-template-part { margin-block-start: 0; }`.
- **Template parts:** a part's root-level children each pick up `margin-block-start` from the default flow gap — zero margins on main/footer wrappers explicitly.
- **Stacked columns:** `core/columns` stacked at ≤781px inherit a 24px vertical gap. Set `blockGap.top` explicitly — a literal px value when the design's mobile gap differs from the preset's mobile remap.
- **Constrained-layout clamp:** a constrained parent clamps an oversized absolutely-positioned child (e.g. a decorative backdrop image wider than the content column) to content width, and the parent's `overflow: hidden` then crops it — give that child's figure `max-width: none`.
- **Wide and full alignment:** in a constrained group with a custom `contentSize` and no `wideSize`, `alignwide` resolves to the content size. `alignfull` inside a padded constrained group bleeds through the padding with negative margins.
- **Flex children:** a child's `flexSize` sets `flex-basis`, not width. Nowrap content wider than it widens the child unless `min-width` is 0. An image block in a nowrap flex row shrinks, because its `<img>` has `max-width: 100%` (use `fixedNoShrink`, above).
- **A control with a minimum width** inside a shrink-wrapped flex item is a floor for its whole column. Sweep every such view below that minimum plus its paddings, and decide explicitly whether to copy the overflow or fix it.
- **Scroll-driven entrances:** `animation-timeline: view()` measures against the nearest scroll container, which any ancestor with `overflow` set is. An entrance animation inside such an ancestor never runs.
- **Where two dark full-width blocks meet over a light page**, keep a 1px overlap. Without it a light hairline shows between them at a fractional scale. A source's `margin-bottom: -1px` on such a block is this guard, not a hack to drop.
- **A closed hover card or menu that is still laid out** widens a narrow page. Check sideways overflow at the narrowest width of every view (`visual-refinement.md`).

## Images

- **Media-library images carry `width` and `height` attributes.** WordPress adds both from the attachment to every `<img>` with a `wp-image-<id>` class. An image sized by height alone then takes its width from the attribute and renders squashed: give it `"width":"auto"` (`style="width:auto;height:…"`). The same file referenced from the theme has no attributes, so the fault only appears when an image moves into the library. For an SVG the attribute values are rounded, which can leave a sub-pixel difference in the computed width.
- **Images that point at theme files reserve no space.** WordPress prints the two attributes for media-library images only. An image block that points at a theme file is 0px tall until the file arrives, and everything after it moves when it loads. For such an image in the flow, set both dimensions or an `aspectRatio` on the block. The standards audit lists these for review.
- **Safe SVG reports an SVG's size from its `viewBox`,** not from the `width` and `height` the file declares, and `core/site-logo` and `core/image` derive their attributes from it. An icon drawn in a small `viewBox` reports that small size. Set the block's width explicitly and measure the result.
- **The logo** is `core/site-logo`. Its duotone setting recolours a single-colour logo (both stops the same colour), which covers a white-on-dark variant without a second file.
- **An image with only a width** gets `height:auto` from the validator, so write it that way from the start.
- **An image lower than the text line beside it** sits on the bottom of its figure's line box. Give it the line's height with `scale: contain`.
- **Decoration:** the image block has `isDecorative`, which prints `role="none"` and an empty alternative text.
- **A linked image that is inline sits on a text line.** When the original's `<a>` around an image is inline or inline-block inside a plain block, a few pixels of descender space hang under the image. `core/image`'s figure does not reproduce that, so a rebuilt stack of such images is shorter by that space per image, and in the original the space disappears wherever the wrapper becomes a flex container. Decide per case whether it is a defect to fix or rhythm to keep as explicit spacing, and record it.
- **Lazy loading is counted per page.** WordPress lazy-loads every content image after the third (`wp_omit_loading_attr_threshold` defaults to 3). Small icons, badges and images inside closed hover cards count, so the largest image of a first screen can come out `loading="lazy"`. It is not visible in a comparison; it costs loading time. Check and report it (`standards.md`).
- **Generated sizes can be heavier than the source.** The resized copies WordPress makes from an optimised PNG can be larger than the original. After importing design images, compare the generated sizes with the source, and note whether production serves images through a CDN that re-encodes them, in which case it does not matter.
- **Emoji become images** where the browser fails WordPress's newest-emoji test. Any content image rule (radius, display, margins) must exclude `img.emoji`.

## Buttons

- **Width.** `core/button` has no minimum width. On WordPress 7.1 its width is `style.dimensions.width` with any CSS length or dimension preset, not only the four percentages. It prints on the wrapper with `has-custom-width`, and a viewport state can override it. A fixed-width button, or a minimum the label never reaches, therefore needs no CSS. Only a minimum that the label can outgrow is a rule in a registered button style.
- **A fixed-width button gives way to a narrower column** only if its buttons block is as wide as the column. In a centred vertical group the buttons block shrink-wraps and overflows: set the group's justification to stretch and centre each buttons block.
- **Icons.** `core/button` has no icon, and the `core/html` policy rejects an SVG inside a link. Paint a decorative icon in a button label from the button's registered style (`block-styles-guide.md` § Icons in buttons).
- **Hover.** A background colour on one button silences the theme's hover background, whether it is an inline style or an `!important` preset class. A button with its own colour needs its own `:hover` state.
- **Accessible names.** `core/button` has no `aria-label` attribute. A link whose accessible name differs from its visible text (one that adds "opens in a new tab", say) cannot be carried over as it is. The choices are the visible label as the name, the `title` attribute, or a render filter. Ask at blueprint time.
- **A dynamic block's built-in button** (a comment form's submit, say) can be styled by attributes: `style.elements.button` on a block that declares no button colour support prints colour, background, border, typography, padding and shadow as one class rule, provided a colour path is set, which is what adds the element class. A flat border colour written as a preset reference is dropped there; `currentColor`, a raw colour or a per-side preset print.

## Links, headings and lists

- **A link colour on a block removes the theme's link hover** for every link inside it. The block's rule (`style.elements.link.color.text`) is printed as `.wp-elements-N a:where(…)` and outranks the theme's hover rule, which WordPress prints inside `:where()`. Give the block its own `:hover` colour if hover matters.
- **Taking the underline off the link inside one block** has no editor control: "None" as a heading's or paragraph's decoration applies to the block, and the link keeps the theme's link style. The attribute route exists: with a link colour set on the block, `style.elements.link.typography.textDecoration` beside it (and under `:hover`) is printed in the same rule.
- **`core/list` cannot drop its markers by attribute.** Its save function prints `list-style-type` for ordered lists only. A list without markers is a registered style.

### core/navigation notes

- `core/navigation-link` accepts `className` — registered block styles render on the `<li>`, enabling overlay-only items and bespoke glyphs (e.g. a CSS-mask external-link arrow) without a custom block.
- **Active state, portably:** core only sets `aria-current`/`current-menu-item` when the link carries a post `id` matching the queried object — which bakes site-specific IDs into the theme. Match on URL **path** instead via a `render_block_core/navigation-link` filter using `WP_HTML_Tag_Processor`; the active style then needs specificity above core's own nav-link colour rules. A current-item look is `theme.json` or CSS, never an attribute.
- **Logo/CTA in the mobile overlay:** nesting `core/site-logo`, fill spacers, and `core/buttons` *inside* `core/navigation` places them in the native mobile overlay for free — but the logo then disappears from the collapsed bar, so add a second compact-only site-logo (hidden by viewport, or gated by an `is-style-*` visibility variation on an older core) outside the nav. Pinning the overlay CTA to the bottom needs `flex-grow` on `.wp-block-navigation__responsive-close` **and** `__responsive-dialog`, not just `__responsive-container-content`.
- **With no overlay menu, the block's classes and inline styles print on both its `nav` and its `ul`.** A border or padding rule on `.wp-block-navigation.is-style-x` is drawn twice. Scope it to `nav.wp-block-navigation.is-style-x`.

## Query loops, archives and pagination

- **`core/post-template` is a `ul`.** A list in post content shown inside a query loop is a nested list to the browser (a circle marker), while the same content on the single view has a disc. A content style must set the marker, and the archive's rendering of content should be compared with the single's as well as with its original.
- **An element colour on a block inside a query loop is printed once per rendered post,** because element classes are numbered, not hashed like layout and state classes. Put link colours on `core/post-template`, which renders once and supports a link colour, or in a block style.
- **`core/query-pagination` has no spacing or border support.** Its rule and spacing belong in a style on the block itself, not on a wrapper group, because the block prints nothing for a single page and a wrapper would leave a stray rule. `display: contents` on the numbers container gives even gaps and per-number wrapping.
- **A template's whole output is texturised.** Text printed by a render filter or a dynamic block (a ` - ` in a label) gets typographic punctuation there, which `do_blocks()` in a test or a probe does not show. Write such a character as a character reference.
- **What a block can know about the view** is narrower than it looks: see `custom-blocks-guide.md` § What a block can know.

## Forms (Jetpack)

When the design includes a contact or newsletter form and Jetpack is available, `jetpack/contact-form` is the mapping (a one-field form covers newsletter signups):

- On local Studio sites the `contact-form` module works offline; the `subscriptions` module cannot activate without a WordPress.com connection — do not map newsletter signups to subscription blocks locally.
- Field blocks are **composed** (Jetpack Forms 16.x): a self-closing `<!-- wp:jetpack/field-email /-->` fails validation. The required shape is the field's wrapping `<div>` + `wp:jetpack/label` + `wp:jetpack/input` inner blocks.
- Any non-default `is-style-*` on `jetpack/contact-form` suppresses field labels (16.0.1) — apply `"className":"is-style-default is-style-<custom>"` together.

## File classification: template vs part vs page

For each HTML file in the set, decide its home:

- **Core template** — the file represents a WordPress view: blog index → `templates/index.html` (or `home.html`); a single post layout → `single.html`; an archive → `archive.html`; a 404 → `404.html`; a generic page layout → `page.html`. **Never `front-page.html`** — see the homepage rule below.
- **Shared-wrapper page content** — the file is an inner page (About, Services, Contact) that shares the same header/footer/wrapper as others and differs only in body content. The wrapper becomes a template (often `page.html`); the body becomes a **WordPress page** whose `post_content` is block markup, assigned to that template. The content lives in WordPress, not hardcoded in the template.
- **Template part** — markup that repeats across files unchanged (header, footer, nav, a CTA banner) → `parts/*.html`, referenced via `core/template-part`.

When two files share chrome but differ in body, extract the chrome **once** into parts and a shared template; never duplicate it per file.

**A recoloured copy of a part is a block style, not a second part.** `core/template-part` takes a `className`, so the template that needs the variant puts a registered style on the part (`block-styles-guide.md` § A second colour scheme for a template part).

### Where content lives (a blueprint decision, with a default)

**Default: nothing a visitor reads is held in a PHP pattern.** Content held in `patterns/*.php` and referenced from a part or a page is not editable where an editor expects it, and the theme's files no longer show what the site says.

- Parts and templates are plain block markup in `.html` files, editable in the Site Editor.
- Page content is written straight to the page.
- A section two pages share is repeated in each page's content. A synced pattern, which is a database post, would keep the copies in step; use one only when the user wants edit-once-update-everywhere.
- Translation functions are not used, which is what lets parts be plain HTML.

Put this in the blueprint as a decision the user confirms, because two kinds of project need a different answer:

- **Text in the chrome must be translatable**, or a part needs a theme-relative URL in its markup. That is what a PHP pattern is for: the part holds a `core/pattern` reference and the pattern file holds the markup. Say what it costs: that text is then edited in PHP, not in the Site Editor.
- **The user wants starter patterns** offered in the inserter. Register those as well as, never in place of, the content.

The consequence to state in every report: no page content is in the theme or the repository, so another environment gets its pages by a content migration.

### The homepage rule: no front-page.html

Never create `templates/front-page.html`. The homepage is **content, not a view**: build it as a WordPress page whose `post_content` is the block markup, then point WordPress at it through the Reading settings (`studio wp option update show_on_front page --path=<site-path>`, then `studio wp option update page_on_front <page-id> --path=<site-path>`). Choose its template by wrapper:

- Homepage shares the standard page chrome → the shared page template (`page.html` / `default`).
- Homepage has its own chrome (different or absent header/footer, full-viewport hero) → a **custom page template** (e.g. `templates/page-home.html`) registered in `theme.json` `customTemplates`, rendering the page's content via `core/post-content` with a constrained layout (§ Post content sits at content width). Its full-width sections are `alignfull` blocks in the page.

This keeps the homepage editable in WordPress like every other page instead of hardcoding its content in a template that shadows the page.

## Long-form and repeated content: generate it

- **Convert a text-heavy page with a script, not by hand.** Where the source is a flat run of paragraphs, headings and lists, a short script re-wraps each element in its block delimiters. It must refuse any element, class, attribute or inline style it does not recognise, and refuse to write unless the visible text of the result equals the visible text of the source. That guarantee matters for legal text, and it keeps tens of kilobytes of prose out of a builder's context.
- **For hand-written source markup,** walk the source as a tree and state, at each level, what is expected, refusing anything else. Cross-check what the page repeats: each contents link against its target's id and words, ids for duplicates, and every link's `href`, `target` and `rel` before and after. Test the refusals with tampered copies of the source: each must be refused with nothing written.
- **Two pages or templates of one design come from one generator,** with a table of what depends on the variant and a mode that prints the differences per named part. The two structures cannot drift apart, and a check mode fails when a file on disk no longer equals the source.
- **A page that is one template plus one run of text does not need a builder.** The orchestrator generates it, validates it, writes it and compares it.

## Asset routing

- **Fonts** → declare in `theme.json` `settings.typography.fontFamilies` with `fontFace` entries; copy the font files into `assets/fonts/`. Do not `@import` from a CDN. Which file draws which weight is measured, not read (`theme-json-guide.md` § Font faces).
- **Design images** (photos, illustrations, logos, icons, badges) → the media library, referenced as the editor writes them: the `id` attribute, the attachment URL and the `wp-image-<id>` class. An editor can then replace any of them, and no page points at a theme file. This is a blueprint decision with this default, because of what it brings:
  - **SVG needs the Safe SVG plugin**, which becomes a site dependency.
  - **The media travels with the content migration**, not with the deploy.
  - Keep one manifest for the run (`<site-path>/.h2bt/media.json`: file name → id, URL and dimensions) and have every builder take ids from it. Import with a script that can be run again: it finds an attachment by a source meta key before sideloading, turns off big-image scaling so originals are not resized, and prints a sentinel.
- **Images a template, part or stylesheet itself needs** stay in the theme's `assets/`. A theme `.html` file cannot point at a media item portably, because ids and URLs differ per environment, and it cannot build a theme URL without PHP.
  - Paint decoration from the block's stylesheet, where a relative URL resolves.
  - For a real `<img>` in a part, the choices are a root-relative theme path, which breaks if WordPress is served from a subdirectory, or a media item whose URL is fixed up after migration. Record which was chosen, and reserve the image's space (§ Images).
- **Linked CSS** → read it to extract tokens and per-class styling; it is design intent to be *translated*, not shipped. Do not enqueue the original stylesheet.
- **JS** → see below.

## JS / interactivity

Static JS in the design (sliders, accordions, mobile menus, scroll effects) has no home in static block markup. Route it by rung:

- **Core block already does it** → use the core block; drop the bespoke JS.
  - A mobile menu is `core/navigation`.
  - An accordion is `core/accordion` (with `core/accordion-item`, `core/accordion-heading` and `core/accordion-panel`; its `autoclose` attribute closes the other items) or a run of `core/details` blocks. Native `<details name="group">` (same `name` on siblings) gives one-open-at-a-time groups with zero JS — also usable inside a block's `render.php`. Choose by which markup is closer to the design's.
  - Tabs are `core/tabs`, which holds a `core/tab-list` and a `core/tab-panels` with one `core/tab-panel` per tab.
  - The accordion and tabs blocks are in WordPress 7.1. On an older core, check that the block exists before planning on it (§ Read the installed core, then probe).
- **Needs custom behaviour** → follow `custom-blocks-guide.md`. Try the Interactivity API on an existing block, a variation or a filter first; then a block reused from the blocks monorepo; and only then a new block built in the monorepo. This is the home the user wants for "functionality beyond core."
- **Purely decorative scroll/animation** → reproduce with CSS where cheap; otherwise drop it and note it in the report. Do not enqueue the original JS file wholesale.
- **Behaviour the blueprint puts out of scope** is built in its default, script-free state. An element a later script reveals is kept as a hidden block (`metadata.blockVisibility: false`, or a hidden style on an older core) so its design is not lost.

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
- **WordPress texturises content on output.** A straight apostrophe or quote in the stored text is shown as a typographic one, and a hyphen with a space on each side as an en dash. A design whose source shows straight quotes will differ by a fraction of a pixel per line. Record it as drift; do not turn texturising off for it.
- **A shared section is measured again in every host.** The same screen width gives a different column width when the host page adds its own padding, so a minimum width or a wrap that never bit on the first page can bite on the second.
