#!/usr/bin/env bash
#
# standards-audit.sh — enforce the machine-checkable standards for a generated
# block theme:
#   1. Block markup (templates/, parts/, patterns/) contains ONLY <!-- wp ... -->
#      comments. Any other HTML comment is a violation.
#   2. Custom CSS is minimal — report the footprint so it can be reviewed.
#   3. Block CSS is one file per block type, each enqueued via wp_enqueue_block_style().
#      Standalone layout: assets/css/blocks/<block>.css, enqueued from functions.php.
#      Template layout (a8csp-project-template theme): assets/css/src/blocks/<block>.scss,
#      built to assets/css/build/blocks/<block>.css and enqueued from functions.php or
#      includes/*.php. Stray, unbuilt, or unenqueued block stylesheets are violations.
#   4. No templates/front-page.html — the homepage must be a WordPress page set as
#      the static front page via Reading settings, not a template.
#   5. No blocks in the theme — no block.json anywhere under the theme. Blocks come from
#      the A8C Special Projects blocks monorepo, or (template mode, approved exclusions
#      only) the features mu-plugin.
#
# Usage: standards-audit.sh --theme-dir <dir> [--layout auto|standalone|template]
# Exits non-zero if stray comments, block-CSS organization violations, a
# front-page.html template, or a block inside the theme are found.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: standards-audit.sh --theme-dir <dir> [--layout auto|standalone|template]

Scans <dir>/templates, <dir>/parts, <dir>/patterns for HTML comments that are not
Gutenberg block delimiters, measures the custom-CSS footprint, checks that block CSS is
one file per block type enqueued via wp_enqueue_block_style(), and checks that the theme
ships no templates/front-page.html and no block.json. Prints a report. Exits 1 on any
violation, 0 otherwise.

--layout auto (default) picks "template" when the theme has assets/sass/style.scss,
includes/, and .phpcs.xml (an a8csp-project-template theme), else "standalone".
EOF
}

theme_dir=""
layout="auto"
while [[ $# -gt 0 ]]; do
	case "$1" in
		--theme-dir) theme_dir="${2:-}"; shift 2 ;;
		--layout) layout="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$theme_dir" ]] || { echo "--theme-dir is required" >&2; exit 2; }
[[ -d "$theme_dir" ]] || { echo "Theme directory not found: $theme_dir" >&2; exit 1; }
if [[ "$layout" == "auto" ]]; then
	if [[ -f "$theme_dir/assets/sass/style.scss" && -d "$theme_dir/includes" && -f "$theme_dir/.phpcs.xml" ]]; then
		layout="template"
	else
		layout="standalone"
	fi
fi
[[ "$layout" == "standalone" || "$layout" == "template" ]] || { echo "--layout must be auto, standalone, or template" >&2; exit 2; }
echo "Layout: $layout"
echo

echo "== Comment audit (block markup) =="
command -v perl >/dev/null 2>&1 || { echo "perl is required for the comment audit" >&2; exit 1; }
violations=0
while IFS= read -r -d '' file; do
	# Strip wp block delimiters first, then flag any HTML comment that remains —
	# this catches stray comments that share a line with a wp delimiter.
	matches="$(perl -ne 's/<!--\s*\/?wp:.*?-->//g; print "$.\n" if /<!--/;' "$file" || true)"
	if [[ -n "$matches" ]]; then
		while IFS= read -r lineno; do
			[[ -z "$lineno" ]] && continue
			echo "  STRAY COMMENT  ${file#$theme_dir/}:${lineno}"
			violations=$((violations + 1))
		done <<<"$matches"
	fi
done < <(find "$theme_dir/templates" "$theme_dir/parts" "$theme_dir/patterns" \
	-type f \( -name '*.html' -o -name '*.php' \) -print0 2>/dev/null)

if [[ "$violations" -eq 0 ]]; then
	echo "  OK — no stray comments in block markup"
fi

