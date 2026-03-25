#!/usr/bin/env bash
#
# fetch-plugin.sh — Download a WordPress plugin and gather metadata
#
# Usage: ./fetch-plugin.sh <plugin-slug>
# Creates: /tmp/plugin-review-<slug>/ with:
#   source/           — extracted plugin files
#   api-data.json     — raw wp.org API response
#   support-forum.xml — RSS feed of recent support threads
#   plugin-meta.txt   — extracted key metrics summary

set -euo pipefail

SLUG="${1:-}"

if [ -z "$SLUG" ]; then
    echo "ERROR: Plugin slug is required."
    echo "Usage: $0 <plugin-slug>"
    exit 1
fi

# Strip URL down to slug if a wordpress.org URL was passed
SLUG=$(echo "$SLUG" | sed -E 's|https?://wordpress\.org/plugins/([^/]+)/?.*|\1|')

# Validate slug to prevent path traversal
if [[ ! "$SLUG" =~ ^[a-zA-Z0-9][a-zA-Z0-9_-]*$ ]]; then
    echo "ERROR: Invalid plugin slug '${SLUG}'. Slugs may only contain letters, numbers, hyphens, and underscores."
    exit 1
fi

WORK_DIR="/tmp/plugin-review-${SLUG}"
API_URL="https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&slug=${SLUG}"
SUPPORT_RSS="https://wordpress.org/support/plugin/${SLUG}/feed/"

# Clean up any previous source download
rm -rf "$WORK_DIR/source"
mkdir -p "$WORK_DIR/source"

echo "Fetching plugin info for: ${SLUG}"
echo ""

# --- Step 1: Fetch API data ---
echo "→ Querying wordpress.org API..."
HTTP_CODE=$(curl -s -o "$WORK_DIR/api-data.json" -w "%{http_code}" "$API_URL")

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: WordPress.org API returned HTTP $HTTP_CODE for slug '${SLUG}'."
    echo "The plugin may not exist or may have been removed."
    exit 1
fi

# Check if the API returned an error (wp.org returns 200 with error body for bad slugs)
if jq -e '.error' "$WORK_DIR/api-data.json" &>/dev/null; then
    ERROR_MSG=$(jq -r '.error' "$WORK_DIR/api-data.json")
    echo "ERROR: Plugin not found — ${ERROR_MSG}"
    exit 1
fi

# --- Step 2: Download and extract plugin zip ---
DOWNLOAD_URL=$(jq -r '.download_link' "$WORK_DIR/api-data.json")

if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" = "null" ]; then
    echo "ERROR: No download link found in API response."
    exit 1
fi

echo "→ Downloading plugin zip..."
curl -s -L -o "$WORK_DIR/plugin.zip" "$DOWNLOAD_URL"

if [ ! -s "$WORK_DIR/plugin.zip" ]; then
    echo "ERROR: Downloaded file is empty."
    exit 1
fi

echo "→ Extracting..."
unzip -q -o "$WORK_DIR/plugin.zip" -d "$WORK_DIR/source"
rm "$WORK_DIR/plugin.zip"

