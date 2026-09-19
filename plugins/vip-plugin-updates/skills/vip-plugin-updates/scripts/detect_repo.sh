#!/usr/bin/env bash
# Work out how a VIP repo wants plugin updates done, by looking at the repo
# itself: where plugins are vendored, which branch is the testing branch, which
# is production, what label plugin-update PRs carry, and what guards the
# production branch.
#
# Usage: detect_repo.sh [--repo-path DIR] [--format json|text]
#
# Nothing here is hardcoded per site. Everything is read from the working copy
# and from GitHub, so a new repo needs no configuration. Written for bash 3.2.
set -euo pipefail

REPO_PATH="$(pwd)"
FORMAT="json"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path) REPO_PATH="${2:-}"; shift 2;;
    --format) FORMAT="${2:-json}"; shift 2;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
  esac
done

command -v git >/dev/null || { echo "git not found" >&2; exit 1; }
cd "$REPO_PATH"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -n "$ROOT" ] || { echo "Not a git repository: $REPO_PATH" >&2; exit 1; }
cd "$ROOT"

REMOTE="origin"
git remote get-url "$REMOTE" >/dev/null 2>&1 || REMOTE="$(git remote | head -n1)"
REMOTE_URL="$(git remote get-url "$REMOTE" 2>/dev/null || echo "")"

NWO=""
DEFAULT_BRANCH=""
if command -v gh >/dev/null 2>&1; then
  NWO="$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null || true)"
  [ -n "$NWO" ] && DEFAULT_BRANCH="$(gh api "repos/$NWO" --jq .default_branch 2>/dev/null || true)"
fi
[ -n "$DEFAULT_BRANCH" ] || DEFAULT_BRANCH="$(git symbolic-ref --quiet --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null | sed "s|^$REMOTE/||" || true)"

# --- where plugins are vendored --------------------------------------------
PLUGINS_DIR=""
for candidate in plugins wp-content/plugins content/plugins; do
  [ -d "$ROOT/$candidate" ] || continue
  if find "$ROOT/$candidate" -mindepth 2 -maxdepth 2 -type f -name '*.php' -exec grep -lIiE '^[[:space:]]*\*?[[:space:]]*Plugin Name:' {} + 2>/dev/null | head -n1 | grep -q .; then
    PLUGINS_DIR="$candidate"
    break
  fi
done
PLUGIN_COUNT=0
[ -n "$PLUGINS_DIR" ] && PLUGIN_COUNT="$(find "$ROOT/$PLUGINS_DIR" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"

# --- branches ---------------------------------------------------------------
BRANCHES="$(git ls-remote --heads "$REMOTE" 2>/dev/null | sed 's|.*refs/heads/||' || true)"
[ -n "$BRANCHES" ] || BRANCHES="$(git for-each-ref --format='%(refname:short)' "refs/remotes/$REMOTE" | sed "s|^$REMOTE/||")"

has_branch() { printf '%s\n' "$BRANCHES" | grep -qx "$1"; }

PROD_BRANCH=""
for candidate in master main production prod live; do
  if has_branch "$candidate"; then PROD_BRANCH="$candidate"; break; fi
done
DEV_BRANCH=""
for candidate in develop staging dev development preprod testing; do
  if has_branch "$candidate" && [ "$candidate" != "$PROD_BRANCH" ]; then DEV_BRANCH="$candidate"; break; fi
done
[ -n "$PROD_BRANCH" ] || PROD_BRANCH="$DEFAULT_BRANCH"
if [ -z "$DEV_BRANCH" ] && [ -n "$DEFAULT_BRANCH" ] && [ "$DEFAULT_BRANCH" != "$PROD_BRANCH" ]; then
  DEV_BRANCH="$DEFAULT_BRANCH"
fi

# --- label to put on the PRs ------------------------------------------------
LABELS=""
LABEL=""
if [ -n "$NWO" ] && command -v gh >/dev/null 2>&1; then
  LABELS="$(gh api "repos/$NWO/labels?per_page=100" --jq '.[].name' 2>/dev/null || true)"
  for pattern in '[Pp]lugin [Uu]pdate' '[Pp]lugin-[Uu]pdate' '^[Uu]pdate$' '^[Pp]lugin$' '[Dd]ependenc'; do
    LABEL="$(printf '%s\n' "$LABELS" | grep -E "$pattern" | head -n1 || true)"
    [ -n "$LABEL" ] && break
  done
fi

# --- guards and process docs, read from the testing branch ------------------
# Read from the ref rather than the working tree: the checked-out branch may be
# production, where the docs and workflows that describe the process do not exist.
REF="$REMOTE/${DEV_BRANCH:-$DEFAULT_BRANCH}"
git rev-parse --verify --quiet "$REF" >/dev/null 2>&1 || REF="HEAD"
TREE_FILES="$(git ls-tree -r --name-only "$REF" 2>/dev/null || true)"
set +e

