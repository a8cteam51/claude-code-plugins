#!/usr/bin/env bash
# studio-repo-clone: deterministic WordPress + repo scaffold + Studio site.
# Source of truth for the workflow. The plugin's command orchestrates user
# prompts and then defers ALL filesystem mutation and Studio invocation
# here so the process is repeatable without agent improvisation.
#
# Strategy: stage the full WordPress + wp-content layout in a temp dir,
# then move into the target as the LAST filesystem step. Once files are
# in place, patch wp-content/.gitignore for Studio-generated files and
# register a Studio site at the target via `studio site create`. Studio
# uses SQLite (the only DB the CLI currently supports as of 1.8).
#
# Usage:
#   scaffold.sh --target-dir <path> --repo <owner/repo|git-url> [--site-name <name>] [--debug-log]

set -euo pipefail

WP_ZIP_URL="https://wordpress.org/latest.zip"
WP_SHA1_URL="${WP_ZIP_URL}.sha1"

usage() {
  cat <<EOF
Usage: scaffold.sh --target-dir <path> --repo <owner/repo|git-url> [--site-name <name>] [--debug-log]

  --target-dir   Path to scaffold into. Must be empty or not exist.
                 Created if it does not exist.
  --repo         GitHub shorthand (owner/repo) or full git URL. Cloned
                 into <target>/wp-content as a full wp-content replacement.
  --site-name    Studio site name. Defaults to the target dir basename.
  --debug-log    Enable WP_DEBUG_LOG on the created site via
                 'studio site set --debug-log --path <target>'.

  -h, --help     Show this help.

Requires: curl, unzip, git, studio (Studio CLI 1.8+) on PATH.
EOF
}

