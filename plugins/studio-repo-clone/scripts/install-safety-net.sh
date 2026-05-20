#!/usr/bin/env bash
# studio-repo-clone: install + activate the a8cteam51/safety-net plugin into
# a Studio site's wp-content/plugins.
#
# safety-net is the team51 plugin that disables outbound emails and Jetpack
# on local dev environments. Every site set up via this plugin gets it
# installed so a fresh clone of a production wp-content can't accidentally
# email real users from a developer's laptop.
#
# Strategy:
#   1. Query GitHub's releases/latest API for the most recent release tag.
#   2. Download the source archive for that tag.
#   3. If wp-content/plugins/safety-net/ already exists, leave it alone
#      (the repo may have committed it, or a previous run already installed
#      it; we don't blindly overwrite the user's state).
#   4. Otherwise unpack the archive into wp-content/plugins/safety-net/.
#   5. Activate via `studio wp --path <target> plugin activate safety-net`.
#      Activation failure is non-fatal — the plugin files are on disk and
#      the user can activate from wp-admin.
#
# Usage:
#   install-safety-net.sh --target-dir <path>

set -euo pipefail

REPO="a8cteam51/safety-net"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"

usage() {
  cat <<EOF
Usage: install-safety-net.sh --target-dir <path>

  --target-dir  Studio site root (the directory that contains wp-content/).
                The plugin is installed at <target>/wp-content/plugins/safety-net
                and activated via 'studio wp'.

  -h, --help    Show this help.

Requires: curl, unzip, studio (Studio CLI) on PATH. The latest release tag is
resolved from $API_URL at runtime.
EOF
}

target=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      [[ $# -ge 2 ]] || { echo "install-safety-net.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "install-safety-net.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$target" ]]; then
  echo "install-safety-net.sh: --target-dir is required" >&2
  usage >&2
  exit 2
fi

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

if [[ ! -d "$abs_target/wp-content" ]]; then
  echo "install-safety-net.sh: $abs_target/wp-content does not exist; is this a WordPress site?" >&2
  exit 1
fi

plugins_dir="$abs_target/wp-content/plugins"
mkdir -p "$plugins_dir"

dest="$plugins_dir/safety-net"

if [[ -d "$dest" ]]; then
  echo "==> safety-net already present at $dest; skipping download"
else
  echo "==> resolving latest safety-net release"
  # Parse the tag_name field from the JSON response without requiring jq.
  # Using sed -nE: match the first "tag_name": "..." pair and capture the value.
  latest_json="$(curl -fsSL "$API_URL")" || {
    echo "install-safety-net.sh: failed to fetch $API_URL" >&2
    exit 1
  }
  tag="$(printf '%s' "$latest_json" | sed -nE 's/.*"tag_name"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/p' | head -n 1)"
  if [[ -z "$tag" ]]; then
    echo "install-safety-net.sh: could not parse tag_name from $API_URL response" >&2
    exit 1
  fi
  echo "    tag: $tag"

  zip_url="https://github.com/${REPO}/archive/refs/tags/${tag}.zip"

  work="$(mktemp -d 2>/dev/null || mktemp -d -t safety-net)"
  trap 'rm -rf "$work"' EXIT

  echo "==> downloading $zip_url"
  curl -fsSL -o "$work/safety-net.zip" "$zip_url"

  mkdir "$work/extracted"
  unzip -q "$work/safety-net.zip" -d "$work/extracted"

  # GitHub source archives unpack as a single top-level dir like 'safety-net-1.5.8'.
  # Pick the first directory found rather than hardcoding the tag-based name,
  # since GitHub may rewrite the prefix (e.g. strip a leading 'v').
  src="$(find "$work/extracted" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [[ -z "$src" ]]; then
    echo "install-safety-net.sh: unexpected archive layout (no top-level dir)" >&2
    exit 1
  fi

  echo "==> installing into $dest"
  mv "$src" "$dest"
fi

# Activate via Studio's WP-CLI wrapper. Non-fatal: if activation fails (no
# studio CLI, site not registered, WP not bootstrapped yet) the plugin files
# are still on disk and the user can activate from wp-admin.
if ! command -v studio >/dev/null 2>&1; then
  echo "install-safety-net.sh: 'studio' CLI not on PATH; skipping activation" >&2
  exit 0
fi

echo "==> activating safety-net via 'studio wp'"
if studio wp --path "$abs_target" plugin activate safety-net; then
  echo "    activated"
else
  echo "install-safety-net.sh: 'studio wp ... plugin activate safety-net' failed; activate manually in wp-admin" >&2
fi
