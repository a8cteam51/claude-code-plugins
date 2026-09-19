#!/usr/bin/env bash
# Unpack a drop folder of plugin zips and/or directories into one clean staging
# folder: one directory per plugin, no archive wrappers, no macOS junk.
#
# Usage: stage_updates.sh --source DIR [--dest DIR] [--force]
#
# Defaults --dest to <source>/.staged. Prints one OK line per staged plugin and
# a WARN line for anything it could not unpack. Written for bash 3.2 (macOS).
set -euo pipefail

SOURCE=""
DEST=""
FORCE=""

usage() { sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --source) SOURCE="${2:-}"; shift 2;;
    --dest)   DEST="${2:-}"; shift 2;;
    --force)  FORCE="1"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2;;
  esac
done

[ -n "$SOURCE" ] || { echo "--source is required" >&2; exit 2; }
[ -d "$SOURCE" ] || { echo "Source folder not found: $SOURCE" >&2; exit 1; }
command -v unzip >/dev/null || { echo "unzip not found" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync not found" >&2; exit 1; }

SOURCE="$(cd "$SOURCE" && pwd)"
DEST="${DEST:-$SOURCE/.staged}"

if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null)" ]; then
  if [ -n "$FORCE" ]; then
    find "$DEST" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  else
    echo "Destination is not empty: $DEST (pass --force to replace its contents)" >&2
    exit 1
  fi
fi
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"

scrub() {
  find "$1" \( -name '.DS_Store' -o -name '._*' -o -name 'Thumbs.db' \) -delete 2>/dev/null || true
  find "$1" -type d -name '__MACOSX' -prune -exec rm -rf {} + 2>/dev/null || true
}

copy_tree() {  # copy_tree <src-dir> <dest-dir>
  rsync -a --exclude '.DS_Store' --exclude '__MACOSX' --exclude '._*' \
        --exclude '.git' --exclude '.svn' --exclude 'Thumbs.db' "$1/" "$2/"
}

# woocommerce.4.2.1.zip / woocommerce-4.2.1.zip / woocommerce_v4.2.1.zip -> woocommerce
slug_from_archive() {
  local base="${1##*/}"
  # -iname finds .ZIP and .Zip too, so strip the extension case-insensitively.
  base="$(printf '%s' "$base" | sed -E 's/\.[Zz][Ii][Pp]$//')"
  printf '%s' "$base" | sed -E 's/[-_.]v?[0-9]+([._-][0-9A-Za-z]+)*$//'
}

place() {  # place <src-dir> <slug> <origin-label>
  local src="$1" slug="$2" origin="$3" main=""
  if [ -e "$DEST/$slug" ]; then
    echo "WARN  $origin: '$slug' is already staged - skipped (two sources for the same plugin?)"
    return
  fi
  copy_tree "$src" "$DEST/$slug"
  scrub "$DEST/$slug"
  main="$(find "$DEST/$slug" -maxdepth 1 -type f -name '*.php' -exec grep -lIiE '^[[:space:]]*\*?[[:space:]]*Plugin Name:' {} + 2>/dev/null | head -n1 || true)"
  if [ -n "$main" ]; then
    echo "OK    $slug  (from $origin)"
  else
    echo "WARN  $slug: staged from $origin but no top-level PHP file has a Plugin Name header"
  fi
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- archives ---------------------------------------------------------------
find "$SOURCE" -mindepth 1 -maxdepth 1 -type f -iname '*.zip' | sort | while IFS= read -r archive; do
  work="$TMP/$(basename "$archive" | tr -c 'A-Za-z0-9._-' '_')"
  rm -rf "$work"; mkdir -p "$work"
  if ! unzip -qq -o "$archive" -d "$work" >/dev/null 2>&1; then
    echo "WARN  $(basename "$archive"): unzip failed - inspect it by hand"
    continue
  fi
  scrub "$work"
  dir_count="$(find "$work" -mindepth 1 -maxdepth 1 -type d -not -name '.*' | wc -l | tr -d ' ')"
  file_count="$(find "$work" -mindepth 1 -maxdepth 1 -type f -not -name '.*' | wc -l | tr -d ' ')"
  first_dir="$(find "$work" -mindepth 1 -maxdepth 1 -type d -not -name '.*' | sort | head -n1)"

  # Classify on where the plugin header lives, not on file counts. Counting
  # misreads both common layouts: a wrapper directory shipped beside a stray
  # license.txt looks "flat", and a genuinely flat plugin with an includes/
  # directory looks "wrapped".
  root_main="$(find "$work" -maxdepth 1 -type f -name '*.php' -exec grep -lIiE '^[[:space:]]*\*?[[:space:]]*Plugin Name:' {} + 2>/dev/null | head -n1 || true)"

  if [ -n "$root_main" ]; then
    # The archive root is the plugin folder.
    place "$work" "$(slug_from_archive "$archive")" "$(basename "$archive") (flat archive)"
  elif [ "$dir_count" = "1" ]; then
    # One wrapper directory, whatever else sits beside it at the root.
    place "$first_dir" "$(basename "$first_dir")" "$(basename "$archive")"
  elif [ "$dir_count" != "0" ]; then
    echo "WARN  $(basename "$archive"): $dir_count top-level folders and no plugin header at the root - unpack it by hand"
  elif [ "$file_count" != "0" ]; then
    place "$work" "$(slug_from_archive "$archive")" "$(basename "$archive") (flat archive)"
  else
    echo "WARN  $(basename "$archive"): archive looks empty"
  fi
done

# --- already-unpacked folders ----------------------------------------------
find "$SOURCE" -mindepth 1 -maxdepth 1 -type d -not -name '.*' -not -name '__MACOSX' | sort | while IFS= read -r entry; do
  [ "$entry" = "$DEST" ] && continue
  place "$entry" "$(basename "$entry")" "folder $(basename "$entry")/"
done

count="$(find "$DEST" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
echo
echo "Staged $count plugin folder(s) in: $DEST"
