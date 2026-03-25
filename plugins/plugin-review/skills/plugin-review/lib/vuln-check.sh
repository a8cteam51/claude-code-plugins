#!/usr/bin/env bash
#
# vuln-check.sh — Check NVD + WPScan databases for known plugin vulnerabilities
#
# Usage: ./vuln-check.sh <plugin-slug> [work-dir]
# Creates (in work-dir, defaults to /tmp/plugin-review-<slug>/):
#   cve-results.json   — raw NVD API response
#   wpscan-results.json — raw WPScan API response (if API key is set)
#   cve-summary.txt    — human-readable summary (combined)
#
# Environment:
#   WPSCAN_API_TOKEN — WPScan API key (optional, enables WPScan database)
#                      Get a free key at https://wpscan.com/register

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

mkdir -p "$WORK_DIR"

# ─── WPScan Database ───────────────────────────────────────────────────────────

WPSCAN_API_TOKEN="${WPSCAN_API_TOKEN:-}"
WPSCAN_FOUND=0
WPSCAN_SKIPPED_REASON=""

if [ -n "$WPSCAN_API_TOKEN" ]; then
    echo "→ Checking WPScan for known vulnerabilities: ${SLUG}..."

    WPSCAN_HTTP=$(curl -s -o "$WORK_DIR/wpscan-results.json" -w "%{http_code}" \
        --max-time 15 \
        -H "Authorization: Token token=${WPSCAN_API_TOKEN}" \
        "https://wpscan.com/api/v3/plugins/${SLUG}")

    if [ "$WPSCAN_HTTP" = "200" ]; then
        # Count vulnerabilities
        WPSCAN_FOUND=$(jq "[.\"${SLUG}\".vulnerabilities[]?] | length" "$WORK_DIR/wpscan-results.json" 2>/dev/null || echo 0)
        if [ "$WPSCAN_FOUND" -gt 0 ]; then
            echo "  Found ${WPSCAN_FOUND} vulnerability/ies in WPScan database."
        else
            echo "  No known vulnerabilities in WPScan database."
        fi
    elif [ "$WPSCAN_HTTP" = "403" ] || [ "$WPSCAN_HTTP" = "401" ]; then
        echo "  WARNING: WPScan API returned HTTP ${WPSCAN_HTTP} (invalid or expired API key)."
        WPSCAN_SKIPPED_REASON="invalid API key (HTTP ${WPSCAN_HTTP})"
        WPSCAN_FOUND=0
    elif [ "$WPSCAN_HTTP" = "429" ]; then
        echo "  WARNING: WPScan API rate limit reached (25/day on free tier)."
        WPSCAN_SKIPPED_REASON="rate limit reached"
        WPSCAN_FOUND=0
    elif [ "$WPSCAN_HTTP" = "404" ]; then
        echo "  Plugin not found in WPScan database."
        WPSCAN_FOUND=0
    else
        echo "  WARNING: WPScan API returned HTTP ${WPSCAN_HTTP}. Skipping."
        WPSCAN_SKIPPED_REASON="HTTP ${WPSCAN_HTTP}"
        WPSCAN_FOUND=0
    fi
else
    echo "→ WPScan: skipped (no API key)"
    echo "  Tip: Get a free key at https://wpscan.com/register (25 lookups/day)"
    echo "  Then: export WPSCAN_API_TOKEN=\"your-key-here\""
    WPSCAN_SKIPPED_REASON="no API key configured"
fi

# ─── NVD Database ──────────────────────────────────────────────────────────────

NVD_API="https://services.nvd.nist.gov/rest/json/cves/2.0"
SEARCH_TERM="wordpress ${SLUG}"
ENCODED_SEARCH=$(printf '%s' "$SEARCH_TERM" | jq -sRr @uri)

echo "→ Checking NVD for known vulnerabilities: ${SLUG}..."

# Query NVD API
HTTP_CODE=$(curl -s -o "$WORK_DIR/cve-results.json" -w "%{http_code}" \
    --max-time 20 \
    "${NVD_API}?keywordSearch=${ENCODED_SEARCH}&resultsPerPage=50")

if [ "$HTTP_CODE" = "403" ]; then
    echo "  NVD API rate limited. Retrying in 10 seconds..."
    sleep 10
    HTTP_CODE=$(curl -s -o "$WORK_DIR/cve-results.json" -w "%{http_code}" \
        --max-time 20 \
        "${NVD_API}?keywordSearch=${ENCODED_SEARCH}&resultsPerPage=50")
fi

