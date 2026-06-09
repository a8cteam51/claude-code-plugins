# Block styles guide: custom classes → block style variations

When a recurring custom CSS class adds styling that block supports cannot express (rung 2 of the ladder), register it as a **block style variation** rather than writing loose CSS. Variations are selectable in the editor, scoped to specific block types, and apply via an `is-style-<slug>` class.

This is the mechanism the brief calls "block styles registered by their own JSON files."

## Preferred: declarative variations in `/styles/*.json` (WP 6.6+)

Drop a partial `theme.json`-format file in the theme's `/styles` directory. WordPress auto-registers it as a block style variation for the listed block types.

`styles/elevated.json`:

```json
{
  "$schema": "https://schemas.wp.org/trunk/theme.json",
  "version": 3,
  "slug": "elevated",
  "title": "Elevated",
  "blockTypes": ["core/group", "core/column"],
  "styles": {
    "border": { "radius": "12px" },
    "shadow": "var:preset|shadow|natural",
    "spacing": { "padding": "var:preset|spacing|40" },
    "color": { "background": "var:preset|color|base" }
  }
}
```

- `slug` → the `is-style-elevated` class. `title` → the editor label.
- `blockTypes` scopes which blocks offer it.
- `styles` accepts the same property tree as `theme.json` `styles` (colour, spacing, border, shadow, typography, and nested `elements`). It carries **theme.json properties only** — no arbitrary CSS selectors. Pull from presets so the variation stays token-driven.

Apply it in block markup by adding the class and (for clarity) the attribute:

```html
<!-- wp:group {"className":"is-style-elevated"} -->
<div class="wp-block-group is-style-elevated">…</div>
<!-- /wp:group -->
```

Map one design class to one variation: `.card--elevated` → `elevated` variation on `core/group`/`core/column`. Reuse the same variation everywhere that class appeared.

## When a variation needs real CSS

If the effect needs something theme.json properties can't carry (a pseudo-element, a gradient overlay, a hover transition), register the style in PHP and ship a **minimal, tightly scoped** stylesheet. This is still rung 2 — keep it small and report it.

`functions.php`:

```php
add_action( 'init', function () {
	register_block_style(
		'core/button',
		array(
			'name'  => 'ghost',
			'label' => __( 'Ghost', 'theme-textdomain' ),
		)
	);
} );
```

Then scope the CSS to the generated class only, in the theme stylesheet or a small enqueued file:

```css
.wp-block-button.is-style-ghost .wp-block-button__link {
	background: transparent;
	border: 1px solid currentColor;
}
```

Rules:

- Selector must start with `.is-style-<slug>` (or the block's wrapper + that class). Never style by the original design class name.
- One concern per variation. Do not bundle unrelated rules.
- Prefer `var(--wp--preset--…)` custom properties in the CSS so values still come from `theme.json`.

## Section styles (variations that restyle inner blocks)

A variation can also restyle the blocks nested inside it (a "section style") via nested `styles.blocks` / `styles.elements` in the `/styles/*.json` file. Use this for design "themes" applied to a whole section — e.g. an inverted/dark band that recolours its headings, paragraphs, and buttons:

```json
{
  "version": 3,
  "slug": "inverted",
  "title": "Inverted",
  "blockTypes": ["core/group", "core/cover"],
  "styles": {
    "color": { "background": "var:preset|color|contrast", "text": "var:preset|color|base" },
    "elements": {
      "heading": { "color": { "text": "var:preset|color|base" } },
      "button":  { "color": { "background": "var:preset|color|base", "text": "var:preset|color|contrast" } }
    }
  }
}
```

This replaces what would otherwise be a block of descendant-selector CSS with one declarative file.

## Discipline

- One variation per recurring custom class. Do not create variations for one-off styling — push that onto the block instance's `style`, or accept it as documented custom CSS (rung 4) if truly unavoidable.
- Slugs are stable identifiers; choose them from the design's intent (`elevated`, `ghost`, `inverted`, `bordered`), not the original class string.
- Every variation that ships real CSS (not just declarative properties) is reported as part of the custom-CSS footprint.
