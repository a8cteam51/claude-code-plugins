#!/usr/bin/env bash
#
# github-check.sh — Find and analyze a plugin's GitHub repository
#
# Usage: ./github-check.sh <plugin-slug> [work-dir]
# Creates (in work-dir):
#   github-info.json — repo metadata from GitHub API (if found)
#   github-summary.txt — human-readable summary
#
# Exit codes: 0 = repo found, 1 = error, 2 = no repo found

set -euo pipefail

SLUG="${1:-}"
WORK_DIR="${2:-/tmp/plugin-review-${SLUG}}"

if [ -z "$SLUG" ]; then
    echo "ERROR: Plugin slug is required."
    echo "Usage: $0 <plugin-slug> [work-dir]"
    exit 1
fi

# Validate slug to prevent path traversal
if [[ ! "$SLUG" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
    echo "ERROR: Invalid plugin slug '${SLUG}'. Slugs may only contain letters, numbers, hyphens, and underscores."
    exit 1
fi

SOURCE_DIR="$WORK_DIR/source"
API_DATA="$WORK_DIR/api-data.json"

# Build auth header if GITHUB_TOKEN is available
AUTH_HEADER=""
if [ -n "${GITHUB_TOKEN:-}" ]; then
    AUTH_HEADER="Authorization: token $GITHUB_TOKEN"
fi

echo "→ Searching for GitHub repository..."

# ============================================================
# Step 1: Extract GitHub URLs from plugin files and API data
# ============================================================

GITHUB_URLS=""

# Search source files for github.com URLs
if [ -d "$SOURCE_DIR" ]; then
    FILE_URLS=$(grep -roha --binary-files=without-match 'https\?://github\.com/[a-zA-Z0-9._-]*/[a-zA-Z0-9._-]*' "$SOURCE_DIR" 2>/dev/null | sort -u || true)
    if [ -n "$FILE_URLS" ]; then
        GITHUB_URLS="$FILE_URLS"
    fi
fi

# Search API data for github.com URLs (homepage, description, etc.)
if [ -f "$API_DATA" ]; then
    API_URLS=$(grep -oh 'https\?://github\.com/[a-zA-Z0-9._-]*/[a-zA-Z0-9._-]*' "$API_DATA" 2>/dev/null | sort -u || true)
    if [ -n "$API_URLS" ]; then
        if [ -n "$GITHUB_URLS" ]; then
            GITHUB_URLS="$GITHUB_URLS"$'\n'"$API_URLS"
        else
            GITHUB_URLS="$API_URLS"
        fi
    fi
fi

# Deduplicate and clean URLs (strip trailing slashes, .git suffix)
if [ -n "$GITHUB_URLS" ]; then
    GITHUB_URLS=$(echo "$GITHUB_URLS" | sed 's|\.git$||; s|/$||' | sort -u)
fi

# ============================================================
# Step 2: Pick the best candidate URL
# ============================================================

REPO_URL=""
CONFIDENCE="none"

if [ -n "$GITHUB_URLS" ]; then
    # Prefer a URL that contains the plugin slug
    SLUG_MATCH=$(echo "$GITHUB_URLS" | grep -iF "/$SLUG" | head -1 || true)
    if [ -n "$SLUG_MATCH" ]; then
        REPO_URL="$SLUG_MATCH"
        CONFIDENCE="high"
    else
        # Fall back to the first URL found
        REPO_URL=$(echo "$GITHUB_URLS" | head -1)
        CONFIDENCE="medium"
    fi
fi

if [ -z "$REPO_URL" ]; then
    echo "  No GitHub repository found in plugin files or API data."
    mkdir -p "$WORK_DIR"
    echo "NO_REPO_FOUND" > "$WORK_DIR/github-summary.txt"
    echo '{}' > "$WORK_DIR/github-info.json"
    exit 2
fi

# Extract owner/repo from URL
OWNER_REPO=$(echo "$REPO_URL" | sed -E 's|https?://github\.com/||')

echo "  Found: $REPO_URL (confidence: $CONFIDENCE)"

# ============================================================
# Step 3: Query GitHub API for repository metadata
# ============================================================

echo "→ Fetching repository info from GitHub API..."

GITHUB_API="https://api.github.com/repos/${OWNER_REPO}"

# Repo metadata (follow redirects for renamed repos)
HTTP_CODE=$(curl -s -L -o "$WORK_DIR/github-info.json" -w "%{http_code}" \
    -H "Accept: application/vnd.github.v3+json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    "$GITHUB_API" 2>/dev/null)

if [ "$HTTP_CODE" != "200" ]; then
    if [ "$HTTP_CODE" = "403" ]; then
        echo "  WARNING: GitHub API rate limit exceeded (HTTP 403)."
        if [ -z "${GITHUB_TOKEN:-}" ]; then
            echo "  Set GITHUB_TOKEN environment variable to increase rate limit."
        fi
    else
        echo "  GitHub API returned HTTP ${HTTP_CODE}. Repository may be private or deleted."
    fi
    cat > "$WORK_DIR/github-summary.txt" <<EOF
=== GitHub Repository ===

URL: ${REPO_URL}
Status: Not accessible (HTTP ${HTTP_CODE}). Repository may be private, deleted, or renamed.
Confidence: ${CONFIDENCE}
EOF
    echo '{}' > "$WORK_DIR/github-info.json"
    exit 0
fi

# Fetch open issues (just the count, first page)
OPEN_ISSUES=$(jq '.open_issues_count // 0' "$WORK_DIR/github-info.json")
STARS=$(jq '.stargazers_count // 0' "$WORK_DIR/github-info.json")
FORKS=$(jq '.forks_count // 0' "$WORK_DIR/github-info.json")
DEFAULT_BRANCH=$(jq -r '.default_branch // "main"' "$WORK_DIR/github-info.json")
PUSHED_AT=$(jq -r '.pushed_at // "Unknown"' "$WORK_DIR/github-info.json")
ARCHIVED=$(jq -r '.archived // false' "$WORK_DIR/github-info.json")
LICENSE=$(jq -r '.license.spdx_id // "Unknown"' "$WORK_DIR/github-info.json")
DESCRIPTION=$(jq -r '.description // "None"' "$WORK_DIR/github-info.json")

# Calculate days since last push
DAYS_SINCE_PUSH="Unknown"
if [ "$PUSHED_AT" != "Unknown" ]; then
    PUSH_DATE=$(echo "$PUSHED_AT" | cut -dT -f1)
    PUSH_EPOCH=$(date -j -f "%Y-%m-%d" "$PUSH_DATE" "+%s" 2>/dev/null || date -d "$PUSH_DATE" "+%s" 2>/dev/null || echo "0")
    NOW_EPOCH=$(date "+%s")
    if [ "$PUSH_EPOCH" != "0" ]; then
        DAYS_SINCE_PUSH=$(( (NOW_EPOCH - PUSH_EPOCH) / 86400 ))
    fi
fi

# Fetch recent issues with "security" or "vulnerability" in title (best effort)
SECURITY_ISSUES=""
SECURITY_ISSUE_DATA=$(curl -s -H "Accept: application/vnd.github.v3+json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    "${GITHUB_API}/issues?state=all&per_page=100&sort=created&direction=desc" 2>/dev/null || echo "[]")

if [ "$SECURITY_ISSUE_DATA" != "[]" ] && echo "$SECURITY_ISSUE_DATA" | jq empty 2>/dev/null; then
    SECURITY_ISSUES=$(echo "$SECURITY_ISSUE_DATA" | jq -r '
        [.[] | select(
            (.title | ascii_downcase | test("security|vulnerability|vuln|xss|sql.?inject|csrf|rce|exploit|cve")) or
            (.labels[]?.name | ascii_downcase | test("security|vulnerability"))
        )] |
        if length > 0 then
            map("  #\(.number) [\(.state)] \(.title) (\(.created_at | split("T")[0]))")
            | join("\n")
        else
            "  None found."
        end
    ' 2>/dev/null || echo "  Could not parse issues.")
fi

# Fetch latest release info
LATEST_RELEASE_DATA=$(curl -s -H "Accept: application/vnd.github.v3+json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    "${GITHUB_API}/releases/latest" 2>/dev/null || echo "{}")

LATEST_RELEASE="None"
if echo "$LATEST_RELEASE_DATA" | jq -e '.tag_name' &>/dev/null; then
    RELEASE_TAG=$(echo "$LATEST_RELEASE_DATA" | jq -r '.tag_name')
    RELEASE_DATE=$(echo "$LATEST_RELEASE_DATA" | jq -r '.published_at // "Unknown"' | cut -dT -f1)
    LATEST_RELEASE="${RELEASE_TAG} (${RELEASE_DATE})"
fi

# ============================================================
# Step 4: Write summary
# ============================================================

cat > "$WORK_DIR/github-summary.txt" <<EOF
=== GitHub Repository ===

URL:            ${REPO_URL}
Confidence:     ${CONFIDENCE}
Description:    ${DESCRIPTION}
Stars:          ${STARS}
Forks:          ${FORKS}
Open Issues:    ${OPEN_ISSUES}
License:        ${LICENSE}
Archived:       ${ARCHIVED}
Default Branch: ${DEFAULT_BRANCH}
Last Push:      ${PUSHED_AT} (${DAYS_SINCE_PUSH} days ago)
Latest Release: ${LATEST_RELEASE}

Security-Related Issues:
${SECURITY_ISSUES:-  None found.}
EOF

echo ""
cat "$WORK_DIR/github-summary.txt"
