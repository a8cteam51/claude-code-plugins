#!/usr/bin/env bash
# Put one plugin update on its own branch and open one pull request for it.
#
# Usage:
#   open_plugin_pr.sh --repo-path DIR --base-branch BRANCH --slug SLUG --src DIR \
#                     --new-version VER [--old-version VER] [--name "Plugin Name"] \
#                     [--plugins-dir plugins] [--branch NAME] [--label LABEL] \
#                     [--remote origin] [--body-file FILE] [--draft] [--dry-run] \
#                     [--reuse-branch] [--allow-dirty]
#
# One plugin per run, deliberately: a plugin that goes wrong does not take the
# rest of the batch with it, and rolling one back is one merge revert. Versions
# are passed in rather than parsed here, so a plugin with an unreadable header
# is a value the caller supplies, not a crash.
#
# Prints a RESULT line: `RESULT <status> <slug> <branch> <pr-url-or-->`, where
# status is one of created, skipped-branch-exists, skipped-no-changes,
# pushed-no-pr, dry-run. Exits non-zero only on a real failure. bash 3.2 safe.
set -euo pipefail

REPO_PATH=""; BASE_BRANCH=""; SLUG=""; SRC=""; NEW_VERSION=""; OLD_VERSION=""
NAME=""; PLUGINS_DIR="plugins"; BRANCH=""; LABEL=""; REMOTE="origin"; BODY_FILE=""
DRAFT=""; DRYRUN=""; REUSE=""; ALLOW_DIRTY=""

usage() { sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path) REPO_PATH="${2:-}"; shift 2;;
    --base-branch) BASE_BRANCH="${2:-}"; shift 2;;
    --slug) SLUG="${2:-}"; shift 2;;
    --src) SRC="${2:-}"; shift 2;;
    --new-version) NEW_VERSION="${2:-}"; shift 2;;
    --old-version) OLD_VERSION="${2:-}"; shift 2;;
    --name) NAME="${2:-}"; shift 2;;
    --plugins-dir) PLUGINS_DIR="${2:-}"; shift 2;;
    --branch) BRANCH="${2:-}"; shift 2;;
    --label) LABEL="${2:-}"; shift 2;;
    --remote) REMOTE="${2:-}"; shift 2;;
    --body-file) BODY_FILE="${2:-}"; shift 2;;
    --draft) DRAFT="1"; shift;;
    --dry-run) DRYRUN="1"; shift;;
    --reuse-branch) REUSE="1"; shift;;
    --allow-dirty) ALLOW_DIRTY="1"; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage >&2; exit 2;;
  esac
done

for required in REPO_PATH BASE_BRANCH SLUG SRC NEW_VERSION; do
  eval "value=\"\${$required}\""
  [ -n "$value" ] || { echo "Missing required argument for $required" >&2; usage >&2; exit 2; }
done

command -v git   >/dev/null || { echo "git not found" >&2; exit 1; }
command -v rsync >/dev/null || { echo "rsync not found" >&2; exit 1; }
[ -n "$DRYRUN" ] || command -v gh >/dev/null || { echo "gh not found (brew install gh)" >&2; exit 1; }

[ -d "$SRC" ] || { echo "Source plugin folder not found: $SRC" >&2; exit 1; }
SRC="$(cd "$SRC" && pwd)"
cd "$REPO_PATH"
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
[ -d "$ROOT/$PLUGINS_DIR" ] || { echo "No $PLUGINS_DIR directory in $ROOT" >&2; exit 1; }

NAME="${NAME:-$SLUG}"
BRANCH="${BRANCH:-update/${SLUG}-${NEW_VERSION}-${BASE_BRANCH}}"
DEST="$ROOT/$PLUGINS_DIR/$SLUG"
START_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [ -n "$DRYRUN" ]; then
  echo "DRY-RUN  ${NAME} (${SLUG}) ${OLD_VERSION:-new} -> ${NEW_VERSION}"
  echo "         branch ${BRANCH} off ${BASE_BRANCH}, copying ${SRC} -> ${PLUGINS_DIR}/${SLUG}"
  echo "RESULT dry-run $SLUG $BRANCH -"
  exit 0
fi

# Tracked modifications anywhere would ride along on the update branch. Untracked
# files elsewhere are harmless - only the plugin directory is staged - but
# untracked files inside the target plugin would be swept into the commit.
TRACKED_CHANGES="$(git status --porcelain --untracked-files=no)"
UNTRACKED_IN_DEST="$(git ls-files --others --exclude-standard -- "$PLUGINS_DIR/$SLUG")"
if [ -z "$ALLOW_DIRTY" ] && [ -n "$TRACKED_CHANGES" ]; then
  echo "Working tree has uncommitted tracked changes. Commit or stash first, or pass --allow-dirty if you know they are unrelated:" >&2
  printf '%s\n' "$TRACKED_CHANGES" | head -n 20 >&2
  exit 1
fi
if [ -z "$ALLOW_DIRTY" ] && [ -n "$UNTRACKED_IN_DEST" ]; then
  echo "Untracked files inside $PLUGINS_DIR/$SLUG would be committed by this update:" >&2
  printf '%s\n' "$UNTRACKED_IN_DEST" | head -n 20 >&2
  echo "Remove them, or pass --allow-dirty if they belong in the commit." >&2
  exit 1
