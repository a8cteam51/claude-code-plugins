# Block styles guide: custom classes → block style variations

When a recurring custom CSS class adds styling that block supports cannot express (rung 2 of the ladder), register it as a **block style variation** rather than writing loose, global CSS. Variations are selectable in the editor, scoped to specific block types, and apply via an `is-style-<slug>` class.

This skill registers variations in **`functions.php` with `register_block_style()`**, and ships each block type's CSS as **its own file** loaded on demand with **`wp_enqueue_block_style()`**. There is no monolithic theme stylesheet and no `/styles/*.json` block-style files — one readable CSS file per block type, loaded only when that block is on the page.

## The rule: one CSS file per block type

- All custom CSS for a block type lives in **one file**: `assets/css/blocks/<block-name>.css`, where the block name's `/` becomes `-` (`core/button` → `assets/css/blocks/core-button.css`, `core/group` → `core-group.css`, `mytheme/hero` → `mytheme-hero.css`).
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
- Always pass `path` alongside `src`. It is what lets WordPress scope loading to pages where the block is present (and inline the file when appropriate). Without it the conditional loading benefit is lost.
- `register_block_style()` only registers the variation's name and label — it does **not** carry styling. The look comes entirely from the block type's CSS file. (This is why every variation here is CSS-backed; the declarative `/styles/*.json` block-style mechanism is not used.)
- Pull values from `var(--wp--preset--…)` so the CSS stays token-driven; never hard-code a value that already exists as a `theme.json` token.

## Variation rules

- **Selector must start with `.is-style-<slug>`** (or the block wrapper + that class). Never style by the original design class name.
- One concern per variation; one slug per recurring design class. Choose slugs from design intent (`elevated`, `ghost`, `inverted`, `bordered`), not the original class string.
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

Some block types need a little custom CSS that is not an editor-selectable variation (a tweak block supports cannot reach). It follows the same rule: put it in that block type's `assets/css/blocks/<block-name>.css`, scoped to the block wrapper, enqueued with `wp_enqueue_block_style()` (no `register_block_style()` call needed when there is no selectable variation). This is rung 4 and is reported. Do not invent a fake variation just to hold it, and do not drop it into a global stylesheet.

## Discipline

- One CSS file per block type; no monolithic stylesheet; each file enqueued with `wp_enqueue_block_style()`.
- Registration, the CSS file, and the enqueue stay in sync: if a block type has a file under `assets/css/blocks/`, `functions.php` must `wp_enqueue_block_style()` it. The standards audit fails when a block CSS file is not enqueued this way.
- Every line of block CSS is reported as part of the custom-CSS footprint (`scripts/standards-audit.sh` lists each file).
