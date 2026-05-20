#!/usr/bin/env bash
# studio-repo-clone: convert an existing local Studio site's wp-content into a
# git clone of a GitHub repo, preserving the site's local runtime data.
#
# Strategy:
#   1. Preflight: validate inputs, git auth against the repo.
#   2. Rename existing wp-content -> wp-content-temp (single atomic step).
#   3. git clone the repo into a fresh wp-content.
#   4. Move the following runtime artefacts from wp-content-temp back into the
#      new wp-content (overwriting anything the repo shipped at the same path):
#        - uploads/ (whole folder)
#        - database/ (whole folder)
#        - db.php (single file)
#        - mu-plugins/sqlite-database-integration/ (single subdir; merged into
#          any mu-plugins/ the repo ships)
#        - plugins/* (each child individually; merged into any plugins/ the
#          repo ships, with local copies winning per child)
#        - themes/* (same per-child merge as plugins/)
#   5. Patch wp-content/.gitignore so Studio-generated runtime files don't show
#      up as uncommitted changes inside the cloned repo.
#   6. Leave wp-content-temp in place for the user to inspect and delete.
#
# Failure handling:
#   - If git clone fails after the rename, wp-content is restored from
#     wp-content-temp before exit.
#   - Failures during the restore step or .gitignore patch leave the half-
#     migrated state on disk so the user can fix and re-run by hand. We don't
#     try to undo a partially-restored move; doing so risks losing data.
#
# Usage:
#   clone-into-existing-site.sh --site-path <path> --repo <owner/repo|git-url>

set -euo pipefail

usage() {
  cat <<EOF
Usage: clone-into-existing-site.sh --site-path <path> --repo <owner/repo|git-url>

  --site-path  Path to an existing WordPress site directory (must contain
               wp-content/). The site's wp-content will be renamed to
               wp-content-temp and replaced with a fresh clone of --repo.
  --repo       GitHub shorthand (owner/repo) or full git URL. Cloned into
               <site-path>/wp-content.

  -h, --help   Show this help.

Requires: git on PATH.
EOF
}