fi

git fetch "$REMOTE" --prune >/dev/null 2>&1 || git fetch "$REMOTE" --prune
git rev-parse --verify --quiet "$REMOTE/$BASE_BRANCH" >/dev/null || {
  echo "Base branch $REMOTE/$BASE_BRANCH does not exist" >&2; exit 1; }

BRANCH_ON_REMOTE=""
git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1 && BRANCH_ON_REMOTE="1"

if [ -n "$BRANCH_ON_REMOTE" ] && [ -z "$REUSE" ]; then
  echo "Branch $BRANCH already exists on $REMOTE - skipping (pass --reuse-branch to push onto it)"
  echo "RESULT skipped-branch-exists $SLUG $BRANCH -"
  exit 0
fi

# Reuse means adding a commit to the branch, so start from its tip. Starting
# from the base branch would discard what is already on it and the push would
# be rejected as a non-fast-forward.
START_POINT="$REMOTE/$BASE_BRANCH"
if [ -n "$BRANCH_ON_REMOTE" ] && [ -n "$REUSE" ]; then
  if git rev-parse --verify --quiet "$REMOTE/$BRANCH" >/dev/null; then
    START_POINT="$REMOTE/$BRANCH"
    echo "Reusing $BRANCH - committing onto its existing tip, not onto $BASE_BRANCH"
  else
    echo "Branch $BRANCH is on $REMOTE but has no local ref after fetch; starting from $BASE_BRANCH" >&2
  fi
fi

restore() { git checkout --quiet "$START_BRANCH" 2>/dev/null || true; }

git checkout --quiet -B "$BRANCH" "$START_POINT"

# Replace rather than merge: the new package is the whole plugin. --delete
# removes files the new version dropped, which is the point.
rsync -a --delete \
  --exclude '.DS_Store' --exclude '__MACOSX' --exclude '._*' \
  --exclude '.git' --exclude '.svn' --exclude 'Thumbs.db' \
  "$SRC/" "$DEST/"

git add -A -- "$PLUGINS_DIR/$SLUG"
if [ -z "$(git diff --cached --name-only)" ]; then
  echo "No file changes for $SLUG against $BASE_BRANCH - nothing to commit"
  restore
  echo "RESULT skipped-no-changes $SLUG $BRANCH -"
  exit 0
fi

CHANGED="$(git diff --cached --name-only | wc -l | tr -d ' ')"
git commit --quiet -m "Update ${NAME} from ${OLD_VERSION:-new} to ${NEW_VERSION}"

if ! git push --quiet "$REMOTE" "$BRANCH"; then
  echo "Push failed for $BRANCH" >&2
  restore
  exit 1
fi

TITLE="Update ${NAME} from ${OLD_VERSION:-new} to ${NEW_VERSION}"
BODY_TMP=""
if [ -z "$BODY_FILE" ]; then
  BODY_TMP="$(mktemp)"
  {
    printf 'Updates **%s** (`%s`) %s%s on `%s`.\n\n' "$NAME" "$SLUG" \
      "${OLD_VERSION:+$OLD_VERSION -> }" "$NEW_VERSION" "$BASE_BRANCH"
    printf '### What changed\n\n- Replaced `%s/%s/` with the new release (%s file(s) changed).\n\n' \
      "$PLUGINS_DIR" "$SLUG" "$CHANGED"
    printf '### Checklist\n\n'
    printf -- '- [ ] Smoke test the site after deploy\n'
    printf -- '- [ ] Check the logs for fatals\n'
    printf -- '- [ ] Confirm the version in WP Admin > Plugins\n'
  } > "$BODY_TMP"
  BODY_FILE="$BODY_TMP"
fi

create_pr() {  # uses $TRY_LABEL; prints the last line gh emits
  set -- pr create --base "$BASE_BRANCH" --head "$BRANCH" --title "$TITLE" --body-file "$BODY_FILE"
  [ -n "$DRAFT" ] && set -- "$@" --draft
  if [ -n "$TRY_LABEL" ]; then set -- "$@" --label "$TRY_LABEL"; fi
  gh "$@" 2>&1 | tail -n1
}

TRY_LABEL="$LABEL"
PR_URL="$(create_pr || true)"
if [ -n "$LABEL" ] && ! printf '%s' "$PR_URL" | grep -q '^https://'; then
  # A missing or renamed label should not cost us the pull request.
  echo "PR creation failed with label '$LABEL' ($PR_URL) - retrying without it" >&2
  TRY_LABEL=""
  PR_URL="$(create_pr || true)"
fi

if printf '%s' "$PR_URL" | grep -q '^https://'; then
  STATUS="created"
else
  echo "gh pr create did not return a PR URL for $BRANCH: $PR_URL" >&2
  # The branch is pushed, so the PR can be opened by hand or retried without redoing the work.
  STATUS="pushed-no-pr"
  PR_URL="-"
fi

[ -n "$BODY_TMP" ] && rm -f "$BODY_TMP"
restore
echo "RESULT $STATUS $SLUG $BRANCH $PR_URL"
