#!/usr/bin/env bash
# studio-site-from-host: pull the wp-content/plugins archive off a hosted site
# via the team51 CLI, and report which host the site actually lives on.
#
# Doubles as site identification: the team51 download commands echo the site's
# display name, ID and URL before they start, so a single invocation tells us
# both "is this Pressable or WPCOM" and "what is the production URL".
#
# Host detection: Pressable is tried first (team51's Pressable lookup throws
# "Invalid Pressable site." for anything it doesn't own), and only that specific
# failure falls through to WPCOM. Any other failure - SSH, SFTP, auth, empty
# archive - is reported as-is rather than masked by a pointless second attempt.
#
# Usage:
#   pull-site-plugins.sh --site <id-or-domain> [--host pressable|wpcom|auto] [--archive <path>]

set -euo pipefail

usage() {
  cat <<EOF
Usage: pull-site-plugins.sh --site <id-or-domain> [--host pressable|wpcom|auto] [--archive <path>]

  --site      Domain or numeric site ID on Pressable or WordPress.com.
  --host      Which host to pull from. Default 'auto': try Pressable, fall
              back to WPCOM only if Pressable reports the site as unknown.
  --archive   Where to write the .tar.gz. Default: a temp file.

  -h, --help  Show this help.

On success prints a machine-readable block on stdout:
  RESULT_HOST=pressable|wpcom
  RESULT_SITE_ID=<id>
  RESULT_SITE_URL=<url or domain as reported by the host>
  RESULT_ARCHIVE=<path to .tar.gz>

Requires: team51 (with a loaded identity) on PATH.
EOF
}

site=""
host="auto"
archive=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site)
      [[ $# -ge 2 ]] || { echo "pull-site-plugins.sh: --site needs a value" >&2; exit 2; }
      site="$2"; shift 2 ;;
    --host)
      [[ $# -ge 2 ]] || { echo "pull-site-plugins.sh: --host needs a value" >&2; exit 2; }
      host="$2"; shift 2 ;;
    --archive)
      [[ $# -ge 2 ]] || { echo "pull-site-plugins.sh: --archive needs a value" >&2; exit 2; }
      archive="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "pull-site-plugins.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$site" ]]; then
  echo "pull-site-plugins.sh: --site is required" >&2
  usage >&2
  exit 2
fi

case "$host" in
  auto|pressable|wpcom) ;;
  *) echo "pull-site-plugins.sh: --host must be one of: auto, pressable, wpcom" >&2; exit 2 ;;
esac

if ! command -v team51 >/dev/null 2>&1; then
  echo "pull-site-plugins.sh: 'team51' CLI not found on PATH." >&2
  exit 1
fi

if [[ -z "$archive" ]]; then
  site_slug="$(printf '%s' "$site" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' '-' | sed -E 's/-+/-/g; s/^-|-$//g')"
  [[ -n "$site_slug" ]] || site_slug="site"
  archive="${TMPDIR:-/tmp}/team51-plugins-${site_slug}-$(date -u +%Y%m%d-%H%M%S).tar.gz"
fi

case "$archive" in
  /*) abs_archive="$archive" ;;
  *)  abs_archive="$PWD/$archive" ;;
esac
mkdir -p "$(dirname "$abs_archive")"

log="$(mktemp 2>/dev/null || mktemp -t pull-site-plugins)"
trap 'rm -f "$log"' EXIT

# Runs one team51 download command, streaming its output to stderr (so the
# operator sees progress) while capturing it for parsing. Returns the command's
# exit status; the captured output is left in "$log".
attempt() {
  local cmd="$1"
  : > "$log"
  set +e
  team51 --no-ansi -n "$cmd" "$site" --destination="$abs_archive" 2>&1 | tee "$log" >&2
  local rc=${PIPESTATUS[0]}
  set -e
  return "$rc"
}

# Both download commands announce themselves as:
#   Downloading plugins from <Host> site <name> (ID <id>, URL <url>) to <dest>.
parse_field() {
  sed -nE "s/.*\(ID ([^,]+), URL ([^)]*)\).*/\\$1/p" "$log" | head -n 1
}

resolved_host=""
if [[ "$host" == "pressable" || "$host" == "auto" ]]; then
  echo "==> trying Pressable: $site" >&2
  if attempt "pressable:download-site-plugins"; then
    resolved_host="pressable"
  elif [[ "$host" == "auto" ]] && grep -qi "Invalid Pressable site" "$log"; then
    echo "==> not a Pressable site; falling back to WordPress.com" >&2
  else
    echo "pull-site-plugins.sh: Pressable plugin download failed (see output above)" >&2
    exit 1
  fi
fi

if [[ -z "$resolved_host" ]]; then
  echo "==> trying WordPress.com: $site" >&2
  if attempt "wpcom:download-site-plugins"; then
    resolved_host="wpcom"
  else
    echo "pull-site-plugins.sh: WPCOM plugin download failed (see output above)" >&2
    exit 1
  fi
fi

if [[ ! -s "$abs_archive" ]]; then
  echo "pull-site-plugins.sh: team51 reported success but $abs_archive is missing or empty" >&2
  exit 1
fi

site_id="$(parse_field 1)"
site_url="$(parse_field 2)"

echo
echo "RESULT_HOST=$resolved_host"
echo "RESULT_SITE_ID=$site_id"
echo "RESULT_SITE_URL=$site_url"
echo "RESULT_ARCHIVE=$abs_archive"
