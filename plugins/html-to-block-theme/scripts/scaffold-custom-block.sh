#!/usr/bin/env bash
#
# scaffold-custom-block.sh — scaffold an APPROVED EXCLUSION: a block that stays in an
# a8csp-project-template repository instead of the A8C Special Projects blocks monorepo.
#
# Blocks belong in the monorepo (see references/custom-blocks-guide.md). A block may stay in the
# project only when an engineering lead has approved an exclusion, so this script refuses to run
# without --exclusion-approved. It never writes a block into a theme.
#
# The block's sources go in the features mu-plugin under blocks/src/<slug>/ (ES modules + JSX,
# strict-types render.php), built by wp-scripts into blocks/build/ with a blocks manifest; the
# script also wires the manifest registration, the package.json build/lint scripts, and the
# .github/blocks-allowlist entries CI requires, under a comment marking the approved exclusion.
#
# Usage:
#   scaffold-custom-block.sh --exclusion-approved --features-dir <dir> --slug <slug> \
#       --title "<Title>" --namespace <theme-slug> [--prefix <php_prefix_>]
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  scaffold-custom-block.sh --exclusion-approved --features-dir <dir> --slug <slug> \
      --title "<Title>" --namespace <theme-slug> [--prefix <php_prefix_>]

Scaffolds an approved exclusion in an a8csp-project-template repository: a block kept in the
project instead of the A8C Special Projects blocks monorepo. Run it only when an engineering
lead has approved the exclusion; otherwise build the block in the monorepo
(references/custom-blocks-guide.md).

Creates <features-dir>/blocks/src/<slug>/{block.json,index.js,render.php}, adds
includes/blocks.php (manifest registration) if missing, adds the build:features:blocks and
start:features:blocks npm scripts and the blocks/src lint paths when missing, and lists the
block's src and build block.json in .github/blocks-allowlist under an approved-exclusion
comment. --prefix defaults to the one in the theme's .phpcs.xml. Build with
`npm run build:features:blocks`.

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
	grep -qxF "# Approved exclusion: ${namespace}/${slug}" "$allowlist" || echo "# Approved exclusion: ${namespace}/${slug}" >>"$allowlist"
	for rel in "mu-plugins/$features_slug/blocks/src/$slug/block.json" "mu-plugins/$features_slug/blocks/build/$slug/block.json"; do
		grep -qxF "$rel" "$allowlist" || echo "$rel" >>"$allowlist"
	done
	echo "==> .github/blocks-allowlist lists the block's src and build block.json"

	if [[ -f "$features_dir/.disabled" ]]; then
		echo "NOTE: $features_dir/.disabled is present, so the features plugin registers nothing until it is deleted."
	fi
	echo "H2BT_BLOCK_OK slug=${slug} dir=${block_dir} layout=template exclusion=approved build=\"npm run build:features:blocks\""
}

slug=""
title=""
namespace=""
features_dir=""
prefix=""
approved="no"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--exclusion-approved) approved="yes"; shift ;;
		--slug) slug="${2:-}"; shift 2 ;;
		--title) title="${2:-}"; shift 2 ;;
		--namespace) namespace="${2:-}"; shift 2 ;;
		--features-dir) features_dir="${2:-}"; shift 2 ;;
		--prefix) prefix="${2:-}"; shift 2 ;;
		--theme-dir|--layout)
			echo "$1 is no longer supported: blocks are never scaffolded into a theme. Reuse or build them in the blocks monorepo (references/custom-blocks-guide.md)." >&2
			exit 2
			;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

if [[ "$approved" != "yes" ]]; then
	echo "Refusing to scaffold: blocks belong in the A8C Special Projects blocks monorepo. Pass --exclusion-approved only when an engineering lead has approved keeping this block in the project (references/custom-blocks-guide.md)." >&2
	exit 2
fi
[[ -n "$slug" ]] || { echo "--slug is required" >&2; exit 2; }
[[ -n "$title" ]] || { echo "--title is required" >&2; exit 2; }
[[ -n "$namespace" ]] || { echo "--namespace is required (use the project theme slug)" >&2; exit 2; }
[[ "$slug" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Slug must be lowercase alphanumeric + hyphens: $slug" >&2; exit 1; }
[[ "$namespace" =~ ^[a-z][a-z0-9-]*$ ]] || { echo "Namespace must be lowercase alphanumeric + hyphens: $namespace" >&2; exit 1; }
[[ -n "$features_dir" && -d "$features_dir" ]] || { echo "--features-dir must name the features mu-plugin directory" >&2; exit 2; }

scaffold_template_block
