#!/usr/bin/env bash
# export-pages.sh — export a Studio site's page content for standards-audit.sh --content-dir.
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  export-pages.sh --site-path <site>

Writes the block markup of every page and synced pattern (wp_block) on the Studio site,
published or not, to <site>/.h2bt/export/<post-type>-<id>.html, after removing the files
an earlier export left there. Content with no block delimiters is counted as skipped and
not written. Nothing is written to the database. Then audit the theme with it:

  standards-audit.sh --theme-dir <theme-dir> --content-dir <site>/.h2bt/export

A run audits the page sources it wrote (<site>/.h2bt/pages); what changed in the
database since is only in the export. The last line is
  H2BT_EXPORT_OK pages=<n> patterns=<n> skipped=<n> dir=<dir>
or H2BT_EXPORT_FAIL reason=<why>, and the exit code follows it.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

fail() { echo "H2BT_EXPORT_FAIL reason=$1"; exit 1; }

site_path=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || fail site-path-not-found
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

exported() { find "$export_dir" -maxdepth 1 -type f \( -name 'page-*.html' -o -name 'wp_block-*.html' \) "$@"; }

# A page deleted since the last export would otherwise still be audited.
exported -delete

script_basename="export-$$.php"
cleanup() { rm -f "$stage_dir/$script_basename"; }
trap cleanup EXIT

tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__EXPORT_DIR__/$export_name}"
printf '%s\n' "$tmpl_body" > "$stage_dir/$script_basename"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/$script_basename" --path="$site_path" 2>&1)" || true

# Studio can print PHP notices around the script's output.
sentinel="$(grep -E '^H2BT_EXPORT_(OK|FAIL)' <<<"$out" | tail -1 || true)"

if [[ "$sentinel" == H2BT_EXPORT_OK* ]]; then
	pages="$(sed -E 's/.* pages=([0-9]+).*/\1/' <<<"$sentinel")"
	patterns="$(sed -E 's/.* patterns=([0-9]+).*/\1/' <<<"$sentinel")"
	expected=$(( pages + patterns ))
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
