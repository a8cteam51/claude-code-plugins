#!/usr/bin/env bash
#
# standards-audit.sh — enforce the two machine-checkable standards for a generated
# block theme:
#   1. Block markup (templates/, parts/, patterns/) contains ONLY <!-- wp ... -->
#      comments. Any other HTML comment is a violation.
#   2. Custom CSS is minimal — report the footprint so it can be reviewed.
#
# Usage: standards-audit.sh --theme-dir <dir>
# Exits non-zero if stray (non-wp) HTML comments are found.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: standards-audit.sh --theme-dir <dir>

Scans <dir>/templates, <dir>/parts, <dir>/patterns for HTML comments that are not
Gutenberg block delimiters, and measures the custom-CSS footprint across the theme.
Prints a report. Exits 1 if any stray comment is found, 0 otherwise.
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
if [[ "$violations" -gt 0 ]]; then
	echo "H2BT_AUDIT_FAIL stray_comments=${violations} css_lines=${total}"
	exit 1
fi
echo "H2BT_AUDIT_OK stray_comments=0 css_lines=${total}"