site_path=""
repo=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --site-path)
      [[ $# -ge 2 ]] || { echo "clone-into-existing-site.sh: --site-path needs a value" >&2; exit 2; }
      site_path="$2"; shift 2 ;;
    --repo)
      [[ $# -ge 2 ]] || { echo "clone-into-existing-site.sh: --repo needs a value" >&2; exit 2; }
      repo="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "clone-into-existing-site.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$site_path" || -z "$repo" ]]; then
  echo "clone-into-existing-site.sh: --site-path and --repo are required" >&2
  usage >&2
  exit 2
fi

# Validate site-path. Must be a directory containing wp-content/.
if [[ ! -d "$site_path" ]]; then
  echo "clone-into-existing-site.sh: site-path is not a directory: $site_path" >&2
  exit 1
fi
case "$site_path" in
  /*) abs_site="$site_path" ;;
  *)  abs_site="$PWD/$site_path" ;;
esac

wp_content="$abs_site/wp-content"
wp_content_temp="$abs_site/wp-content-temp"

if [[ ! -d "$wp_content" ]]; then
  echo "clone-into-existing-site.sh: $wp_content does not exist; is this a WordPress site directory?" >&2
  exit 1
fi

if [[ -e "$wp_content_temp" ]]; then
  echo "clone-into-existing-site.sh: $wp_content_temp already exists; refusing to overwrite" >&2
  echo "clone-into-existing-site.sh: remove or rename it manually, then retry" >&2
  exit 1
fi

# Normalise repo. Reject shorthand that contains traversal segments.
if [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  case "$repo" in
    *..*|.*|*/.*) echo "clone-into-existing-site.sh: invalid repo shorthand: $repo" >&2; exit 2 ;;
  esac
  repo_url="https://github.com/${repo}.git"
else
  repo_url="$repo"
fi

# Preflight: confirm we can reach + auth to the repo before mutating anything.
# Disable the credential prompter so private repos fail fast on missing creds
# instead of hanging on a TTY prompt.
echo "==> checking repo access: $repo_url"
if ! GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code "$repo_url" HEAD >/dev/null 2>&1; then
  echo "clone-into-existing-site.sh: cannot reach or authenticate to $repo_url" >&2
  echo "clone-into-existing-site.sh: for private repos configure a git credential helper (e.g. 'gh auth login') or SSH agent and retry" >&2
  exit 1
fi

echo "==> site:   $abs_site"
echo "==> repo:   $repo_url"

# Rollback state. Only the rename is reversible without risk of clobbering
# restored files; once the clone succeeds we commit to the new layout.
renamed=0
cloned=0

_cleanup() {
  local rc=$?
  trap - EXIT
  if (( rc != 0 && renamed == 1 && cloned == 0 )); then
    echo "clone-into-existing-site.sh: clone failed; restoring wp-content from wp-content-temp" >&2
    rm -rf "$wp_content"
    mv "$wp_content_temp" "$wp_content"
  fi
  exit "$rc"
}
trap _cleanup EXIT

echo "==> renaming wp-content -> wp-content-temp"
mv "$wp_content" "$wp_content_temp"
renamed=1

echo "==> cloning $repo_url into wp-content"
git clone "$repo_url" "$wp_content"
cloned=1

# Restore Studio runtime data. Each item is independent; missing items are
# skipped. If the cloned repo shipped a path at the same location, the temp
# version overwrites it (runtime data wins — the repo can't know what the
# user's local DB / uploads / activated plugins look like).
restore_path() {
  local rel="$1"
  local src="$wp_content_temp/$rel"
  local dest="$wp_content/$rel"
  if [[ ! -e "$src" ]]; then
    echo "    skip:  $rel (not present in wp-content-temp)"
    return 0
  fi
  mkdir -p "$(dirname "$dest")"
  if [[ -e "$dest" ]]; then
    rm -rf "$dest"
  fi
  mv "$src" "$dest"
  echo "    moved: $rel"
}

# Move each child of <rel>/ from wp-content-temp into wp-content, rather than
# moving the whole directory. This matters for paths like plugins/ and themes/
# where the cloned repo may already ship its own — we want to merge by child
# so the repo's contents aren't blown away wholesale. Per-child conflicts
# still favour the local version (Studio's activated plugin/theme wins).
restore_path_contents() {
  local rel="$1"
  local src="$wp_content_temp/$rel"
  local dest="$wp_content/$rel"
  if [[ ! -d "$src" ]]; then
    echo "    skip:  $rel/* (not present in wp-content-temp)"
    return 0
  fi
  mkdir -p "$dest"
  local moved_any=0
  shopt -s dotglob nullglob
  for entry in "$src"/*; do
    local name
    name="$(basename "$entry")"
    if [[ -e "$dest/$name" ]]; then
      rm -rf "$dest/$name"
    fi
    mv "$entry" "$dest/$name"
    echo "    moved: $rel/$name"
    moved_any=1
  done
  shopt -u dotglob nullglob
  if (( moved_any == 0 )); then
    echo "    skip:  $rel/* (empty in wp-content-temp)"
  fi
}

echo "==> restoring Studio runtime data from wp-content-temp"
restore_path "uploads"
restore_path "database"
restore_path "db.php"
restore_path "mu-plugins/sqlite-database-integration"
restore_path_contents "plugins"
restore_path_contents "themes"

# Patch wp-content/.gitignore so Studio-generated runtime files don't surface
# as uncommitted changes inside the cloned repo. Idempotent: skipped if the
# marker already exists. Patterns are anchored with a leading slash so they
# only match at the wp-content root (where Studio drops these); without the
# slash, gitignore treats them as recursive matches and would hide legitimate
# files like theme/plugin index.php stubs deeper in the tree.
gitignore="$wp_content/.gitignore"
gitignore_marker="# Ignore files generated by the Studio CLI"
if [[ ! -f "$gitignore" ]] || ! grep -qxF "$gitignore_marker" "$gitignore"; then
  {
    [[ -s "$gitignore" ]] && echo ""
    echo "$gitignore_marker"
    echo "/database"
    echo "/db.php"
    echo "/index.php"
    echo "/uploads"
    echo "/mu-plugins/sqlite-database-integration"
  } >> "$gitignore"
  echo "==> .gitignore patched"
fi

# Install + activate safety-net. Non-fatal: a failure here leaves the site
# usable; the user can re-run install-safety-net.sh manually.
echo
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! bash "$script_dir/install-safety-net.sh" --target-dir "$abs_site"; then
  echo "clone-into-existing-site.sh: safety-net install failed; continuing anyway" >&2
  safety_net_status="failed (re-run install-safety-net.sh manually)"
else
  safety_net_status="installed and activated"
fi

echo
echo "==> done"
echo "    site path:        $abs_site"
echo "    wp-content:       cloned from $repo_url"
echo "    wp-content-temp:  preserved (delete manually after verifying)"
echo "    safety-net:       $safety_net_status"
