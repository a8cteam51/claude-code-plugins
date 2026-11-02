# Block styles guide: custom classes → block style variations

When a recurring custom CSS class adds styling that block supports cannot express (rung 2 of the ladder), register it as a **block style variation** rather than writing loose, global CSS. Variations are selectable in the editor, scoped to specific block types, and apply via an `is-style-<slug>` class.

This skill registers variations in **`functions.php` with `register_block_style()`**, and ships each block type's CSS as **its own file** loaded on demand with **`wp_enqueue_block_style()`**. There is no monolithic theme stylesheet and no `/styles/*.json` block-style files — one readable CSS file per block type, loaded only when that block is on the page.

**Template mode** (an a8csp-project-template repository; see `project-template-guide.md`) keeps every rule in this guide but changes the locations:
- Each block type's stylesheet source is `assets/sass/blocks/<block-name>.scss`, built to `assets/css/blocks/<block-name>.css` (`project-template-guide.md` § Build pipeline points the template's scripts there).
- **Write the Sass nested**, the root partials in `assets/sass/` as well as the block stylesheets in `assets/sass/blocks/`. Give each block style, or the block's own rules, one parent rule, and nest inside it what belongs to it: its states (`&:hover`, `&:focus-visible`), its children (`> .wp-block-cover__inner-container`), its descendants (`a`), a context that wraps it (`body:not(.editor-styles-wrapper) & a::after`) and its breakpoints (`@include breakpoint-down( mobile )`). Don't repeat the full selector rule after rule. Nest in the order the flat rules would cascade: where a parent's rules are split by another rule with the same specificity that can match the same element, keep them apart. To nest Sass that was written flat, save the compiled CSS first and check that after the change it is the same, rule for rule and in the same order, once whitespace and comments are set aside.
- **Check what Sass arithmetic in pixels compiles to.** `math.div(18px * 5, 24)` compiles to `3.75px`, a fraction of a pixel (`mapping-guide.md` § Pixel values are whole pixels), and nothing flags it while the Sass is written. The standards audit finds it in a built block stylesheet. It does not read the root `style.css` that the partials build, so a fraction from arithmetic in a partial is found only by reading that file. Tried with the audit of 0.8.2 on a fixture theme in this layout. An icon drawn from such arithmetic is drawn in `em` instead (§ Icons in buttons).
- `register_block_style()` and `wp_enqueue_block_style()` live in `includes/block-styles.php`, not `functions.php`. They enqueue the **build** path and name each `.css` file literally.
- Handles are `<theme_slug>-block-<block-name>`, and the text domain is the theme slug.
- The standards audit detects this layout by itself.

## The rule: one CSS file per block type

- All custom CSS for a block type lives in **one file**: `assets/css/blocks/<block-name>.css`, where the block name's `/` becomes `-` (`core/button` → `assets/css/blocks/core-button.css`, `core/group` → `core-group.css`, the monorepo's `a8csp/modal` → `a8csp-modal.css`). Blocks reused or built from the blocks monorepo are styled from the theme this way too; they ship only wireframe styling (`custom-blocks-guide.md`).
- That one file holds **every** custom rule for the block — general block tweaks and the rules for **all** of its `is-style-*` variations. Do not split one block type across files; do not merge multiple block types into one file.
- Enqueue each file with `wp_enqueue_block_style( '<block-name>', … )` so WordPress loads it **only when that block renders** on the page. Never `wp_enqueue_style()` a global stylesheet for block CSS.

## Register the variation, ship the file, enqueue it

Three pieces in `functions.php`, all on `init`:

1. `register_block_style()` — registers the editor-selectable variation (name + label) for a block type.
2. The CSS for that variation goes in the block type's file under `assets/css/blocks/`, scoped to `.is-style-<slug>`.
3. `wp_enqueue_block_style()` — registers + conditionally enqueues that file for the block type.

`functions.php`:

```php
add_action( 'init', function () {
	$ver = wp_get_theme()->get( 'Version' );

	// One on-demand stylesheet per block type that carries custom CSS.
	wp_enqueue_block_style(
		'core/button',
		array(
			'handle' => 'theme-block-core-button',
			'src'    => get_theme_file_uri( 'assets/css/blocks/core-button.css' ),
			'path'   => get_theme_file_path( 'assets/css/blocks/core-button.css' ),
			'ver'    => $ver,
		)
	);

	// The editor-selectable variation(s) whose rules live in that file.
	register_block_style(
		'core/button',
		array(
			'name'  => 'ghost',
			'label' => __( 'Ghost', 'theme-textdomain' ),
		)
	);
} );
```

