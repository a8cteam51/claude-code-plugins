#!/usr/bin/env bash
# export-pages.sh — export a Studio site's page content for standards-audit.sh --content-dir.
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  export-pages.sh --site-path <site> [--post-type <a,b,...>]

Writes the block markup of every page and user pattern (wp_block, synced or not) on the
Studio site, published or not, to <site>/.h2bt/export/<post-type>-<id>.html, after
removing the files an earlier export left there. A run that is refused before it reads
the site leaves the earlier export as it was. Content with no block delimiters is counted
as skipped and not written. Nothing is written to the database. Then audit the theme with
it:

  standards-audit.sh --theme-dir <theme-dir> --content-dir <site>/.h2bt/export

--post-type names the post types to export, separated by commas (default page,wp_block).
Add a type when a change writes or generates its block content: posts, or a custom type
whose template prints core/post-content, as in --post-type page,wp_block,post. The list
replaces the default, so name page and wp_block in it to keep them.

A run audits the page sources it wrote (<site>/.h2bt/pages); what changed in the
database since is only in the export. The last line is
  H2BT_EXPORT_OK pages=<n> patterns=<n> skipped=<n> [<post-type>=<n>]... dir=<dir>
with one <post-type>=<n> for each type named other than page and wp_block, or
H2BT_EXPORT_FAIL reason=<why>, and the exit code follows it. A type the site does not
register ends H2BT_EXPORT_FAIL reason=unknown-post-type type=<post-type>. A list that is
not post type keys separated by commas is a usage error, like any other bad argument
(exit 2, no sentinel).
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

fail() { echo "H2BT_EXPORT_FAIL reason=$1"; exit 1; }

site_path=""
post_types="page,wp_block"

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		--post-type) need_value "$@"; post_types="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || fail site-path-not-found
# The list is written into the staged PHP, and a post type's key holds only these characters.
if [[ ! "$post_types" =~ ^[a-z0-9_-]+(,[a-z0-9_-]+)*$ ]]; then
	echo "--post-type takes post type keys separated by commas: $post_types" >&2
	usage >&2
	exit 2
fi
command -v studio >/dev/null 2>&1 || fail studio-cli-not-found

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmpl="$script_dir/export-pages.php.tmpl"
[[ -r "$tmpl" ]] || fail template-not-found

# A site whose PHP sees only its own directory cannot write to host /tmp, so the export stays inside it.
site_path="$(cd "$site_path" && pwd)"
stage_dir="$site_path/.h2bt"
export_name="export"
export_dir="$stage_dir/$export_name"
mkdir -p "$export_dir"

exported() { find "$export_dir" -maxdepth 1 -type f -name '*-[0-9]*.html'; }

script_basename="export-$$.php"
cleanup() { rm -f "$stage_dir/$script_basename"; }
trap cleanup EXIT

tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__EXPORT_DIR__/$export_name}"
tmpl_body="${tmpl_body//__POST_TYPES__/$post_types}"
printf '%s\n' "$tmpl_body" > "$stage_dir/$script_basename"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/$script_basename" --path="$site_path" 2>&1)" || true

# Studio can print PHP notices around the script's output.
sentinel="$(grep -E '^H2BT_EXPORT_(OK|FAIL)' <<<"$out" | tail -1 || true)"

if [[ "$sentinel" == H2BT_EXPORT_OK* ]]; then
	expected=0
	for counter in $sentinel; do
		case "$counter" in
			skipped=*) ;;
			*=*[!0-9]*|*=) ;;
			*=*) expected=$(( expected + ${counter#*=} )) ;;
		esac
	done
	written="$(exported | wc -l | tr -d ' ')"
	if [[ "$written" -ne "$expected" ]]; then
		printf '%s\n' "$out"
		fail "file-count written=$written expected=$expected"
	fi
	printf '%s dir=%s\n' "$sentinel" "$export_dir"
	exit 0
fi

printf '%s\n' "$out"
if [[ "$sentinel" == H2BT_EXPORT_FAIL* ]]; then
	echo "$sentinel"
	exit 1
fi
fail no-sentinel
