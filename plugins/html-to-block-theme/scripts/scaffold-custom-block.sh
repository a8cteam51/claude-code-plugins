#!/usr/bin/env bash
#
# scaffold-custom-block.sh — write a custom block skeleton and make sure it gets registered.
#
# Standalone layout (default): a build-less block in the theme. No node/webpack: block.json
# points at render.php (dynamic), index.js (editor, global wp / no JSX), and view.js.
#
# Template layout (--layout template): an a8csp-project-template repository. The block's
# sources go in the features mu-plugin under blocks/src/<slug>/ (ES modules + JSX, strict-types
# render.php), built by wp-scripts into blocks/build/ with a blocks manifest; the script also
# wires the manifest registration, the package.json build/lint scripts, and the
# .github/blocks-allowlist entries CI requires.
#
# Usage:
#   scaffold-custom-block.sh --theme-dir <dir> --slug <slug> --title "<Title>" [--namespace <ns>]
#   scaffold-custom-block.sh --layout template --features-dir <dir> --slug <slug> --title "<Title>" \
#       --namespace <theme-slug> [--prefix <php_prefix_>]
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  scaffold-custom-block.sh --theme-dir <dir> --slug <slug> --title "<Title>" [--namespace <ns>]
  scaffold-custom-block.sh --layout template --features-dir <dir> --slug <slug> --title "<Title>" \
      --namespace <theme-slug> [--prefix <php_prefix_>]

Standalone: creates <theme-dir>/blocks/<slug>/{block.json,render.php,index.js,view.js,style.css}
and ensures <theme-dir>/functions.php registers every block in blocks/* on init.
Namespace defaults to "theme".

Template: creates <features-dir>/blocks/src/<slug>/{block.json,index.js,render.php}, adds
includes/blocks.php (manifest registration) if missing, adds the build:features:blocks and
start:features:blocks npm scripts and the blocks/src lint paths when missing, and lists the
block's src and build block.json in .github/blocks-allowlist. --prefix defaults to the one in
the theme's .phpcs.xml. Build with `npm run build:features:blocks`.

Refuses to overwrite an existing block directory.
EOF
}

# --- Template layout ----------------------------------------------------------------------

# Header value from a WordPress file header (`Text Domain:`, `@package`).
file_header() { # file_header <file> <name>
	sed -n "s/^[[:space:]*]*$2:*[[:space:]]*//p" "$1" 2>/dev/null | head -1 | tr -d '\r'
}