GUARDS=""
if [ -n "$PROD_BRANCH" ]; then
  GUARDS="$(printf '%s\n' "$TREE_FILES" | grep -E '^\.github/workflows/' | while IFS= read -r f; do
    body="$(git show "$REF:$f" 2>/dev/null)"
    # Both YAML spellings: `branches: [master]` inline, and `branches:` with
    # `- master` on its own line underneath. grep is line-oriented, so the
    # second form needs its own pattern or a real guard reads as none.
    printf '%s\n' "$body" | grep -qE '^[[:space:]]*branches:' || continue
    # Quotes and list punctuation become spaces first, so one simple word-
    # boundary match covers `[master]`, `"master"`, `master` and `- master`
    # without a bracket expression per spelling.
    flat="$(printf '%s\n' "$body" | tr -d "\"'" | tr '[],' '   ')"
    if printf '%s\n' "$flat" | grep -qE "branches:.*[[:space:]]${PROD_BRANCH}([[:space:]]|\$)" \
       || printf '%s\n' "$flat" | grep -qE "^[[:space:]]*-[[:space:]]*${PROD_BRANCH}[[:space:]]*\$"; then
      basename "$f"
    fi
  done | sort | tr '\n' ' ')" || true
fi
DOCS=""
SEEN_DOCS=""
for doc in docs/plugin-updates.md docs/branches-and-deploys.md docs/deploys.md CONTRIBUTING.md AGENTS.md CLAUDE.md readme.md README.md; do
  printf '%s\n' "$TREE_FILES" | grep -qx "$doc" || [ -f "$ROOT/$doc" ] || continue
  # Case-insensitive filesystems answer to both readme.md and README.md.
  key="$(printf '%s' "$doc" | tr 'A-Z' 'a-z')"
  case " $SEEN_DOCS " in *" $key "*) continue;; esac
  SEEN_DOCS="$SEEN_DOCS $key"
  DOCS="$DOCS $doc"
done

set -e
# Tracked changes block an update run; untracked files only matter inside a
# plugin directory, so they are counted separately rather than lumped in.
DIRTY="false"
[ -n "$(git status --porcelain --untracked-files=no)" ] && DIRTY="true"
UNTRACKED_COUNT="$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")"

esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
lines_json() {  # one item per stdin line -> JSON array (labels may contain spaces)
  local first=1 line
  printf '['
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    [ $first -eq 1 ] || printf ', '
    printf '"%s"' "$(esc "$line")"
    first=0
  done
  printf ']'
}
list_json() {  # whitespace separated -> JSON array
  local first=1 item
  printf '['
  for item in $1; do
    [ $first -eq 1 ] || printf ', '
    printf '"%s"' "$(esc "$item")"
    first=0
  done
  printf ']'
}

if [ "$FORMAT" = "text" ]; then
  cat <<TXT
Repository:       ${NWO:-unknown} ($REMOTE_URL)
Working copy:     $ROOT
Current branch:   $CURRENT_BRANCH (tracked changes: $DIRTY, untracked files: $UNTRACKED_COUNT)
Default branch:   $DEFAULT_BRANCH
Testing branch:   ${DEV_BRANCH:-<none found>}
Production branch: ${PROD_BRANCH:-<none found>}
Plugins dir:      ${PLUGINS_DIR:-<not found>} ($PLUGIN_COUNT plugins)
PR label:         ${LABEL:-<none - PRs will be unlabelled>}
Prod guards:      ${GUARDS:-<none>}
Process docs:     ${DOCS:-<none>} (read from $REF)
TXT
  exit 0
fi

cat <<JSON
{
  "repo": "$(esc "${NWO:-}")",
  "remote": "$(esc "$REMOTE")",
  "remote_url": "$(esc "$REMOTE_URL")",
  "root": "$(esc "$ROOT")",
  "current_branch": "$(esc "$CURRENT_BRANCH")",
  "dirty": $DIRTY,
  "untracked_files": $UNTRACKED_COUNT,
  "default_branch": "$(esc "$DEFAULT_BRANCH")",
  "dev_branch": "$(esc "$DEV_BRANCH")",
  "prod_branch": "$(esc "$PROD_BRANCH")",
  "plugins_dir": "$(esc "$PLUGINS_DIR")",
  "plugins_dir_abs": "$(esc "${PLUGINS_DIR:+$ROOT/$PLUGINS_DIR}")",
  "vendored_plugin_count": $PLUGIN_COUNT,
  "label": "$(esc "$LABEL")",
  "all_labels": $(printf '%s\n' "$LABELS" | lines_json),
  "prod_branch_guard_workflows": $(list_json "$GUARDS"),
  "process_docs": $(list_json "$DOCS"),
  "docs_ref": "$(esc "$REF")"
}
JSON
