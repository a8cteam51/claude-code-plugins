#!/usr/bin/env bash
#
# scaffold-custom-block.sh — write a build-less custom block skeleton into a block
# theme and ensure the theme registers it. No node/webpack: block.json points at
# render.php (dynamic), index.js (editor, global wp / no JSX), and view.js.
#
# Usage:
#   scaffold-custom-block.sh --theme-dir <dir> --slug <slug> --title "<Title>" [--namespace <ns>]
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  scaffold-custom-block.sh --theme-dir <dir> --slug <slug> --title "<Title>" [--namespace <ns>]

Creates <theme-dir>/blocks/<slug>/{block.json,render.php,index.js,view.js,style.css}
and ensures <theme-dir>/functions.php registers every block in blocks/* on init.
Namespace defaults to "theme". Refuses to overwrite an existing block directory.
EOF
}

theme_dir=""
slug=""
title=""
namespace="theme"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--theme-dir) theme_dir="${2:-}"; shift 2 ;;
		--slug) slug="${2:-}"; shift 2 ;;
		--title) title="${2:-}"; shift 2 ;;
		--namespace) namespace="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$theme_dir" ]] || { echo "--theme-dir is required" >&2; exit 2; }
[[ -n "$slug" ]] || { echo "--slug is required" >&2; exit 2; }
[[ -n "$title" ]] || { echo "--title is required" >&2; exit 2; }
[[ -d "$theme_dir" ]] || { echo "Theme directory not found: $theme_dir" >&2; exit 1; }
[[ "$slug" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Slug must be lowercase alphanumeric + hyphens: $slug" >&2; exit 1; }
[[ "$namespace" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Namespace must be lowercase alphanumeric + hyphens: $namespace" >&2; exit 1; }

block_dir="$theme_dir/blocks/$slug"
[[ -e "$block_dir" ]] && { echo "Block already exists: $block_dir" >&2; exit 1; }
mkdir -p "$block_dir"

cat >"$block_dir/block.json" <<EOF
{
	"\$schema": "https://schemas.wp.org/trunk/block.json",
	"apiVersion": 3,
	"name": "${namespace}/${slug}",
	"title": "${title}",
	"category": "design",
	"icon": "screenoptions",
	"supports": { "html": false, "anchor": true, "align": ["wide", "full"] },
	"attributes": {},
	"editorScript": "file:./index.js",
	"viewScriptModule": "file:./view.js",
	"render": "file:./render.php",
	"style": "file:./style.css"
}
EOF

cat >"$block_dir/render.php" <<'EOF'
<?php
/**
 * Server-rendered output for the block. $attributes, $content, $block are in scope.
 */

$wrapper_attributes = get_block_wrapper_attributes();
?>
<div <?php echo $wrapper_attributes; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?>>
	<?php echo $content; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- InnerBlocks content, sanitized on save ?>
</div>
EOF

cat >"$block_dir/index.js" <<EOF
( function ( blocks, blockEditor, element ) {
	var el = element.createElement;
	blocks.registerBlockType( '${namespace}/${slug}', {
		edit: function () {
			var blockProps = blockEditor.useBlockProps();
			return el( 'div', blockProps, el( blockEditor.InnerBlocks, null ) );
		},
		save: function () {
			return el( blockEditor.InnerBlocks.Content, null );
		},
	} );
} )( window.wp.blocks, window.wp.blockEditor, window.wp.element );
EOF

cat >"$block_dir/view.js" <<EOF
import { store, getContext } from '@wordpress/interactivity';

store( '${namespace}/${slug}', {
	actions: {},
	callbacks: {},
} );
EOF

# Start empty — add scoped rules only when a real style is unavoidable (ladder rung 4).
: >"$block_dir/style.css"

functions="$theme_dir/functions.php"
register_marker="h2bt_register_theme_blocks"

read -r -d '' register_snippet <<'EOF' || true

if ( ! function_exists( 'h2bt_register_theme_blocks' ) ) {
	/**
	 * Register every build-less block in the theme's blocks/ directory.
	 */
	function h2bt_register_theme_blocks() {
		foreach ( glob( get_stylesheet_directory() . '/blocks/*', GLOB_ONLYDIR ) as $block_dir ) {
			register_block_type( $block_dir );
		}
	}
	add_action( 'init', 'h2bt_register_theme_blocks' );
}
EOF

if [[ ! -f "$functions" ]]; then
	{ echo "<?php"; echo "$register_snippet"; } >"$functions"
	echo "==> created functions.php with block registration"
elif ! grep -q "$register_marker" "$functions"; then
	printf '%s\n' "$register_snippet" >>"$functions"
	echo "==> appended block registration to functions.php"
else
	echo "==> functions.php already registers theme blocks"
fi

echo "H2BT_BLOCK_OK slug=${slug} dir=${block_dir}"