`assets/css/blocks/core-button.css`:

```css
.wp-block-button.is-style-ghost .wp-block-button__link {
	background: transparent;
	border: 1px solid var(--wp--preset--color--contrast);
}
```

Notes:

- `handle` must be unique — name it `theme-block-<block-name>` so files and handles map 1:1.
- **Enqueue each file literally, not via a glob loop.** The standards audit statically greps `functions.php` for each CSS file's basename **including the `.css` suffix** (`core-button.css`); a glob-based `wp_enqueue_block_style()` loop works at runtime but fails the audit, as does an enqueue map whose values omit `.css`.
- Always pass `path` alongside `src`. It is what lets WordPress scope loading to pages where the block is present (and inline the file when appropriate). Without it the conditional loading benefit is lost.
- `register_block_style()` only registers the variation's name and label — it does **not** carry styling. The look comes entirely from the block type's CSS file. (This is why every variation here is CSS-backed; the declarative `/styles/*.json` block-style mechanism is not used.)
- Pull values from `var(--wp--preset--…)` so the CSS stays token-driven; never hard-code a value that already exists as a `theme.json` token.

## Variation rules

- **Selector must start with `.is-style-<slug>`** (or the block wrapper + that class). Never style by the original design class name.
- **Check the block emits a wrapper class before scoping to it.** A block whose `block.json` sets `"className": false` saves no `wp-block-<name>` class. `core/paragraph` is the one that matters: WordPress 7.0 and later add `wp-block-paragraph` when the paragraph renders on the front end, but earlier versions never do, so there `.wp-block-paragraph.is-style-x` matches nothing. Scope paragraph variations as element + class (`p.is-style-x`), which matches on every version.
- One concern per variation; one slug per recurring design class. Choose slugs from design intent (`elevated`, `ghost`, `inverted`, `bordered`), not the original class string.
- **A class never stands in for a block setting.** A font family, font size, colour, spacing or alignment the editor has a control for is the block's attribute (rung 1): the control then shows the value, and an editor can change it there. A design's helper class for a second font is a `fontFamily` preset, not a class and not a variation. A preset class written into the markup without its attribute (`has-display-font-family` with no `fontFamily`) still validates; the editor then lists it under Additional CSS class(es) and its typography control stays empty. The standards audit fails on a `has-*` class in `className`, on a font family or font size class with no attribute behind it, and on a `className` the theme's stylesheets select that is not a registered style (`class_hooks`).
- Apply a variation in block markup with the class and the attribute:

  ```html
  <!-- wp:button {"className":"is-style-ghost"} -->
  <div class="wp-block-button is-style-ghost"><a class="wp-block-button__link wp-element-button">…</a></div>
  <!-- /wp:button -->
  ```

- Map one design class to one variation and reuse it everywhere that class appeared. Do not create variations for one-off styling — push that onto the block instance's `style`, or accept it as documented custom CSS (rung 4) if truly unavoidable.

## Section styles (a variation that restyles inner blocks)

A variation on a container (`core/group`, `core/cover`) can restyle the blocks nested inside it — e.g. an inverted/dark band that recolours its headings, paragraphs, and buttons. Register it the same way and put the descendant rules in the container's file:

`assets/css/blocks/core-group.css`:

```css
.wp-block-group.is-style-inverted {
	background-color: var(--wp--preset--color--contrast);
	color: var(--wp--preset--color--base);
}
.wp-block-group.is-style-inverted :where(.wp-block-heading) {
	color: var(--wp--preset--color--base);
}
.wp-block-group.is-style-inverted .wp-block-button__link {
	background-color: var(--wp--preset--color--base);
	color: var(--wp--preset--color--contrast);
}
```

Keep these scoped under `.is-style-<slug>` and token-driven. Because the file is enqueued for `core/group`, the rules load only on pages that use a group.

## Block CSS that is not a variation