NVD_TOTAL=0
if [ "$HTTP_CODE" = "200" ]; then
    NVD_TOTAL=$(jq '.totalResults // 0' "$WORK_DIR/cve-results.json")
    if [ "$NVD_TOTAL" -gt 0 ]; then
        echo "  Found ${NVD_TOTAL} potential CVE(s) in NVD."
    else
        echo "  No known CVEs found in NVD."
    fi
else
    echo "  WARNING: NVD API returned HTTP ${HTTP_CODE}. Skipping NVD check."
    echo '{"totalResults":0,"vulnerabilities":[]}' > "$WORK_DIR/cve-results.json"
fi

# ─── Build Combined Summary ────────────────────────────────────────────────────

{
    echo "=== Vulnerability Check ==="
    echo ""
    echo "Sources checked:"
    if [ -n "$WPSCAN_SKIPPED_REASON" ]; then
        echo "  - WPScan: SKIPPED ($WPSCAN_SKIPPED_REASON)"
    elif [ -n "$WPSCAN_API_TOKEN" ]; then
        echo "  - WPScan: ${WPSCAN_FOUND} vulnerability/ies found"
    fi
    if [ "$HTTP_CODE" = "200" ]; then
        echo "  - NVD: ${NVD_TOTAL} CVE(s) found"
    else
        echo "  - NVD: SKIPPED (API unavailable)"
    fi
    echo ""

    # WPScan results
    if [ "$WPSCAN_FOUND" -gt 0 ]; then
        echo "--- WPScan Vulnerabilities ---"
        echo ""
        jq -r "
            .\"${SLUG}\".vulnerabilities[]? |
            \"  \(.title // \"Unknown\")\n\" +
            \"    ID: \(.id // \"N/A\")\n\" +
            \"    Type: \(.vuln_type // \"N/A\")\n\" +
            \"    Fixed in: \(.fixed_in // \"NOT PATCHED\")\n\" +
            \"    Published: \(.published_date // .created_at // \"N/A\" | split(\"T\")[0])\n\" +
            \"    CVE: \(if .references.cve then (.references.cve | join(\", \")) else \"N/A\" end)\n\" +
            \"    References: \(if .references.url then (.references.url | join(\", \") | .[0:400]) else \"N/A\" end)\n\"
        " "$WORK_DIR/wpscan-results.json" 2>/dev/null || true
        echo ""
    fi

    # NVD results
    if [ "$NVD_TOTAL" -gt 0 ]; then
        echo "--- NVD CVEs ---"
        echo ""
        echo "NOTE: NVD keyword search may return CVEs that mention the plugin but"
        echo "are not direct vulnerabilities in it. Review each CVE for relevance."
        echo ""
        jq -r '
            .vulnerabilities[]? |
            {
                id: .cve.id,
                published: (.cve.published // "Unknown" | split("T")[0]),
                description: (
                    [.cve.descriptions[]? | select(.lang == "en") | .value] | first // "No description"
                ),
                cvss31: (
                    [.cve.metrics.cvssMetricV31[]? | .cvssData.baseScore] | first // null
                ),
                cvss31_severity: (
                    [.cve.metrics.cvssMetricV31[]? | .cvssData.baseSeverity] | first // null
                ),
                cvss2: (
                    [.cve.metrics.cvssMetricV2[]? | .cvssData.baseScore] | first // null
                ),
                references: [.cve.references[]? | .url] | join(", ")
            } |
            "  \(.id) (\(.published))\n" +
            "    CVSS: \(if .cvss31 then "\(.cvss31) (\(.cvss31_severity))" elif .cvss2 then "\(.cvss2) (v2)" else "N/A" end)\n" +
            "    \(.description | .[0:400])\n" +
            "    Refs: \(.references | .[0:400])"
        ' "$WORK_DIR/cve-results.json" 2>/dev/null || true
        echo ""
    fi

    # Summary when nothing found anywhere
    if [ "$WPSCAN_FOUND" -eq 0 ] && [ "$NVD_TOTAL" -eq 0 ]; then
        echo "No known vulnerabilities found for \"${SLUG}\"."
        echo ""
        echo "This is a positive signal, but does not guarantee the plugin is vulnerability-free."
        if [ -n "$WPSCAN_SKIPPED_REASON" ]; then
            echo ""
            echo "NOTE: WPScan was not checked ($WPSCAN_SKIPPED_REASON)."
            echo "WPScan has better WordPress-specific coverage than NVD alone."
            echo "Set WPSCAN_API_TOKEN for more comprehensive vulnerability detection."
        fi
    fi
} > "$WORK_DIR/cve-summary.txt"

echo ""
cat "$WORK_DIR/cve-summary.txt"
