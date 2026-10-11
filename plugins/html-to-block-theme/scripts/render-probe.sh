#!/usr/bin/env bash
#
# render-probe.sh — render a block-markup file on a Studio site and print what WordPress
# makes of it: the HTML and the block-supports CSS. Nothing is written to the database.
#
# It answers "does this attribute print, and as what?" in one call, on the installed core:
# a per-viewport value, a hover state, an element style, a colour WordPress may drop. Use it
# before relying on an attribute form, since forms move between core versions.
#
#   render-probe.sh --site-path <site> --markup <markup-file> [--post-id <id>]
#
# --post-id sets the post the blocks read, for blocks that depend on one (post title, a
# bindings source). Output: a line starting H2BT_PROBE_BEGIN with the PHP and WordPress
# versions and the active theme, the rendered HTML, the CSS, then H2BT_PROBE_OK. Anything
# else exits non-zero.
#
# Two limits: the probe runs do_blocks(), so text is not texturised as a template's whole
# output is on a real page, and blocks see no query unless --post-id gives them a post.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  render-probe.sh --site-path <site> --markup <markup-file> [--post-id <id>]

Renders the block markup in <markup-file> on the Studio site and prints the HTML and the
block-supports stylesheet it produced. Writes nothing to the database. Exits non-zero
unless the H2BT_PROBE_OK sentinel was printed.
EOF
}

site_path=""
markup=""
post_id="0"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) site_path="${2:-}"; shift 2 ;;
		--markup) markup="${2:-}"; shift 2 ;;
		--post-id) post_id="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" && -n "$markup" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || { echo "Site path not found: $site_path" >&2; exit 1; }
[[ -r "$markup" && -s "$markup" ]] || { echo "Markup file missing or empty: $markup" >&2; exit 1; }
[[ "$post_id" =~ ^[0-9]+$ ]] || { echo "--post-id must be a number: $post_id" >&2; exit 2; }
command -v studio >/dev/null 2>&1 || { echo "studio CLI not found" >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmpl="$script_dir/render-probe.php.tmpl"
[[ -r "$tmpl" ]] || { echo "Template not found: $tmpl" >&2; exit 1; }

# Studio's wp cannot read host /tmp: stage inside the site, under names nothing else uses.
site_path="$(cd "$site_path" && pwd)"
stage_dir="$site_path/.h2bt"
mkdir -p "$stage_dir"
markup_basename="probe-$$.html"
script_basename="probe-$$.php"
cleanup() { rm -f "$stage_dir/$markup_basename" "$stage_dir/$script_basename"; }
trap cleanup EXIT

cp "$markup" "$stage_dir/$markup_basename"

# Both values are generated or validated above, so plain substitution is safe.
tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__MARKUP_FILE__/$markup_basename}"
tmpl_body="${tmpl_body//__POST_ID__/$post_id}"
printf '%s\n' "$tmpl_body" > "$stage_dir/$script_basename"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/$script_basename" --path="$site_path" 2>&1)" || true

if grep -q '^H2BT_PROBE_OK' <<<"$out"; then
	# Studio can print PHP notices before the script's output: show the probe's part only.
	sed -n '/^H2BT_PROBE_BEGIN/,/^H2BT_PROBE_OK/p' <<<"$out"
	exit 0
fi

printf '%s\n' "$out"
echo "PROBE FAILED: no H2BT_PROBE_OK sentinel" >&2
exit 1
