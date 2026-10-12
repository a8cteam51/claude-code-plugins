#!/usr/bin/env bash
#
# import-media.sh — import design images into a Studio site's media library, and keep the
# run's media manifest (file name -> attachment id, URL and dimensions) up to date.
#
#   import-media.sh --site-path <site> --list <media-list.json> [--manifest <path>]
#
# <media-list.json> is an array of items:
#   { "file": "<path>", "title": "<attachment title>", "alt": "<alternative text>",
#     "name": "<file name in the library>" }
# "file" is absolute, or relative to the list file's directory. "name" defaults to the file's
# own name and is what the manifest is keyed by, so it has to be unique in the list: two
# sources with the same file name need a "name" each. "title" and "alt" are optional.
#
# The work is done by import-media.php.tmpl through `studio wp eval-file`, staged inside the
# site directory, as every file PHP reads has to be (a source outside the site is copied in
# for the import). It can be run again: an attachment is found by its source meta key before
# anything is uploaded. Originals are not scaled down. The import runs as an administrator,
# because Safe SVG refuses an SVG from no user.
#
# Prints one FAILED line per file that was not imported, then the sentinel:
#   H2BT_MEDIA items=<n> new=<n> kept=<n> failed=<n> manifest_entries=<n> php=<version> manifest=<path>
# or H2BT_MEDIA_FAIL reason=<why>. Exits 0 only on H2BT_MEDIA with failed=0.
#
set -euo pipefail

# From bash 5.2 an `&` in the replacement of ${var//pattern/replacement} stands for the
# matched text. Only a generated file name is substituted below.
shopt -u patsub_replacement 2>/dev/null || true

usage() {
	cat <<'EOF'
Usage:
  import-media.sh --site-path <site> --list <media-list.json> [--manifest <path>]

Imports the images a JSON list names into the site's media library and writes each one's
attachment id, URL and dimensions to the media manifest (default <site>/.h2bt/media.json,
merged with what is there). The list is an array of
  { "file": "<path>", "title": "<title>", "alt": "<alternative text>", "name": "<library file name>" }
with "file" absolute or relative to the list. Safe to repeat: nothing is uploaded twice.

Last line: H2BT_MEDIA items=<n> new=<n> kept=<n> failed=<n> ... manifest=<path>, or
H2BT_MEDIA_FAIL reason=<why>. Exits non-zero unless every file was imported.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

cannot_import() { # cannot_import <reason, no spaces> <message>
	echo "$2" >&2
	echo "H2BT_MEDIA_FAIL reason=$1"
	exit 1
}

site_path=""
list=""
manifest=""

while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) need_value "$@"; site_path="$2"; shift 2 ;;
		--list) need_value "$@"; list="$2"; shift 2 ;;
		--manifest) need_value "$@"; manifest="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$site_path" && -n "$list" ]] || { usage >&2; exit 2; }
[[ -d "$site_path" ]] || cannot_import site-not-found "Site path not found: $site_path"
[[ -r "$list" ]] || cannot_import list-not-found "List file not readable: $list"
command -v studio >/dev/null 2>&1 || cannot_import no-studio "studio CLI not found"
command -v python3 >/dev/null 2>&1 || cannot_import no-python3 "python3 is required to read the list"

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
tmpl="$script_dir/import-media.php.tmpl"
[[ -r "$tmpl" ]] || cannot_import template-missing "Template not found: $tmpl"

site_path="$(cd "$site_path" && pwd -P)"
stage_dir="$site_path/.h2bt"
mkdir -p "$stage_dir"
[[ -n "$manifest" ]] || manifest="$stage_dir/media.json"

job_basename="content-media-$$.json"
script_basename="write-media-$$.php"
copies_dir="$stage_dir/content-media-$$"

cleanup() { rm -rf "$copies_dir"; }
trap cleanup EXIT

# Reads the list, checks it, copies in any source that is outside the site, and writes the job.
# Its one line of output goes through a file: bash 3.2 misparses a here-document inside $( ).
job_report="$(mktemp "${TMPDIR:-/tmp}/h2bt-media.XXXXXX")"
job_status=0
python3 -I - "$site_path" "$list" "$manifest" "$stage_dir/$job_basename" "$copies_dir" >"$job_report" <<'PY' || job_status=$?
import json
import os
import re
import shutil
import sys

site, list_path, manifest, job_path, copies = sys.argv[1:6]
site = os.path.realpath(site)


def stop(reason, message):
    print('%s\t%s' % (reason, message))
    sys.exit(1)


