#!/usr/bin/env bash
#
# write-page.sh — sentinel-verified upsert of a WordPress page from block markup.
#
# Wraps the whole staged-write flow the section-builder needs: copies the markup
# file inside the site dir (Studio's wp sandbox cannot read host /tmp), stages the
# title beside it, fills the write-page-content.php.tmpl placeholders, runs it via
# `studio wp eval-file` (a real file path — `eval-file -` can silently no-op), and
# greps the output for the H2BT_OK sentinel. Anything but a printed H2BT_OK exits
# non-zero.
#
#   write-page.sh --site-path <site> --title <title> --slug <slug> [--parent <page-path>] \
#                 [--template <template-slug|default>] --content <markup-file>
#
# On success the PHP sentinel line is printed and the staged files are removed:
#   H2BT_OK id=<id> slug=<slug> parent=<id|0> template=<template> bytes=<n> php=<version>
# The PHP reads the stored title, slug, parent, template and content back before it prints
# the sentinel, so anything WordPress stored differently fails. A slug held by a post that
# is not a page (an attachment, usually) fails before anything is written. A page whose
# stored template the active theme does not offer (a page builder's) has it cleared before
# the update, and the sentinel ends with replaced_template=<that template>.
#
# --parent puts the page under another page, named by its path (about, or about/team): a
# site whose addresses are nested keeps them. The parent has to exist, so write it first.
#
set -euo pipefail

# From bash 5.2 an `&` in the replacement of ${var//pattern/replacement} stands for the
# matched text. Only validated values are substituted below, and the title never is;
# switching the option off keeps every bash version on the same behaviour.
shopt -u patsub_replacement 2>/dev/null || true

usage() {
	cat <<'EOF'
Usage:
  write-page.sh --site-path <site> --title <title> --slug <slug> [--parent <page-path>] \
                [--template <template-slug|default>] --content <markup-file>

Upserts a WordPress page whose post_content is the block markup in <markup-file>,
assigned to <template-slug> (or the default page template). <template-slug> is the slug
of a template of the active theme, such as page-home, not a file path. --parent names the
page this one sits under, by its path (about, or about/team); it must exist. Prints the H2BT_OK
sentinel on success; exits non-zero on any failure. Trust the exit code — it is
derived from the sentinel, not from `studio wp`'s own exit status.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

site_path=""
title=""
slug=""
template="default"
content=""
parent=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		--title) need_value "$@"; title="$2"; shift 2 ;;
		--slug) need_value "$@"; slug="$2"; shift 2 ;;
		--template) need_value "$@"; template="$2"; shift 2 ;;
		--content) need_value "$@"; content="$2"; shift 2 ;;
		--parent) need_value "$@"; parent="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" && -n "$title" && -n "$slug" && -n "$content" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
[[ -r "$content" && -s "$content" ]] || { echo "Content file missing or empty: $content" >&2; exit 1; }
[[ "$slug" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "Slug must be lowercase kebab-case: $slug" >&2; exit 2; }
[[ "$template" =~ ^[A-Za-z0-9_-]+$ ]] || { echo "Template must be a template slug (page-home, not templates/page-home.html) or \"default\": $template" >&2; exit 2; }
[[ "$title" != *$'\n'* ]] || { echo "Title must be a single line" >&2; exit 2; }
parent="${parent#/}"
parent="${parent%/}"
[[ -z "$parent" || "$parent" =~ ^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*)*$ ]] || { echo "Parent must be a page path of lowercase kebab-case slugs (about, or about/team): $parent" >&2; exit 2; }
command -v studio >/dev/null 2>&1 || { echo "studio CLI not found" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmpl="$script_dir/write-page-content.php.tmpl"
[[ -r "$tmpl" ]] || { echo "Template not found: $tmpl" >&2; exit 1; }

site_path="$(cd "$site_path" && pwd)"
stage_dir="$site_path/.h2bt"
mkdir -p "$stage_dir"

# Two pages can share a slug under different parents: the staged names carry the parent too.
stage_key="$slug"
[[ -z "$parent" ]] || stage_key="$(printf '%s' "$parent" | sed 's|/|--|g')--${slug}"
content_basename="content-${stage_key}.html"
title_basename="title-${stage_key}.txt"
script_basename="write-${stage_key}.php"
cp "$content" "$stage_dir/$content_basename"

# The title is free text, so it travels in its own file and is never substituted into PHP.
printf '%s' "$title" > "$stage_dir/$title_basename"

# The remaining values are validated above: none can hold a quote, a backslash or an ampersand.
tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__TITLE_FILE__/$title_basename}"
tmpl_body="${tmpl_body//__PAGE_SLUG__/$slug}"
tmpl_body="${tmpl_body//__PARENT_PATH__/$parent}"
tmpl_body="${tmpl_body//__TEMPLATE__/$template}"
tmpl_body="${tmpl_body//__CONTENT_FILE__/$content_basename}"
printf '%s\n' "$tmpl_body" > "$stage_dir/$script_basename"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/$script_basename" --path="$site_path" 2>&1)" || true

# Studio can print PHP notices around the script's output: show only the sentinel line.
sentinel="$(grep -E '^H2BT_(OK|FAIL)' <<<"$out" | tail -1 || true)"

if [[ "$sentinel" == H2BT_OK* ]]; then
	printf '%s\n' "$sentinel"
	rm -f "$stage_dir/$content_basename" "$stage_dir/$title_basename" "$stage_dir/$script_basename"
	exit 0
fi

printf '%s\n' "$out"
echo "WRITE FAILED: no H2BT_OK sentinel for page '${slug}' (staged files kept in $stage_dir)" >&2
exit 1