echo
echo "== Custom CSS footprint =="
# Lines of CSS a reviewer reads: comments (/* */, and // in SCSS) and blank lines excluded, so
# the theme-header comment in style.css does not count.
css_lines() {
	perl -0777 -ne 's{/\*.*?\*/}{}gs; s{^\s*//.*$}{}mg; print scalar( grep { /\S/ } split /\n/ ), "\n";' "$1"
}
total=0
found_css=0
if [[ "$layout" == "template" ]]; then
	footprint_find=( "$theme_dir/assets/sass" "$theme_dir/assets/css/src" "$theme_dir/blocks" -type f \( -name '*.scss' -o -name '*.css' \) )
else
	footprint_find=( "$theme_dir" -type f -name '*.css' )
fi
while IFS= read -r -d '' css; do
	found_css=1
	count="$(css_lines "$css")"
	total=$((total + count))
	echo "  ${css#$theme_dir/}: ${count} CSS lines"
done < <(find "${footprint_find[@]}" -print0 2>/dev/null | sort -z)

if [[ "$found_css" -eq 0 ]]; then
	echo "  (no stylesheet sources found)"
fi
echo "  TOTAL custom CSS lines: ${total}"
if [[ "$layout" == "template" ]]; then
	echo "  NOTE: counts the Sass/SCSS sources (built CSS is generated from them); lower is better."
else
	echo "  NOTE: comments and blank lines excluded; lower is better. Review each rule against the report."
fi

echo
echo "== Block CSS organization =="
css_org=0
functions_php="$theme_dir/functions.php"

