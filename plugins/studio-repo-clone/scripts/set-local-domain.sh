#!/usr/bin/env bash
# studio-site-from-host: point a Studio site at a <name>.local custom domain.
#
# scaffold.sh (studio-repo-clone) creates the site on a localhost port; this
# gives it the .local hostname that mirrors the production domain, matching the
# convention every other site in the user's Studio install already follows.
#
# Usage:
#   set-local-domain.sh --target-dir <site-root> --domain <name.local> [--no-https]

set -euo pipefail

usage() {
  cat <<EOF
Usage: set-local-domain.sh --target-dir <site-root> --domain <name.local> [--no-https]

  --target-dir  Studio site root, as registered with 'studio site create'.
  --domain      Custom domain. Studio requires it to end in '.local'.
  --no-https    Skip HTTPS. On by default to match existing Studio sites.

  -h, --help    Show this help.

Requires: studio (Studio CLI) on PATH. jq is used, when present, to check the
domain is not already claimed by another Studio site.
EOF
}

target=""
domain=""
https=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      [[ $# -ge 2 ]] || { echo "set-local-domain.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    --domain)
      [[ $# -ge 2 ]] || { echo "set-local-domain.sh: --domain needs a value" >&2; exit 2; }
      domain="$2"; shift 2 ;;
    --no-https) https=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "set-local-domain.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$target" || -z "$domain" ]]; then
  echo "set-local-domain.sh: --target-dir and --domain are required" >&2
  usage >&2
  exit 2
fi

if [[ "$domain" != *.local ]]; then
  echo "set-local-domain.sh: Studio requires the custom domain to end in '.local' (got: $domain)" >&2
  exit 2
fi

command -v studio >/dev/null 2>&1 || {
  echo "set-local-domain.sh: 'studio' CLI not found on PATH." >&2
  exit 1
}

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

# Refuse to steal a domain another site already owns; Studio will happily accept
# the duplicate and both sites then resolve unpredictably.
if command -v jq >/dev/null 2>&1; then
  owner="$(studio site list --format json 2>/dev/null \
    | jq -r --arg d "$domain" --arg p "$abs_target" \
        '.[] | select(.customDomain == $d) | select(.path != $p) | .path' 2>/dev/null | head -n 1)"
  if [[ -n "$owner" ]]; then
    echo "set-local-domain.sh: '$domain' is already used by the Studio site at $owner" >&2
    echo "set-local-domain.sh: pick a different domain and re-run" >&2
    exit 1
  fi
fi

echo "==> setting custom domain '$domain' on $abs_target"
if (( https == 1 )); then
  studio site set --path "$abs_target" --domain "$domain" --https
else
  studio site set --path "$abs_target" --domain "$domain"
fi

# Restart so the site is actually served on the new hostname. Non-fatal: a
# failure here just means the user starts it from the Studio app themselves.
echo "==> restarting site"
studio site stop --path "$abs_target" >/dev/null 2>&1 || true
if ! studio site start --path "$abs_target"; then
  echo "set-local-domain.sh: could not restart the site; start it manually with 'studio site start --path $abs_target'" >&2
fi

echo
if (( https == 1 )); then
  echo "RESULT_URL=https://$domain"
else
  echo "RESULT_URL=http://$domain"
fi