manifest = os.path.realpath(os.path.join(os.getcwd(), manifest))
if not manifest.startswith(site + os.sep):
    stop('manifest-outside-site', 'The manifest has to be inside the site directory: %s' % manifest)

try:
    with open(list_path, encoding='utf-8') as handle:
        items = json.load(handle)
except (OSError, ValueError) as error:
    stop('bad-list', 'The list could not be read: %s' % error)
if not isinstance(items, list) or not items:
    stop('bad-list', 'The list has to be a JSON array with at least one item.')

base = os.path.dirname(os.path.realpath(list_path))
job, seen = [], {}
for index, item in enumerate(items):
    if not isinstance(item, dict) or not isinstance(item.get('file'), str) or not item['file']:
        stop('bad-list', 'Item %d has no "file".' % index)
    source = os.path.realpath(os.path.join(base, item['file']))
    if not os.path.isfile(source):
        stop('file-not-found', 'Item %d: no such file: %s' % (index, source))
    name = item.get('name') or os.path.basename(source)
    if not isinstance(name, str) or not re.match(r'^[A-Za-z0-9][A-Za-z0-9._-]*\.[A-Za-z0-9]+$', name):
        stop('bad-name', 'Item %d: "%s" is not a file name the library can take (letters, digits, dot, dash, underscore, with an extension).' % (index, name))
    if os.path.splitext(name)[1].lower() != os.path.splitext(source)[1].lower():
        stop('bad-name', 'Item %d: "%s" does not have the extension of its file (%s).' % (index, name, os.path.basename(source)))
    if name.lower() in seen:
        stop('duplicate-name', 'Items %d and %d would both be "%s" in the library: give each a "name".' % (seen[name.lower()], index, name))
    seen[name.lower()] = index
    for key in ('title', 'alt'):
        if key in item and not isinstance(item[key], str):
            stop('bad-list', 'Item %d: "%s" has to be text.' % (index, key))
    if source.startswith(site + os.sep):
        path = os.path.relpath(source, site)
    else:
        os.makedirs(copies, exist_ok=True)
        staged = os.path.join(copies, '%d-%s' % (index, name))
        shutil.copyfile(source, staged)
        path = os.path.relpath(staged, site)
    entry = {'name': name, 'path': path, 'source': item['file']}
    for key in ('title', 'alt'):
        if key in item:
            entry[key] = item[key]
    job.append(entry)

with open(job_path, 'w', encoding='utf-8') as handle:
    json.dump({'manifest': os.path.relpath(manifest, site), 'items': job}, handle)
print('ok\t%s' % manifest)
PY
problem="$(cat "$job_report")"
rm -f "$job_report"
if [[ "$job_status" -ne 0 || "$problem" != ok$'\t'* ]]; then
	rm -f "$stage_dir/$job_basename"
	[[ "$problem" == *$'\t'* ]] || problem="list-not-read"$'\t'"The list could not be prepared: ${problem:-python3 failed}"
	cannot_import "${problem%%$'\t'*}" "${problem#*$'\t'}"
fi
manifest="${problem#*$'\t'}"

tmpl_body="$(cat "$tmpl")"
tmpl_body="${tmpl_body//__JOB_FILE__/$job_basename}"
printf '%s\n' "$tmpl_body" > "$stage_dir/$script_basename"

out="$(cd "$site_path" && studio wp eval-file ".h2bt/$script_basename" --path="$site_path" 2>&1)" || true

# Studio can print PHP notices around the script's output: show only the script's own lines.
failures="$(grep -E '^FAILED ' <<<"$out" || true)"
sentinel="$(grep -E '^H2BT_MEDIA(_FAIL)? ' <<<"$out" | tail -1 || true)"

if [[ "$sentinel" == "H2BT_MEDIA "* ]]; then
	rm -f "$stage_dir/$job_basename" "$stage_dir/$script_basename"
	[[ -z "$failures" ]] || printf '%s\n' "$failures"
	printf '%s manifest=%s\n' "$sentinel" "$manifest"
	[[ "$sentinel" == *" failed=0 "* ]] || exit 1
	exit 0
fi

if [[ -n "$sentinel" ]]; then
	printf '%s\n' "$sentinel"
else
	printf '%s\n' "$out"
	echo "H2BT_MEDIA_FAIL reason=no-sentinel"
fi
echo "IMPORT FAILED: the import script did not finish (staged files kept in $stage_dir)" >&2
exit 1
