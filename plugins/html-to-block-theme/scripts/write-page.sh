#!/usr/bin/env bash
#
# write-page.sh — sentinel-verified upsert of a WordPress page from block markup.
#
# Wraps the whole staged-write flow the section-builder needs: copies the markup
# file inside the site dir (Studio's wp sandbox cannot read host /tmp), fills the
# write-page-content.php.tmpl placeholders, runs it via `studio wp eval-file`
# (a real file path — `eval-file -` can silently no-op), and greps the output for
# the H2BT_OK sentinel. Anything but a printed H2BT_OK exits non-zero.
#
#   write-page.sh --site-path <site> --title <title> --slug <slug> \
#                 [--template <template-slug|default>] --content <markup-file>
#
# On success the PHP sentinel line (H2BT_OK id=<id> bytes=<n>) is printed.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  write-page.sh --site-path <site> --title <title> --slug <slug> \
                [--template <template-slug|default>] --content <markup-file>

Upserts a WordPress page whose post_content is the block markup in <markup-file>,
assigned to <template-slug> (or the default page template). Prints the H2BT_OK
sentinel on success; exits non-zero on any failure. Trust the exit code — it is
derived from the sentinel, not from `studio wp`'s own exit status.
EOF
}

site_path=""
title=""
slug=""
template="default"
content=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) site_path="${2:-}"; shift 2 ;;
		--title) title="${2:-}"; shift 2 ;;
		--slug) slug="${2:-}"; shift 2 ;;
		--template) template="${2:-}"; shift 2 ;;
		--content) content="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" && -n "$title" && -n "$slug" && -n "$content" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
[[ -r "$content" && -s "$content" ]] || { echo "Content file missing or empty: $content" >&2; exit 1; }
[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "Slug must be lowercase kebab-case: $slug" >&2; exit 2; }
command -v studio >/dev/null 2>&1 || { echo "studio CLI not found" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmpl="$script_dir/write-page-content.php.tmpl"
[[ -r "$tmpl" ]] || { echo "Template not found: $tmpl" >&2; exit 1; }

site_path="$(cd "$site_path" && pwd)"
stage_dir="$site_path/.h2bt"
mkdir -p "$stage_dir"

content_basename="content-${slug}.html"
cp "$content" "$stage_dir/$content_basename"

# Escape values for the template's single-quoted PHP strings.
php_escape() {
	local s="$1"
	s="${s//\\/\\\\}"
	s="${s//\'/\\\'}"
	printf '%s' "$s"
}

tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__PAGE_TITLE__/$(php_escape "$title")}"
tmpl_body="${tmpl_body//__PAGE_SLUG__/$(php_escape "$slug")}"
tmpl_body="${tmpl_body//__TEMPLATE__/$(php_escape "$template")}"
tmpl_body="${tmpl_body//__CONTENT_FILE__/$content_basename}"
printf '%s\n' "$tmpl_body" > "$stage_dir/write-${slug}.php"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/write-${slug}.php" --path="$site_path" 2>&1)" || true
printf '%s\n' "$out"

if grep -q '^H2BT_OK' <<<"$out"; then
	exit 0
fi
echo "WRITE FAILED: no H2BT_OK sentinel for page '${slug}'" >&2
exit 1
