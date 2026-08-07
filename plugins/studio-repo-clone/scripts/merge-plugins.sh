#!/usr/bin/env bash
# studio-site-from-host: merge a team51 plugin archive into a Studio site's
# wp-content/plugins.
#
# wp-content here IS the cloned repo, so anything the repo already tracks must
# win: the production archive is only used to fill in plugins the repo does not
# ship (premium/third-party ones that live outside version control). Existing
# entries are left untouched unless --overwrite is passed explicitly.
#
# Usage:
#   merge-plugins.sh --archive <path.tar.gz> --target-dir <site-root> [--overwrite]

set -euo pipefail

usage() {
  cat <<EOF
Usage: merge-plugins.sh --archive <path.tar.gz> --target-dir <site-root> [--overwrite]

  --archive     Archive produced by pull-site-plugins.sh. Must contain a
                top-level plugins/ directory.
  --target-dir  Studio site root (the directory containing wp-content/).
  --overwrite   Replace plugins that already exist in wp-content/plugins.
                Off by default: repo-tracked plugins win.

  -h, --help    Show this help.

On success prints a machine-readable block on stdout:
  RESULT_ADDED=<comma-separated names, empty if none>
  RESULT_SKIPPED=<comma-separated names, empty if none>
  RESULT_REPLACED=<comma-separated names, empty if none>

Requires: tar on PATH.
EOF
}

archive=""
target=""
overwrite=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive)
      [[ $# -ge 2 ]] || { echo "merge-plugins.sh: --archive needs a value" >&2; exit 2; }
      archive="$2"; shift 2 ;;
    --target-dir)
      [[ $# -ge 2 ]] || { echo "merge-plugins.sh: --target-dir needs a value" >&2; exit 2; }
      target="$2"; shift 2 ;;
    --overwrite) overwrite=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "merge-plugins.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$archive" || -z "$target" ]]; then
  echo "merge-plugins.sh: --archive and --target-dir are required" >&2
  usage >&2
  exit 2
fi

[[ -s "$archive" ]] || { echo "merge-plugins.sh: archive missing or empty: $archive" >&2; exit 1; }

case "$target" in
  /*) abs_target="$target" ;;
  *)  abs_target="$PWD/$target" ;;
esac

if [[ ! -d "$abs_target/wp-content" ]]; then
  echo "merge-plugins.sh: $abs_target/wp-content does not exist; is this a WordPress site?" >&2
  exit 1
fi

plugins_dir="$abs_target/wp-content/plugins"
mkdir -p "$plugins_dir"

work="$(mktemp -d 2>/dev/null || mktemp -d -t merge-plugins)"
trap 'rm -rf "$work"' EXIT

echo "==> extracting $archive"
tar -xzf "$archive" -C "$work"

src="$work/plugins"
if [[ ! -d "$src" ]]; then
  echo "merge-plugins.sh: unexpected archive layout (no top-level plugins/ dir)" >&2
  exit 1
fi

added=()
skipped=()
replaced=()

shopt -s dotglob nullglob
for entry in "$src"/*; do
  name="$(basename "$entry")"
  dest="$plugins_dir/$name"

  # WordPress' own silence stub, never a plugin — counting it as one is noise.
  [[ "$name" == "index.php" ]] && continue

  if [[ -e "$dest" ]]; then
    if (( overwrite == 1 )); then
      rm -rf "$dest"
      mv "$entry" "$dest"
      replaced+=("$name")
      echo "    replaced: $name"
    else
      skipped+=("$name")
      echo "    skipped (already present): $name"
    fi
    continue
  fi

  mv "$entry" "$dest"
  added+=("$name")
  echo "    added: $name"
done
shopt -u dotglob nullglob

join_list() {
  local IFS=,
  echo "$*"
}

echo
echo "RESULT_ADDED=$(join_list "${added[@]+"${added[@]}"}")"
echo "RESULT_SKIPPED=$(join_list "${skipped[@]+"${skipped[@]}"}")"
echo "RESULT_REPLACED=$(join_list "${replaced[@]+"${replaced[@]}"}")"