# The zip usually extracts into a subdirectory named after the slug.
# Flatten so source/ contains the plugin files directly.
if [ -d "$WORK_DIR/source/$SLUG" ]; then
    mv "$WORK_DIR/source/$SLUG"/* "$WORK_DIR/source/" 2>/dev/null || true
    mv "$WORK_DIR/source/$SLUG"/.??* "$WORK_DIR/source/" 2>/dev/null || true
    if ! rmdir "$WORK_DIR/source/$SLUG" 2>/dev/null; then
        echo "WARNING: Could not fully flatten source directory."
    fi
fi

# --- Step 3: Fetch support forum RSS ---
echo "→ Fetching support forum feed..."
curl -s -o "$WORK_DIR/support-forum.xml" "$SUPPORT_RSS" || true

# --- Step 4: Extract key metadata ---
echo "→ Extracting metadata..."

PLUGIN_NAME=$(jq -r '.name // "Unknown"' "$WORK_DIR/api-data.json")
VERSION=$(jq -r '.version // "Unknown"' "$WORK_DIR/api-data.json")
AUTHOR=$(jq -r '.author | gsub("<[^>]*>"; "")' "$WORK_DIR/api-data.json" 2>/dev/null || echo "Unknown")
ACTIVE_INSTALLS=$(jq -r '.active_installs // 0' "$WORK_DIR/api-data.json")
RATING=$(jq -r '.rating // 0' "$WORK_DIR/api-data.json")
NUM_RATINGS=$(jq -r '.num_ratings // 0' "$WORK_DIR/api-data.json")
LAST_UPDATED=$(jq -r '.last_updated // "Unknown"' "$WORK_DIR/api-data.json")
TESTED_WP=$(jq -r '.tested // "Unknown"' "$WORK_DIR/api-data.json")
REQUIRES_PHP=$(jq -r '.requires_php // "Unknown"' "$WORK_DIR/api-data.json")
REQUIRES_WP=$(jq -r '.requires // "Unknown"' "$WORK_DIR/api-data.json")
SUPPORT_THREADS=$(jq -r '.support_threads // 0' "$WORK_DIR/api-data.json")
SUPPORT_RESOLVED=$(jq -r '.support_threads_resolved // 0' "$WORK_DIR/api-data.json")

# Rating breakdown
STARS_5=$(jq -r '.ratings."5" // 0' "$WORK_DIR/api-data.json")
STARS_4=$(jq -r '.ratings."4" // 0' "$WORK_DIR/api-data.json")
STARS_3=$(jq -r '.ratings."3" // 0' "$WORK_DIR/api-data.json")
STARS_2=$(jq -r '.ratings."2" // 0' "$WORK_DIR/api-data.json")
STARS_1=$(jq -r '.ratings."1" // 0' "$WORK_DIR/api-data.json")

# Calculate days since last update
if [ "$LAST_UPDATED" != "Unknown" ]; then
    LAST_UPDATED_DATE=$(echo "$LAST_UPDATED" | cut -d' ' -f1)
    LAST_UPDATED_EPOCH=$(date -j -f "%Y-%m-%d" "$LAST_UPDATED_DATE" "+%s" 2>/dev/null || date -d "$LAST_UPDATED_DATE" "+%s" 2>/dev/null || echo "0")
    NOW_EPOCH=$(date "+%s")
    if [ "$LAST_UPDATED_EPOCH" != "0" ]; then
        DAYS_SINCE_UPDATE=$(( (NOW_EPOCH - LAST_UPDATED_EPOCH) / 86400 ))
    else
        DAYS_SINCE_UPDATE="Unknown"
    fi
else
    DAYS_SINCE_UPDATE="Unknown"
fi

# Support resolution rate
if [ "$SUPPORT_THREADS" -gt 0 ] 2>/dev/null; then
    RESOLUTION_RATE=$(( SUPPORT_RESOLVED * 100 / SUPPORT_THREADS ))
else
    RESOLUTION_RATE="N/A"
fi

# Extract recent reviews from API (sorted by date, mixed ratings)
echo "→ Extracting reviews..."
jq -r '.sections.reviews // ""' "$WORK_DIR/api-data.json" \
    | sed 's/<[^>]*>//g' \
    | sed 's/&amp;/\&/g; s/&lt;/</g; s/&gt;/>/g; s/&#038;/\&/g; s/&nbsp;/ /g; s/&#8217;/'"'"'/g; s/&#8220;/"/g; s/&#8221;/"/g' \
    | sed '/^[[:space:]]*$/d' \
    | sed 's/^[[:space:]]*//' \
    > "$WORK_DIR/reviews-recent.txt" 2>/dev/null || true

if [ ! -s "$WORK_DIR/reviews-recent.txt" ]; then
    echo "No recent reviews available." > "$WORK_DIR/reviews-recent.txt"