Some block types need a little custom CSS that is not an editor-selectable variation (a tweak block supports cannot reach). It follows the same rule: put it in that block type's `assets/css/blocks/<block-name>.css`, enqueued with `wp_enqueue_block_style()` (no `register_block_style()` call needed when there is no selectable variation). This is rung 4 and is reported. Do not invent a fake variation just to hold it, and do not drop it into a global stylesheet.

### Direct block targeting or block style? The decision rule

Rung-4 structural CSS may target **block selectors directly** — the block's own wrapper classes and contextual combinators:

```css
header.wp-block-template-part > .wp-block-group { position: relative; }
header.wp-block-template-part nav.wp-block-navigation { position: absolute; inset-inline-end: 0; }
.wp-block-group > footer.wp-block-template-part { margin-top: auto; }
```

When structure alone identifies the target (there is one header part, one footer part, one cover on that template), no class hook is needed and none should be invented.

The moment a rule needs a **custom class as a CSS hook** to disambiguate ("this group, not the others"), that hook must be a **registered block style**: `register_block_style()` in `functions.php`, applied as `is-style-<slug>`, CSS in the block type's file. Never ship an unregistered bespoke className as a CSS hook — if it is worth a class, it is worth a registration the editor can see. This includes structural/responsive utilities (`is-style-pull-up`, `is-style-hide-below-1024`, `is-style-full-width-below-640`) and variations that restyle a block's inner markup (e.g. swapping a social icon's glyph via mask) — behaviour stays in the block; the variation only restyles it.

**Check the viewport states before registering a responsive utility.** On WordPress 7.1 and later, hiding a block, restacking a row or changing one value at either of the theme's two breakpoints is a block attribute (`mapping-guide.md` § Per-viewport values). A hide-below or stack-below variation is only for a width that is not a viewport state, or for an older core.

Scoping rules either way:

- Never emit an `is-style-*` class that has no `register_block_style()` registration behind it.
- Never style the design's original class names — name variations by intent.
- Keep every rule token-driven (`var(--wp--preset--…)`) and listed in the report.

## Recipes and traps

### A property that steps at a width the viewport states cannot express

Put **every** value of that property in the registered style and leave the block's attribute unset. An attribute prints an inline style, which a media query cannot beat without `!important`, so a base value in the attribute and its steps in CSS is the combination that forces `!important` (`mapping-guide.md` § A value that steps at another width).

### Breakpoints in a block stylesheet

Whole pixels only (`mapping-guide.md` § Pixel values are whole pixels):

- A rule that must switch together with one of the two viewport states uses the state's bound from `settings.viewport`: `@media (max-width: 767px)`. Keep those bounds in one place, such as a Sass map, so that a stylesheet and `theme.json` cannot disagree.
- The other side of a design's `min-width: N` rule is `@media (width < N)`, never `(max-width: N - 0.02px)`. With `(max-width: N - 1px)` beside a `(min-width: N)` rule, neither applies at a fractional width between the two.
- A design's own `max-width: N` rule stays `@media (max-width: N)`.

### Gradient text

- **A gradient preset class needs `!important` to be clipped to text.** `has-<slug>-gradient-background` sets the `background` shorthand with `!important`, which resets `background-clip`. A gradient-text style therefore needs `background-clip: text !important` with `color: transparent`. Without it the block renders as a solid gradient bar.
- **Gradient text on a button that keeps its fill** has no support. Use two background layers: `background-image: <gradient>, none; background-clip: text, border-box`. The gradient spans the button, not the label, so pull its stops in to the label's share of the width. Checked in Chrome only.

### Icons in buttons

An icon on its own is a `core/icon` block on WordPress 7.1 and later (`mapping-guide.md` § Icons). `core/button` has no icon, and the `core/html` policy rejects an SVG inside a link. Paint a decorative icon in a button from the button's registered style: a `::before` on the link, sized like the icon, with `background: currentcolor`, the SVG as a `mask` data URI, and a flex link with a gap. No image file, and the icon follows the label colour.

- **Which flex depends on the original.** Where the original control is block-level, use `display: flex`: an `inline-flex` link sits on a text line of its wrapper and grows the block by a pixel. Where it is an inline box inside running text, keep `inline-flex`, because its line is part of the rhythm.
- **A hover moves the icon, never the box.** Widening an arrow button's gap on hover made the button 4px wider, which moved right-aligned and centred buttons. Slide the icon alone with `translate`. A text link whose arrow grows on hover takes the growth back with a negative margin on the arrow, so its box keeps its size. Measured before and after, at desktop width. The transition sits under `prefers-reduced-motion: no-preference` (`standards.md` § Accessibility).
- **An icon shaped by lengths from its viewBox is drawn in `em`, off a font size of its own.** An arrow that lengthens on hover is two mask layers: a head, and a shaft whose inset and stroke are the viewBox's values scaled to the icon. In px those can come out as fractions of a pixel, which the audit fails on (`subpixel_values`). Give the pseudo-element the icon's size as its `font-size`, and write every length of the drawing in `em`: a `1em` box and head, each viewBox value as its share (`math.div(5em, 24)` in Sass, `calc(5em / 24)` in CSS), and the hover growth with the margin that cancels it. They compute to the same lengths. Converting only the fractions leaves an `em` shaft in a px box: text-only zoom grows the font size and no px length, so the shaft stops short of the head, and a growth left in px stays the same while the arrow scales. Use the icon's own size, not a font-size preset that equals it at one width: a preset can change at a breakpoint. An icon that is one mask with `contain` in a whole-pixel box has no fractions and stays in px. In one build the `em` arrow rendered the same pixels as the px one in Chrome at rest, on hover and through the transition, and at default settings in Safari and Firefox. What text-only zoom does to it is derived from the units, not measured.
- **A control drawn only by a masked icon disappears in forced-colors mode.** The browser replaces backgrounds there, and the icon is one. Inside `@media (forced-colors: active)`, give the icon `forced-color-adjust: none` and a system colour such as `buttontext`, and give the control a border. Derived from how forced colours treat backgrounds, and fixed on one control; not measured across browsers.
- **A glyph the font has** can be printed as generated text instead. It is then part of the control's accessible name unless written `content: "x"; content: "x" / "";`.
- **Sass turns a CSS escape into the character** and adds `@charset` to the built file unless the value is wrapped in `string.unquote()`.

### A second colour scheme for a template part

`core/template-part` has `className` among its attributes and prints the block wrapper attributes, so a registered block style can be put on a part from the template that includes it. A recoloured variant of a shared part (a dark footer on one template, say) is then a style, not a copy of the part.

- The style redefines, on the wrapper, the `--wp--preset--color--<slug>` properties the part's blocks use. Preset classes are `!important` but read the variable where the block is, so no selector on the part's inner blocks is needed.
- A fill is removed by setting its preset to `transparent` and painting the wrapper.
- **Not reached this way:** a custom colour (an inline style: set the colour on the children that inherit it), a duotone filter (override the printed duotone rule with one more class), and hover rules written against a fixed preset.
- **Costs:** that block type's stylesheet loads on every page, and a block later given a custom colour stops following the style. The editor's style picker for a part was not exercised.

### Selectors that surprise

These are stated where the block is mapped; a stylesheet has to honour them:

- `core/navigation` with no overlay menu prints its classes on both `nav` and `ul`: scope to `nav.wp-block-navigation.is-style-x` (`mapping-guide.md` § core/navigation notes).
- A content image rule must exclude `img.emoji` (§ Images).
- A link colour set on a block removes the theme's link hover inside it, and a background colour on one button removes the theme's button hover (§ Links, headings and lists; § Buttons).
- `core/query-pagination` is styled on the block itself, never on a wrapper (§ Query loops, archives and pagination).
- A list inside a query loop is a nested list, with a different default marker (same section).
- `core/breadcrumbs` draws its separator as `.wp-block-breadcrumbs li:not(:last-child)::after` (margin `0 0.5em`, opacity `.7`, 7.1.3). The same selector in the theme only ties with core's, so stylesheet order decides: write `nav.wp-block-breadcrumbs li:not(:last-child)::after`. The separator character is the `--separator` property the block prints inline.

## Discipline

- One CSS file per block type; no monolithic stylesheet; each file enqueued with `wp_enqueue_block_style()`.
- Registration, the CSS file, and the enqueue stay in sync: if a block type has a file under `assets/css/blocks/`, `functions.php` must `wp_enqueue_block_style()` it. The standards audit fails when a block CSS file is not enqueued this way.
- Every line of block CSS is reported as part of the custom-CSS footprint (`scripts/standards-audit.sh` lists each file).