target_dir=""
repo=""
site_name=""
debug_log=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      [[ $# -ge 2 ]] || { echo "scaffold.sh: --target-dir needs a value" >&2; exit 2; }
      target_dir="$2"; shift 2 ;;
    --repo)
      [[ $# -ge 2 ]] || { echo "scaffold.sh: --repo needs a value" >&2; exit 2; }
      repo="$2"; shift 2 ;;
    --site-name)
      [[ $# -ge 2 ]] || { echo "scaffold.sh: --site-name needs a value" >&2; exit 2; }
      site_name="$2"; shift 2 ;;
    --debug-log) debug_log=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "scaffold.sh: unknown arg: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ -z "$target_dir" || -z "$repo" ]]; then
  echo "scaffold.sh: --target-dir and --repo are required" >&2
  usage >&2
  exit 2
fi

# Fail fast if Studio CLI is missing.
if ! command -v studio >/dev/null 2>&1; then
  echo "scaffold.sh: 'studio' CLI not found on PATH. Install WordPress Studio: https://developer.wordpress.com/studio/" >&2
  exit 1
fi

# Normalise repo. Reject shorthand that contains traversal segments.
if [[ "$repo" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  case "$repo" in
    *..*|.*|*/.*) echo "scaffold.sh: invalid repo shorthand: $repo" >&2; exit 2 ;;
  esac
  repo_url="https://github.com/${repo}.git"
else
  repo_url="$repo"
fi

# Preflight: confirm we can actually reach + auth to the repo before doing any
# of the expensive work below. Disable the credential prompter so private repos
# fail fast on missing creds instead of hanging on a TTY prompt.
echo "==> checking repo access: $repo_url"
if ! GIT_TERMINAL_PROMPT=0 git ls-remote --exit-code "$repo_url" HEAD >/dev/null 2>&1; then
  echo "scaffold.sh: cannot reach or authenticate to $repo_url" >&2
  echo "scaffold.sh: for private repos configure a git credential helper (e.g. 'gh auth login') or SSH agent and retry" >&2
  exit 1
fi

# Validate target dir.
if [[ -e "$target_dir" ]]; then
  if [[ ! -d "$target_dir" ]]; then
    echo "scaffold.sh: target exists and is not a directory: $target_dir" >&2
    exit 1
  fi
  if [[ -n "$(ls -A "$target_dir" 2>/dev/null)" ]]; then
    echo "scaffold.sh: target directory is not empty: $target_dir" >&2
    exit 1
  fi
fi

# Cleanup tracking. We delete the target on failure only if WE created it
# AND we got far enough to start mutating it.
target_existed_before=1
[[ -e "$target_dir" ]] || target_existed_before=0
mutated_target=0

work_dir="$(mktemp -d 2>/dev/null || mktemp -d -t scaffold)"

_cleanup() {
  local rc=$?
  trap - EXIT
  rm -rf "$work_dir"
  if (( rc != 0 && mutated_target == 1 )); then
    echo "scaffold.sh: failed mid-move; cleaning up partial target $abs_target" >&2
    if (( target_existed_before == 0 )); then
      rm -rf "$abs_target"
    else
      # Pre-existing empty dir: remove contents we just wrote, leave dir.
      find "$abs_target" -mindepth 1 -delete 2>/dev/null || true
    fi
  fi
  exit "$rc"
}
trap _cleanup EXIT

# Resolve target to absolute path AFTER we know it's valid; create it only
# right before the move so failures earlier don't leave an empty dir behind.
case "$target_dir" in
  /*) abs_target="$target_dir" ;;
  *)  abs_target="$PWD/$target_dir" ;;
esac

echo "==> target: $abs_target"
echo "==> repo:   $repo_url"

mkdir "$work_dir/staged"

echo "==> downloading WordPress"
curl -fsSL -o "$work_dir/wordpress.zip" "$WP_ZIP_URL"

echo "==> verifying SHA1"
curl -fsSL -o "$work_dir/wordpress.zip.sha1" "$WP_SHA1_URL"
expected_sha1="$(tr -d '[:space:]' < "$work_dir/wordpress.zip.sha1")"
if command -v shasum >/dev/null 2>&1; then
  actual_sha1="$(shasum -a 1 "$work_dir/wordpress.zip" | awk '{print $1}')"
elif command -v sha1sum >/dev/null 2>&1; then
  actual_sha1="$(sha1sum "$work_dir/wordpress.zip" | awk '{print $1}')"
else
  echo "scaffold.sh: need shasum or sha1sum to verify download" >&2
  exit 1
fi
if [[ "$expected_sha1" != "$actual_sha1" ]]; then
  echo "scaffold.sh: SHA1 mismatch (expected $expected_sha1, got $actual_sha1)" >&2
  exit 1
fi

echo "==> unzipping"
unzip -q "$work_dir/wordpress.zip" -d "$work_dir"
if [[ ! -d "$work_dir/wordpress" ]]; then
  echo "scaffold.sh: unexpected zip layout (no wordpress/ dir)" >&2
  exit 1
fi

# Build the staged layout: WP minus wp-content.
echo "==> staging WordPress (skipping default wp-content)"
shopt -s dotglob nullglob
for f in "$work_dir/wordpress/"*; do
  base="$(basename "$f")"
  [[ "$base" == "wp-content" ]] && continue
  mv "$f" "$work_dir/staged/"
done
shopt -u dotglob nullglob
rm -rf "$work_dir/wordpress"

echo "==> cloning $repo_url into staged/wp-content"
git clone "$repo_url" "$work_dir/staged/wp-content"

# Final move into target.
echo "==> moving staged tree into $abs_target"
mkdir -p "$abs_target"
mutated_target=1
shopt -s dotglob nullglob
mv "$work_dir/staged/"* "$abs_target/"
shopt -u dotglob nullglob

echo
echo "==> files in place"
echo "    target:     $abs_target"
echo "    wp-content: $abs_target/wp-content (from $repo_url)"

# Patch wp-content/.gitignore so Studio-generated files don't show up as
# uncommitted changes inside the cloned repo. Idempotent: skipped if the marker
# already exists. Creates the file if missing.
gitignore="$abs_target/wp-content/.gitignore"
gitignore_marker="# Ignore files generated by the Studio CLI"
# Patterns are anchored with a leading slash so they only match at the
# wp-content root (where Studio drops these). Without the slash, gitignore
# treats them as recursive matches and would hide legitimate files like
# theme/plugin index.php stubs deeper in the tree.
if [[ ! -f "$gitignore" ]] || ! grep -qxF "$gitignore_marker" "$gitignore"; then
  {
    [[ -s "$gitignore" ]] && echo ""
    echo "$gitignore_marker"
    echo "/database"
    echo "/db.php"
    echo "/index.php"
  } >> "$gitignore"
  echo "==> .gitignore patched"
fi

# Step 5: register and start a Studio site at the target. Studio CLI 1.8 is
# SQLite-only (no DB flag exposed); name defaults to target dir basename.
if [[ -z "$site_name" ]]; then
  site_name="$(basename "$abs_target")"
fi

echo
echo "==> creating Studio site '$site_name' at $abs_target (SQLite, default WP version)"
studio site create \
  --path "$abs_target" \
  --name "$site_name" \
  --skip-browser

# Past the destructive-rollback window: the site is registered, files are in
# place. Any post-create failure should leave them alone so the user can fix
# state with a direct 'studio site ...' invocation instead of rerunning.
mutated_target=0

if (( debug_log == 1 )); then
  echo
  echo "==> enabling WP_DEBUG_LOG"
  studio site set --debug-log --path "$abs_target"
fi

echo
echo "==> done"
echo "    site name:  $site_name"
echo "    site path:  $abs_target"
if (( debug_log == 1 )); then
  echo "    debug log:  enabled"
fi