fi

# Fetch low-star reviews (1-star and 2-star) from wordpress.org review pages
# We extract review titles and URLs — Claude can WebFetch specific ones that look concerning
echo "→ Fetching low-star reviews..."

> "$WORK_DIR/reviews-low-star.txt"

for STAR_RATING in 1 2; do
    REVIEW_URL="https://wordpress.org/support/plugin/${SLUG}/reviews/?filter=${STAR_RATING}"
    REVIEW_HTML=$(curl -s -L "$REVIEW_URL" 2>/dev/null || true)

    if [ -n "$REVIEW_HTML" ]; then
        # Extract review titles and URLs from bbp-topic-permalink links
        REVIEWS=$(echo "$REVIEW_HTML" \
            | grep -o '<a class="bbp-topic-permalink" href="[^"]*">[^<]*' \
            | sed 's/<a class="bbp-topic-permalink" href="//; s/">/  |  /' \
            | sed 's/&amp;/\&/g; s/&#8217;/'"'"'/g; s/&#8220;/"/g; s/&#8221;/"/g; s/&#8211;/-/g; s/&#8230;/.../g; s/&#039;/'"'"'/g' \
            || true)

        if [ -n "$REVIEWS" ]; then
            echo "=== ${STAR_RATING}-Star Reviews ===" >> "$WORK_DIR/reviews-low-star.txt"
            echo "$REVIEWS" >> "$WORK_DIR/reviews-low-star.txt"
            echo "" >> "$WORK_DIR/reviews-low-star.txt"
        fi
    fi
done

if [ ! -s "$WORK_DIR/reviews-low-star.txt" ]; then
    echo "No low-star reviews found." > "$WORK_DIR/reviews-low-star.txt"
fi

# Count PHP files and lines
PHP_FILE_COUNT=$(find "$WORK_DIR/source" -name "*.php" -type f 2>/dev/null | wc -l | tr -d ' ')
PHP_LOC=$(find "$WORK_DIR/source" -name "*.php" -type f -exec cat {} + 2>/dev/null | wc -l | tr -d ' ')
TOTAL_FILE_COUNT=$(find "$WORK_DIR/source" -type f 2>/dev/null | wc -l | tr -d ' ')

# Write plugin-meta.txt
cat > "$WORK_DIR/plugin-meta.txt" <<EOF
Plugin Name:       ${PLUGIN_NAME}
Slug:              ${SLUG}
Version:           ${VERSION}
Author:            ${AUTHOR}
Active Installs:   ${ACTIVE_INSTALLS}
Rating:            ${RATING}/100 (${NUM_RATINGS} ratings)
  5 stars:         ${STARS_5}
  4 stars:         ${STARS_4}
  3 stars:         ${STARS_3}
  2 stars:         ${STARS_2}
  1 star:          ${STARS_1}
Last Updated:      ${LAST_UPDATED} (${DAYS_SINCE_UPDATE} days ago)
Tested Up To:      WordPress ${TESTED_WP}
Requires WP:       ${REQUIRES_WP}
Requires PHP:      ${REQUIRES_PHP}
Support Threads:   ${SUPPORT_THREADS} (${SUPPORT_RESOLVED} resolved, ${RESOLUTION_RATE}% resolution rate)
PHP Files:         ${PHP_FILE_COUNT}
PHP Lines of Code: ${PHP_LOC}
Total Files:       ${TOTAL_FILE_COUNT}
EOF

echo ""
echo "=== Plugin Metadata ==="
cat "$WORK_DIR/plugin-meta.txt"
echo ""
echo "Files saved to: ${WORK_DIR}/"
echo "  api-data.json      — raw API response"
echo "  source/            — plugin source files"
echo "  support-forum.xml  — support forum RSS"
echo "  plugin-meta.txt    — extracted metrics"
echo "  reviews-recent.txt — recent user reviews (from API)"
echo "  reviews-low-star.txt — 1-star and 2-star reviews"
