#!/usr/bin/env bash
# studio-site-from-host: pull the hosted site's database and import it into the
# local Studio site.
#
# Studio's importer speaks MySQL dialect even though it stores SQLite, so a
# straight mysqldump imports cleanly. It also rewrites siteurl/home and most
# serialized content to the local domain on the way in; the search-replace here
# only mops up the stragglers it misses (typically hardcoded URLs in post bodies).
#
# IMPORTANT: importing replaces wp_options, and that includes `active_plugins`.
# Any locally-activated plugin - safety-net, be-media-from-production - is
# deactivated by the import and MUST be reactivated afterwards. This script does
# that itself so the caller cannot forget.
#
# Usage:
#   pull-database.sh --site <id-or-domain> --host <pressable|wpcom> \
#     --target-dir <site-root> --source-host <production-hostname> \
#     --local-domain <name.local> [--dump <path>] [--keep-dump]

set -euo pipefail

usage() {
  cat <<EOF
Usage: pull-database.sh --site <id-or-domain> --host <pressable|wpcom> \\
         --target-dir <site-root> --source-host <production-hostname> \\
         --local-domain <name.local> [--dump <path>] [--keep-dump]

  --site          Domain or numeric site ID on the host.
  --host          'pressable' or 'wpcom'. Use the host resolved by
                  pull-site-plugins.sh; this script does not re-detect it.
  --target-dir    Studio site root (the directory containing wp-content/).
  --source-host   Production hostname to rewrite, WITHOUT scheme, e.g.
                  example.com. Both http and https forms are caught.
  --local-domain  The site's local domain, e.g. example.local.
  --dump          Where to write the .sql dump. Default: a temp file.
  --keep-dump     Keep the dump after a successful import. Default: keep.
                  Present for symmetry; the dump is never auto-deleted.

  -h, --help      Show this help.

On success prints a machine-readable block on stdout:
  RESULT_DUMP=<path to .sql>
  RESULT_POSTS=<post count after import>
  RESULT_USERS=<user count after import>
  RESULT_REACTIVATED=<comma-separated plugins re-activated>

Requires: team51 (with a loaded identity) and studio on PATH.
EOF
}

site=""
host=""
target=""
source_host=""
local_domain=""
dump=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --site needs a value" >&2; exit 2; }
      site="$2"; shift 2 ;;
    --host)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --host needs a value" >&2; exit 2; }
      host="$2"; shift 2 ;;
    --target-dir)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    --source-host)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --source-host needs a value" >&2; exit 2; }
      source_host="$2"; shift 2 ;;
    --local-domain)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --local-domain needs a value" >&2; exit 2; }
      local_domain="$2"; shift 2 ;;
    --dump)
      [[ $# -ge 2 ]] || { echo "pull-database.sh: --dump needs a value" >&2; exit 2; }
      dump="$2"; shift 2 ;;
    --keep-dump) shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "pull-database.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$site" || -z "$host" || -z "$target" || -z "$source_host" || -z "$local_domain" ]]; then
  echo "pull-database.sh: --site, --host, --target-dir, --source-host and --local-domain are required" >&2
  usage >&2
  exit 2
fi

case "$host" in
  pressable|wpcom) ;;
  *) echo "pull-database.sh: --host must be 'pressable' or 'wpcom'" >&2; exit 2 ;;
esac

for c in team51 studio; do
  command -v "$c" >/dev/null 2>&1 || { echo "pull-database.sh: '$c' not found on PATH." >&2; exit 1; }
done

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

if [[ ! -d "$abs_target/wp-content" ]]; then
  echo "pull-database.sh: $abs_target/wp-content does not exist; is this a WordPress site?" >&2
  exit 1
fi

# Strip any scheme/trailing slash the caller passed by mistake - search-replace
# needs the bare hostname so both http:// and https:// forms are rewritten.
source_host="${source_host#http://}"
source_host="${source_host#https://}"
source_host="${source_host%%/*}"

if [[ -z "$dump" ]]; then
  site_slug="$(printf '%s' "$site" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g')"
  [[ -n "$site_slug" ]] || site_slug="site"
  dump="${TMPDIR:-/tmp}/team51-db-${site_slug}-$(date -u +%Y%m%d-%H%M%S).sql"
fi

case "$dump" in
  /*) abs_dump="$dump" ;;
  *)  abs_dump="$PWD/$dump" ;;
esac
mkdir -p "$(dirname "$abs_dump")"

# Capture which plugins are active locally BEFORE the import blows away
# wp_options, so they can be restored afterwards.
echo "==> recording locally active plugins"
pre_active="$(studio wp --path "$abs_target" plugin list --status=active --field=name 2>/dev/null \
  | tr -d '\r' | grep -E '^[a-z0-9._-]+$' || true)"

echo "==> downloading database from $host site $site"
team51 --no-ansi -n "${host}:download-site-database" "$site" --destination="$abs_dump" >&2

if [[ ! -s "$abs_dump" ]]; then
  echo "pull-database.sh: team51 reported success but $abs_dump is missing or empty" >&2
  exit 1
fi
echo "==> dump: $abs_dump ($(du -h "$abs_dump" | cut -f1))"

echo "==> importing into $abs_target"
studio import --path "$abs_target" "$abs_dump" >&2

echo "==> rewriting $source_host -> $local_domain"
# --skip-columns=guid: WordPress treats guid as a permanent identifier, not a URL.
# Note: on SQLite the reported replacement count is unreliable; verify with the
# counts printed below rather than trusting that number.
studio wp --path "$abs_target" search-replace "$source_host" "$local_domain" \
  --all-tables-with-prefix --skip-columns=guid >&2

# The import replaced active_plugins with production's list. Restore anything
# that was active locally and is not active now - notably safety-net.
reactivated=""
if [[ -n "$pre_active" ]]; then
  post_active="$(studio wp --path "$abs_target" plugin list --status=active --field=name 2>/dev/null \
    | tr -d '\r' | grep -E '^[a-z0-9._-]+$' || true)"
  to_activate=""
  while IFS= read -r p; do
    [[ -n "$p" ]] || continue
    if ! printf '%s\n' "$post_active" | grep -qxF "$p"; then
      to_activate="$to_activate $p"
    fi
  done <<< "$pre_active"

  if [[ -n "$to_activate" ]]; then
    echo "==> reactivating plugins deactivated by the import:$to_activate"
    # shellcheck disable=SC2086
    if studio wp --path "$abs_target" plugin activate $to_activate >&2; then
      reactivated="$(echo "$to_activate" | tr ' ' ',' | sed -E 's/^,|,$//g')"
    else
      echo "pull-database.sh: failed to reactivate:$to_activate - activate them from wp-admin" >&2
    fi
  fi
fi

posts="$(studio wp --path "$abs_target" post list --post_type=post --format=count 2>/dev/null | tr -dc '0-9' || true)"
users="$(studio wp --path "$abs_target" user list --format=count 2>/dev/null | tr -dc '0-9' || true)"

echo
echo "RESULT_DUMP=$abs_dump"
echo "RESULT_POSTS=${posts:-unknown}"
echo "RESULT_USERS=${users:-unknown}"
echo "RESULT_REACTIVATED=$reactivated"
