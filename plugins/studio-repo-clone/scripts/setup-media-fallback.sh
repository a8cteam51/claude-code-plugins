#!/usr/bin/env bash
# studio-site-from-host: serve missing uploads from production/staging instead
# of pulling the whole uploads directory down.
#
# Installs billerickson/be-media-from-production and defines
# BE_MEDIA_FROM_PRODUCTION_URL in wp-config.php. Local files always win; only
# missing ones fall through to the remote host.
#
# Usage:
#   setup-media-fallback.sh --target-dir <site-root> --production-url <url>

set -euo pipefail

PLUGIN_SLUG="be-media-from-production"
PLUGIN_ZIP="https://github.com/billerickson/be-media-from-production/releases/latest/download/be-media-from-production.zip"

usage() {
  cat <<EOF
Usage: setup-media-fallback.sh --target-dir <site-root> --production-url <url>

  --target-dir      Studio site root (the directory containing wp-content/).
  --production-url  Origin to fetch missing uploads from, e.g.
                    https://example.com or https://example.wpcomstaging.com.
                    Scheme is added if omitted.

  -h, --help        Show this help.

Requires: studio (Studio CLI) on PATH, with the site already registered.
EOF
}

target=""
prod_url=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      [[ $# -ge 2 ]] || { echo "setup-media-fallback.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    --production-url)
      [[ $# -ge 2 ]] || { echo "setup-media-fallback.sh: --production-url needs a value" >&2; exit 2; }
      prod_url="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "setup-media-fallback.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$target" || -z "$prod_url" ]]; then
  echo "setup-media-fallback.sh: --target-dir and --production-url are required" >&2
  usage >&2
  exit 2
fi

command -v studio >/dev/null 2>&1 || {
  echo "setup-media-fallback.sh: 'studio' CLI not found on PATH." >&2
  exit 1
}

case "$prod_url" in
  http://*|https://*) ;;
  *) prod_url="https://$prod_url" ;;
esac
prod_url="${prod_url%/}"

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

if [[ ! -d "$abs_target/wp-content" ]]; then
  echo "setup-media-fallback.sh: $abs_target/wp-content does not exist; is this a WordPress site?" >&2
  exit 1
fi

echo "==> installing $PLUGIN_SLUG"
studio wp --path "$abs_target" plugin install "$PLUGIN_ZIP" --force --activate

echo "==> defining BE_MEDIA_FROM_PRODUCTION_URL as $prod_url"
studio wp --path "$abs_target" config set BE_MEDIA_FROM_PRODUCTION_URL "$prod_url" --type=constant

echo
echo "RESULT_MEDIA_URL=$prod_url"