if [[ "$layout" == "template" ]]; then
	# Sources under assets/css/src/blocks/, built into assets/css/build/blocks/, enqueued from
	# functions.php or includes/*.php (the template loads every includes/*.php file).
	php_sources=( "$functions_php" )
	while IFS= read -r -d '' inc; do php_sources+=( "$inc" ); done < <(find "$theme_dir/includes" -maxdepth 1 -type f -name '*.php' -print0 2>/dev/null)
	if [[ -d "$theme_dir/assets/css/src/blocks" ]] && ! grep -qs "wp_enqueue_block_style" "${php_sources[@]}"; then
		echo "  MISSING     no theme PHP file calls wp_enqueue_block_style()"
		css_org=$((css_org + 1))
	fi
	while IFS= read -r -d '' src; do
		base="$(basename "$src" .scss)"
		built="$theme_dir/assets/css/build/blocks/$base.css"
		if [[ ! -f "$built" ]]; then
			echo "  UNBUILT     ${src#$theme_dir/} — no assets/css/build/blocks/$base.css (run the build)"
			css_org=$((css_org + 1))
		elif grep -qsF "$base.css" "${php_sources[@]}"; then
			echo "  OK          ${src#$theme_dir/} -> assets/css/build/blocks/$base.css (enqueued)"
		else
			echo "  UNENQUEUED  ${src#$theme_dir/} — $base.css is not referenced in functions.php or includes/*.php"
			css_org=$((css_org + 1))
		fi
	done < <(find "$theme_dir/assets/css/src/blocks" -type f -name '*.scss' -print0 2>/dev/null | sort -z)

	while IFS= read -r -d '' css; do
		rel="${css#$theme_dir/}"
		case "$rel" in
			style.css|style-rtl.css|style-editor.css) ;;
			assets/sass/*.scss|assets/sass/*/*.scss) ;;
			assets/css/src/blocks/*.scss) ;;
			assets/css/build/blocks/*.css)
				[[ -f "$theme_dir/assets/css/src/blocks/$(basename "$css" .css).scss" ]] || {
					echo "  ORPHAN      ${rel} — built block CSS with no assets/css/src/blocks/ source"
					css_org=$((css_org + 1))
				}
				;;
			assets/css/src/*.scss|assets/css/build/*.css)
				echo "  PER-PURPOSE ${rel} — not block CSS; allowed, list it in the report with what enqueues it"
				;;
			blocks/*) ;;
			*)
				echo "  STRAY       ${rel} — block CSS goes in assets/css/src/blocks/<block>.scss; root styles in assets/sass/"
				css_org=$((css_org + 1))
				;;
		esac
	done < <(find "$theme_dir" -path "$theme_dir/node_modules" -prune -o -type f \( -name '*.css' -o -name '*.scss' \) -print0 2>/dev/null)

	if [[ "$css_org" -eq 0 ]]; then
		echo "  OK — block CSS is one Sass source per block type, built and enqueued via wp_enqueue_block_style()"
	fi
else
	blocks_css_dir="$theme_dir/assets/css/blocks"

	# 1. Every per-block stylesheet must be enqueued via wp_enqueue_block_style() in functions.php.
	if [[ -d "$blocks_css_dir" ]]; then
		if [[ ! -f "$functions_php" ]]; then
			echo "  MISSING     functions.php — block CSS files exist but cannot be enqueued"
			css_org=$((css_org + 1))
		elif ! grep -q "wp_enqueue_block_style" "$functions_php"; then
			echo "  MISSING     functions.php never calls wp_enqueue_block_style()"
			css_org=$((css_org + 1))
		fi
		while IFS= read -r -d '' bcss; do
			base="$(basename "$bcss")"
			if [[ -f "$functions_php" ]] && grep -qF "$base" "$functions_php"; then
				echo "  OK          ${bcss#$theme_dir/} (enqueued)"
			else
				echo "  UNENQUEUED  ${bcss#$theme_dir/} — not referenced in functions.php"
				css_org=$((css_org + 1))
			fi
		done < <(find "$blocks_css_dir" -type f -name '*.css' -print0 2>/dev/null)
	fi

	# 2. Block CSS must be one file per block type under assets/css/blocks/. Flag strays.
	#    Allowed elsewhere: only the theme-header style.css. Themes contain no blocks, so no
	#    block-bundled CSS either (see the theme blocks check).
	while IFS= read -r -d '' css; do
		rel="${css#$theme_dir/}"
		case "$rel" in
			style.css) ;;
			assets/css/blocks/*.css) ;;
			*)
				echo "  STRAY       ${rel} — block CSS must be one file per block type under assets/css/blocks/"
				css_org=$((css_org + 1))
				;;
		esac
	done < <(find "$theme_dir" -type f -name '*.css' -print0 2>/dev/null)

	if [[ "$css_org" -eq 0 ]]; then
		echo "  OK — block CSS is one file per block type, each enqueued via wp_enqueue_block_style()"
	fi
fi

echo
echo "== Front-page template check =="
front_page=0
if [[ -f "$theme_dir/templates/front-page.html" ]]; then
	echo "  FORBIDDEN   templates/front-page.html — set a page as the front page via Reading settings instead"
	front_page=1
else
	echo "  OK — no templates/front-page.html"
fi

echo
echo "== Theme blocks check =="
theme_blocks=0
while IFS= read -r -d '' block_json; do
	echo "  FORBIDDEN   ${block_json#$theme_dir/} — blocks never live in a theme; reuse or build them in the blocks monorepo"
	theme_blocks=$((theme_blocks + 1))
done < <(find "$theme_dir" -name node_modules -prune -o -name block.json -type f -print0)
if [[ "$theme_blocks" -eq 0 ]]; then
	echo "  OK — no block.json in the theme"
fi

echo
if [[ "$violations" -gt 0 || "$css_org" -gt 0 || "$front_page" -gt 0 || "$theme_blocks" -gt 0 ]]; then
	echo "H2BT_AUDIT_FAIL layout=${layout} stray_comments=${violations} css_org=${css_org} front_page=${front_page} theme_blocks=${theme_blocks} css_lines=${total}"
	exit 1
fi
echo "H2BT_AUDIT_OK layout=${layout} stray_comments=0 css_org=0 front_page=0 theme_blocks=0 css_lines=${total}"