scaffold_template_block() {
	features_dir="$(cd "$features_dir" && pwd -P)"
	local features_slug repo entry text_domain package const_path block_dir
	features_slug="$(basename "$features_dir")"
	repo="$(cd "$features_dir/../.." && pwd -P)"
	entry="$(grep -l 'Plugin Name:' "$features_dir"/*.php | head -1)"
	[[ -n "$entry" ]] || { echo "No plugin entry file (Plugin Name header) in $features_dir" >&2; return 1; }
	text_domain="$(file_header "$entry" 'Text Domain')"
	package="$(file_header "$entry" '@package')"
	const_path="$(grep -oE "define\( '[A-Z0-9_]+_DIR_PATH'" "$entry" | head -1 | sed -E "s/define\( '([A-Z0-9_]+)'/\1/")"
	if [[ -z "$prefix" ]]; then
		prefix="$(python3 - "$repo" <<'PY'
import glob, re, sys
for f in glob.glob(sys.argv[1] + '/themes/*/.phpcs.xml'):
    m = re.search(r'name="prefixes".*?<element value="([^"]+)"', open(f).read(), re.S)
    if m:
        print(m.group(1))
        break
PY
)"
	fi
	[[ -n "$prefix" ]] || { echo "Could not read the PHP prefix; pass --prefix" >&2; return 1; }
	[[ -n "$const_path" ]] || { echo "Could not find the features plugin's *_DIR_PATH constant in $entry" >&2; return 1; }
	local fn_prefix="${prefix}features_"
	local var_prefix
	var_prefix="${fn_prefix}$(printf '%s' "$slug" | tr '-' '_')_"

	block_dir="$features_dir/blocks/src/$slug"
	[[ -e "$block_dir" ]] && { echo "Block already exists: $block_dir" >&2; return 1; }
	mkdir -p "$block_dir"
	for silence in "$features_dir/blocks/index.php" "$features_dir/blocks/src/index.php"; do
		[[ -f "$silence" ]] || printf '<?php declare( strict_types=1 ); // Silence is golden.\n' >"$silence"
	done

	cat >"$block_dir/block.json" <<EOF
{
	"\$schema": "https://schemas.wp.org/trunk/block.json",
	"apiVersion": 3,
	"name": "${namespace}/${slug}",
	"title": "${title}",
	"category": "design",
	"icon": "screenoptions",
	"textdomain": "${text_domain}",
	"supports": { "html": false, "anchor": true, "align": [ "wide", "full" ] },
	"attributes": {},
	"editorScript": "file:./index.js",
	"render": "file:./render.php"
}
EOF

	cat >"$block_dir/index.js" <<'EOF'
import { registerBlockType } from '@wordpress/blocks';
import { InnerBlocks, useBlockProps } from '@wordpress/block-editor';

import metadata from './block.json';

const Edit = () => (
	<div { ...useBlockProps() }>
		<InnerBlocks />
	</div>
);

registerBlockType( metadata.name, {
	edit: Edit,
	save: () => <InnerBlocks.Content />,
} );
EOF

	cat >"$block_dir/render.php" <<EOF
<?php declare( strict_types=1 );
/**
 * Renders the ${title} block.
 *
 * @package  ${package}
 *
 * @var array<string, mixed> \$attributes Block attributes.
 * @var string               \$content    Inner blocks markup.
 */

\\defined( 'ABSPATH' ) || exit;

\$${var_prefix}wrapper = get_block_wrapper_attributes();
?>
<div <?php echo \$${var_prefix}wrapper; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- get_block_wrapper_attributes() escapes. ?>>
	<?php echo \$content; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- rendered inner blocks. ?>
</div>
EOF

	local blocks_php="$features_dir/includes/blocks.php"
	if [[ ! -f "$blocks_php" ]]; then
		cat >"$blocks_php" <<EOF
<?php declare( strict_types=1 );
/**
 * Registers the site's custom blocks from the wp-scripts build manifest.
 *
 * Blocks live in this plugin rather than the theme because page content stores them; a future
 * theme would otherwise leave them unregistered. Sources are under \`blocks/src/\`;
 * \`npm run build:features:blocks\` writes \`blocks/build/\` and its manifest. Each
 * \`block.json\` is listed in \`.github/blocks-allowlist\`.
 *
 * @package  ${package}
 */

\\defined( 'ABSPATH' ) || exit;

/**
 * Registers every block in the build manifest.
 *
 * @return  void
 */
function ${fn_prefix}register_blocks(): void {
	\$blocks_path   = \\constant( '${const_path}' ) . 'blocks/build';
	\$manifest_path = "{\$blocks_path}/blocks-manifest.php";
	if ( ! \\file_exists( \$manifest_path ) ) {
		return;
	}

	wp_register_block_types_from_metadata_collection( \$blocks_path, \$manifest_path );
}
add_action( 'init', '${fn_prefix}register_blocks' );
EOF
		echo "==> created includes/blocks.php (manifest registration)"
	else
		echo "==> includes/blocks.php already exists"
	fi

	# package.json: build/start scripts and lint paths, inserted textually so the file's own
	# formatting (blank lines between script groups) survives.
	python3 - "$repo/package.json" "mu-plugins/$features_slug/blocks" <<'PY'
import json, re, sys
path, blocks = sys.argv[1], sys.argv[2]
text = open(path).read()
scripts = json.loads(text).get('scripts', {})
build = f'wp-scripts build --webpack-src-dir={blocks}/src --output-path={blocks}/build --webpack-copy-php --blocks-manifest'
start = build.replace('wp-scripts build', 'wp-scripts start', 1)
changed = []

def insert_after_last(prefix, line):
    global text
    matches = list(re.finditer(r'^([ \t]*)"' + re.escape(prefix) + r'[^"]*":.*,[ \t]*$', text, re.M))
    if not matches:
        return False
    m = matches[-1]
    text = text[:m.end()] + '\n' + m.group(1) + line + ',' + text[m.end():]
    return True

for name, cmd, anchor in (('build:features:blocks', build, 'build:'), ('start:features:blocks', start, 'start:')):
    if name not in scripts:
        if insert_after_last(anchor, json.dumps(name) + ': ' + json.dumps(cmd)):
            changed.append(name)
        else:
            print(f'ADD MANUALLY: "{name}": "{cmd}"')

for name, needle in (('lint:scripts', f'{blocks}/src'), ('format:scripts', f'{blocks}/src'), ('lint:styles', f"'{blocks}/src/**/*.{{css,scss}}'")):
    cmd = scripts.get(name)
    if cmd is None or needle in cmd:
        continue
    new = re.sub(r'( --(?:no-error-on-unmatched-pattern|allow-empty-input))', lambda m: ' ' + needle + m.group(1), cmd, count=1)
    if new == cmd:
        print(f'ADD MANUALLY: add {needle} to the "{name}" script')
        continue
    text = text.replace(json.dumps(cmd), json.dumps(new), 1)
    changed.append(name)

json.loads(text)
open(path, 'w').write(text)
if changed:
    print('==> package.json: ' + ', '.join(changed))
missing = [p for p in ('@wordpress/blocks', '@wordpress/block-editor') if '"' + p + '"' not in text]
if missing:
    print('ADD MANUALLY: npm install -D ' + ' '.join(missing) + '  (ESLint import/no-extraneous-dependencies)')
PY

	local allowlist="$repo/.github/blocks-allowlist"
	mkdir -p "$repo/.github"
	[[ -f "$allowlist" ]] || printf '# Blocks kept in this site repository rather than the blocks monorepo: one block.json path per line.\n' >"$allowlist"
	local rel
	for rel in "mu-plugins/$features_slug/blocks/src/$slug/block.json" "mu-plugins/$features_slug/blocks/build/$slug/block.json"; do
		grep -qxF "$rel" "$allowlist" || echo "$rel" >>"$allowlist"
	done
	echo "==> .github/blocks-allowlist lists the block's src and build block.json"

	if [[ -f "$features_dir/.disabled" ]]; then
		echo "NOTE: $features_dir/.disabled is present, so the features plugin registers nothing until it is deleted."
	fi
	echo "H2BT_BLOCK_OK slug=${slug} dir=${block_dir} layout=template build=\"npm run build:features:blocks\""
}

theme_dir=""
slug=""
title=""
namespace="theme"
layout="standalone"
features_dir=""
prefix=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--theme-dir) theme_dir="${2:-}"; shift 2 ;;
		--slug) slug="${2:-}"; shift 2 ;;
		--title) title="${2:-}"; shift 2 ;;
		--namespace) namespace="${2:-}"; shift 2 ;;
		--layout) layout="${2:-}"; shift 2 ;;
		--features-dir) features_dir="${2:-}"; shift 2 ;;
		--prefix) prefix="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$slug" ]] || { echo "--slug is required" >&2; exit 2; }
[[ -n "$title" ]] || { echo "--title is required" >&2; exit 2; }
[[ "$slug" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Slug must be lowercase alphanumeric + hyphens: $slug" >&2; exit 1; }
[[ "$namespace" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Namespace must be lowercase alphanumeric + hyphens: $namespace" >&2; exit 1; }

case "$layout" in
	standalone) ;;
	template)
		[[ -n "$features_dir" && -d "$features_dir" ]] || { echo "--features-dir must name the features mu-plugin directory" >&2; exit 2; }
		[[ "$namespace" != "theme" ]] || { echo "--namespace is required in template layout (use the theme slug)" >&2; exit 2; }
		scaffold_template_block
		exit $?
		;;
	*) echo "--layout must be standalone or template: $layout" >&2; exit 2 ;;
esac

[[ -n "$theme_dir" ]] || { echo "--theme-dir is required" >&2; exit 2; }
[[ -d "$theme_dir" ]] || { echo "Theme directory not found: $theme_dir" >&2; exit 1; }

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
