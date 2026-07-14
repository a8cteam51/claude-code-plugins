#!/usr/bin/env bash
#
# standards-audit.sh — enforce the machine-checkable standards for a generated
# block theme:
#   1. Block markup (templates/, parts/, patterns/) contains ONLY <!-- wp ... -->
#      comments. Any other HTML comment is a violation.
#   2. Custom CSS is minimal — report the footprint so it can be reviewed.
#   3. Block CSS is one file per block type under assets/css/blocks/, each enqueued
#      via wp_enqueue_block_style() in functions.php. Stray or unenqueued block
#      stylesheets are violations.
#   4. No templates/front-page.html — the homepage must be a WordPress page set as
#      the static front page via Reading settings, not a template.
#
# Usage: standards-audit.sh --theme-dir <dir>
# Exits non-zero if stray comments, block-CSS organization violations, or a
# front-page.html template are found.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: standards-audit.sh --theme-dir <dir>

Scans <dir>/templates, <dir>/parts, <dir>/patterns for HTML comments that are not
Gutenberg block delimiters, measures the custom-CSS footprint, and checks that block
CSS is one file per block type under assets/css/blocks/ enqueued via
wp_enqueue_block_style(). Prints a report. Exits 1 if any stray comment or block-CSS
organization violation is found, 0 otherwise.
EOF
}

theme_dir=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--theme-dir) theme_dir="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$theme_dir" ]] || { echo "--theme-dir is required" >&2; exit 2; }
[[ -d "$theme_dir" ]] || { echo "Theme directory not found: $theme_dir" >&2; exit 1; }

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
total=0
found_css=0
while IFS= read -r -d '' css; do
	found_css=1
	# Count non-blank, non-comment-only lines.
	count="$(grep -cvE '^\s*($|/\*|\*/|\*|//)' "$css" || true)"
	total=$((total + count))
	echo "  ${css#$theme_dir/}: ${count} CSS lines"
done < <(find "$theme_dir" -type f -name '*.css' -print0 2>/dev/null)

if [[ "$found_css" -eq 0 ]]; then
	echo "  (no .css files found)"
fi
echo "  TOTAL custom CSS lines: ${total}"
echo "  NOTE: style.css theme-header comment is excluded; lower is better. Review each rule against the report."

echo
echo "== Block CSS organization =="
css_org=0
functions_php="$theme_dir/functions.php"
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
#    Allowed elsewhere: the theme-header style.css and a custom block's own bundled
#    CSS under blocks/<slug>/.
while IFS= read -r -d '' css; do
	rel="${css#$theme_dir/}"
	case "$rel" in
		style.css) ;;
		assets/css/blocks/*.css) ;;
		blocks/*) ;;
		*)
			echo "  STRAY       ${rel} — block CSS must be one file per block type under assets/css/blocks/"
			css_org=$((css_org + 1))
			;;
	esac
done < <(find "$theme_dir" -type f -name '*.css' -print0 2>/dev/null)

if [[ "$css_org" -eq 0 ]]; then
	echo "  OK — block CSS is one file per block type, each enqueued via wp_enqueue_block_style()"
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
if [[ "$violations" -gt 0 || "$css_org" -gt 0 || "$front_page" -gt 0 ]]; then
	echo "H2BT_AUDIT_FAIL stray_comments=${violations} css_org=${css_org} front_page=${front_page} css_lines=${total}"
	exit 1
fi
echo "H2BT_AUDIT_OK stray_comments=0 css_org=0 front_page=0 css_lines=${total}"
