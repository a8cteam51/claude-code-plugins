# Custom blocks guide: build-less, in-theme

Custom blocks are rung 3 — used only for behaviour or markup core blocks cannot produce (JS interactions, dynamic/repeating structures). They are **build-less**: `block.json` + PHP render + vanilla `view.js` or the Interactivity API, registered from the theme. No `node_modules`, no webpack, no JSX compile step.

Scaffold the skeleton with:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold-custom-block.sh" --theme-dir "<theme-dir>" --slug "<slug>" --title "<Title>"
```

It writes `blocks/<slug>/` and ensures the theme registers it.

## When a custom block is justified

Build one only when **all lower rungs fail**:

- A core block plus supports cannot produce the markup or behaviour.
- It is not just styling (that is a block style variation, rung 2).
- The design genuinely needs interactivity (tabs, accordion not covered by `core/details`, carousel, filterable grid, counter) or a repeating dynamic structure.

Record the justification in the blueprint and the report. If in doubt, prefer a core block plus the Interactivity API on a `core/group` before inventing a block.

## File layout

```
blocks/<slug>/
├── block.json
├── render.php        # server-rendered front-end output (dynamic block)
├── index.js          # build-less editor registration (uses global wp, no JSX)
├── view.js           # front-end behaviour (vanilla) OR an Interactivity API module
└── style.css         # optional, minimal, scoped to the block
```

`block.json` (API v3, dynamic, build-less paths):

```json
{
  "$schema": "https://schemas.wp.org/trunk/block.json",
  "apiVersion": 3,
  "name": "theme/<slug>",
  "title": "<Title>",
  "category": "design",
  "icon": "screenoptions",
  "supports": { "html": false, "anchor": true, "align": ["wide", "full"] },
  "attributes": {},
  "editorScript": "file:./index.js",
  "viewScriptModule": "file:./view.js",
  "render": "file:./render.php",
  "style": "file:./style.css"
}
```

Use `viewScript` (classic script) for simple vanilla JS, or `viewScriptModule` when using the Interactivity API (WordPress provides the `@wordpress/interactivity` import map, so the ES module needs no bundling).

## render.php (front end)

```php
<?php
$wrapper = get_block_wrapper_attributes();
?>
<div <?php echo $wrapper; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>>
	<?php echo $content; // inner blocks, already safe ?>
</div>
```

Use `get_block_wrapper_attributes()` so `className`, `style`, and alignment from the editor land on the front-end wrapper — this keeps the block stylable through supports and block styles like any core block.

## index.js (editor, build-less)

No JSX, no imports — use the global `wp` packages WordPress already enqueues:

```js
( function ( blocks, blockEditor, element ) {
	var el = element.createElement;
	blocks.registerBlockType( 'theme/<slug>', {
		edit: function ( props ) {
			var blockProps = blockEditor.useBlockProps();
			return el(
				'div',
				blockProps,
				el( blockEditor.InnerBlocks, null )
			);
		},
		save: function () {
			return el( blockEditor.InnerBlocks.Content, null );
		},
	} );
} )( window.wp.blocks, window.wp.blockEditor, window.wp.element );
```

For blocks with no inner content, render a static editor preview or use `window.wp.serverSideRender` for a live PHP preview. Keep the editor representation simple — fidelity is a front-end concern.

## Interactivity (the front-end behaviour)

Prefer the **Interactivity API** for state-driven UI. Add directives in `render.php`:

```php
<div
	data-wp-interactive="theme/<slug>"
	data-wp-context='{ "open": false }'
>
	<button data-wp-on--click="actions.toggle" data-wp-bind--aria-expanded="context.open">Toggle</button>
	<div data-wp-bind--hidden="!context.open"><?php echo $content; ?></div>
</div>
```

`view.js` as an ES module (loaded via `viewScriptModule`, no build):

```js
import { store, getContext } from '@wordpress/interactivity';

store( 'theme/<slug>', {
	actions: {
		toggle() {
			const ctx = getContext();
			ctx.open = ! ctx.open;
		},
	},
} );
```

For trivial behaviour with no shared state, a plain vanilla `view.js` (`document.querySelectorAll(...).addEventListener(...)`) registered as `viewScript` is fine. Do not enqueue the design's original JS file wholesale — reproduce the behaviour.

## Dynamic content from meta (bindings before blocks)

For meta-driven text, exhaust these before writing a custom block — they keep the content in core blocks:

- **Block Bindings** connect a core block's attribute to post meta with no custom block at all. For *formatted* meta (a composed "year • publisher" line, a bespoke date form), register a custom source with `register_block_bindings_source()` and do the formatting in its callback.
- A paragraph bound to empty meta still renders an empty `<p>` — pair each bound optional field with a scoped `:empty { display: none; }` rule in the relevant block CSS file.
- Sitewide date formatting belongs in a `render_block_core/post-date` filter, not per-instance markup.
- When a custom block *is* justified for meta-driven output, `window.wp.serverSideRender` (see `index.js` above) gives a live PHP-rendered editor preview with no build step.

## Registering from the theme

The scaffold script ensures `functions.php` registers every block directory:

```php
add_action( 'init', function () {
	foreach ( glob( get_stylesheet_directory() . '/blocks/*', GLOB_ONLYDIR ) as $dir ) {
		register_block_type( $dir );
	}
} );
```

## Discipline

- One block per genuine behaviour. Do not create a block for styling.
- Keep `style.css` scoped to the block's wrapper class and minimal; it counts toward the custom-CSS footprint.
- Inputs/outputs stay block-native: style through supports and block styles, not bespoke CSS, wherever the wrapper attributes allow.
