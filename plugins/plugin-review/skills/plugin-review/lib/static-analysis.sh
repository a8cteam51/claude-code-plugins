#!/usr/bin/env bash
#
# static-analysis.sh — Run PHPCS + grep-based vulnerability scanning on plugin source
#
# Usage: ./static-analysis.sh <path-to-plugin-source>
# Creates (in parent of source dir):
#   phpcs-results.json   — PHPCS output (security sniffs only)
#   grep-findings.txt    — grep pattern matches by severity
#   analysis-summary.txt — finding counts summary

set -euo pipefail

SOURCE_DIR="${1:-}"

if [ -z "$SOURCE_DIR" ] || [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: Valid source directory path is required."
    echo "Usage: $0 <path-to-plugin-source>"
    exit 1
fi

OUTPUT_DIR="$(dirname "$SOURCE_DIR")"

# Find PHPCS
PHPCS_CMD=""
if command -v phpcs &>/dev/null; then
    PHPCS_CMD="phpcs"
elif [ -f "$HOME/.composer/vendor/bin/phpcs" ]; then
    PHPCS_CMD="$HOME/.composer/vendor/bin/phpcs"
elif [ -f "$HOME/.config/composer/vendor/bin/phpcs" ]; then
    PHPCS_CMD="$HOME/.config/composer/vendor/bin/phpcs"
fi

# Check if there are any PHP files
PHP_FILES=$(find "$SOURCE_DIR" -name "*.php" -type f 2>/dev/null)
if [ -z "$PHP_FILES" ]; then
    echo "WARNING: No PHP files found in $SOURCE_DIR"
    echo '{"totals":{"errors":0,"warnings":0},"files":{}}' > "$OUTPUT_DIR/phpcs-results.json"
    echo "No PHP files to scan." > "$OUTPUT_DIR/grep-findings.txt"
    echo "No PHP files found." > "$OUTPUT_DIR/analysis-summary.txt"
    exit 0
fi

echo "Running static analysis..."
echo ""

# ============================================================
# TIER 1: PHPCS with WordPress security sniffs
# ============================================================

echo "→ Running PHPCS (WordPress security sniffs)..."

SECURITY_SNIFFS="WordPress.Security.EscapeOutput,WordPress.Security.NonceVerification,WordPress.Security.ValidatedSanitizedInput,WordPress.Security.SafeRedirect,WordPress.Security.PluginMenuSlug,WordPress.DB.PreparedSQL,WordPress.DB.PreparedSQLPlaceholders,WordPress.DB.DirectDatabaseQuery,WordPress.PHP.DiscouragedPHPFunctions,WordPress.PHP.DontExtract,WordPress.WP.AlternativeFunctions"

if [ -n "$PHPCS_CMD" ]; then
    # Build ignore pattern for third-party directories that shouldn't be scanned
    IGNORE_DIRS=""
    for dir in vendor node_modules vendor-prefixed lib/packages; do
        if [ -d "$SOURCE_DIR/$dir" ]; then
            IGNORE_DIRS="${IGNORE_DIRS:+$IGNORE_DIRS,}*/$dir/*"
        fi
    done

    IGNORE_FLAG=""
    if [ -n "$IGNORE_DIRS" ]; then
        IGNORE_FLAG="--ignore=$IGNORE_DIRS"
        echo "  Excluding third-party directories: ${IGNORE_DIRS}"
    fi

    # Run PHPCS — it exits non-zero when it finds issues, which is expected
    $PHPCS_CMD \
        --standard=WordPress \
        --sniffs="$SECURITY_SNIFFS" \
        --report=json \
        --extensions=php \
        --no-colors \
        ${IGNORE_FLAG:+"$IGNORE_FLAG"} \
        "$SOURCE_DIR" \
        > "$OUTPUT_DIR/phpcs-results.json" 2>/dev/null || true

    # Validate the output is valid JSON, fall back to empty result
    if ! jq empty "$OUTPUT_DIR/phpcs-results.json" 2>/dev/null; then
        echo '{"totals":{"errors":0,"warnings":0},"files":{}}' > "$OUTPUT_DIR/phpcs-results.json"
        echo "  PHPCS produced invalid output, skipping."
    else
        PHPCS_ERRORS=$(jq '.totals.errors // 0' "$OUTPUT_DIR/phpcs-results.json")
        PHPCS_WARNINGS=$(jq '.totals.warnings // 0' "$OUTPUT_DIR/phpcs-results.json")
        echo "  Found ${PHPCS_ERRORS} errors, ${PHPCS_WARNINGS} warnings"
    fi
else
    echo "  PHPCS not available, skipping."
    echo '{"totals":{"errors":0,"warnings":0},"files":{}}' > "$OUTPUT_DIR/phpcs-results.json"
fi

# ============================================================
# TIER 2: Grep-based vulnerability pattern scanning
# ============================================================

echo "→ Running grep-based vulnerability scan..."

FINDINGS_FILE="$OUTPUT_DIR/grep-findings.txt"
> "$FINDINGS_FILE"

# Helper: scan for a pattern and label it
# Usage: scan_pattern SEVERITY "label" 'pattern' [file_extension]
# file_extension defaults to "php"
scan_pattern() {
    local severity="$1"
    local label="$2"
    local pattern="$3"
    local ext="${4:-php}"
    local matches

    matches=$(grep -rn --include="*.${ext}" --exclude-dir=vendor --exclude-dir=node_modules --exclude-dir=vendor-prefixed -E "$pattern" "$SOURCE_DIR" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        echo "[$severity] $label" >> "$FINDINGS_FILE"
        echo "$matches" | while IFS= read -r line; do
            # Strip the source dir prefix for cleaner output
            echo "  ${line#$SOURCE_DIR/}" >> "$FINDINGS_FILE"
        done
        echo "" >> "$FINDINGS_FILE"
    fi
}

# CRITICAL — Remote code execution vectors
scan_pattern "CRITICAL" "eval() usage" '\beval\s*\('
scan_pattern "CRITICAL" "exec() usage" '\bexec\s*\('
scan_pattern "CRITICAL" "system() usage" '\bsystem\s*\('
scan_pattern "CRITICAL" "passthru() usage" '\bpassthru\s*\('
scan_pattern "CRITICAL" "shell_exec() usage" '\bshell_exec\s*\('
scan_pattern "CRITICAL" "proc_open() usage" '\bproc_open\s*\('
scan_pattern "CRITICAL" "popen() usage" '\bpopen\s*\('

# HIGH — Obfuscation, deserialization, direct superglobal access
scan_pattern "HIGH" "base64_decode() usage" '\bbase64_decode\s*\('
scan_pattern "HIGH" "unserialize() usage" '\bunserialize\s*\('
scan_pattern "HIGH" "Direct \$_GET access" '\$_GET\s*\['
scan_pattern "HIGH" "Direct \$_POST access" '\$_POST\s*\['
scan_pattern "HIGH" "Direct \$_REQUEST access" '\$_REQUEST\s*\['
scan_pattern "HIGH" "\$_SERVER with user-controlled keys" '\$_SERVER\s*\[\s*['"'"'"]*((HTTP_[A-Z_]+)|QUERY_STRING|REQUEST_URI|PHP_SELF|PATH_INFO)'
scan_pattern "MEDIUM" "Direct \$_SERVER access" '\$_SERVER\s*\['
scan_pattern "HIGH" "Direct \$_FILES access" '\$_FILES\s*\['
scan_pattern "HIGH" "preg_replace with /e modifier" 'preg_replace\s*\(.*\/[a-z]*e[a-z]*\s*,'
# MEDIUM — File operations, remote requests
scan_pattern "MEDIUM" "file_get_contents() usage" '\bfile_get_contents\s*\('
scan_pattern "MEDIUM" "file_put_contents() usage" '\bfile_put_contents\s*\('
scan_pattern "MEDIUM" "fopen() usage" '\bfopen\s*\('
scan_pattern "MEDIUM" "fwrite() usage" '\bfwrite\s*\('
scan_pattern "MEDIUM" "curl_exec() usage" '\bcurl_exec\s*\('
scan_pattern "MEDIUM" "wp_remote_get() usage" '\bwp_remote_get\s*\('
scan_pattern "MEDIUM" "wp_remote_post() usage" '\bwp_remote_post\s*\('
scan_pattern "MEDIUM" "wp_remote_request() usage" '\bwp_remote_request\s*\('
scan_pattern "MEDIUM" "update_option() with variable key" 'update_option\s*\(\s*\$'
scan_pattern "MEDIUM" "add_option() with variable key" 'add_option\s*\(\s*\$'

# LOW — Deprecated/risky functions
scan_pattern "LOW" "extract() usage" '\bextract\s*\('
scan_pattern "LOW" "assert() usage" '\bassert\s*\('
scan_pattern "LOW" "create_function() usage" '\bcreate_function\s*\('
scan_pattern "LOW" "call_user_func() usage" '\bcall_user_func\s*\('
scan_pattern "LOW" "call_user_func_array() usage" '\bcall_user_func_array\s*\('

# INFO — Database queries (not necessarily bad, but worth reviewing)
scan_pattern "INFO" "Direct \$wpdb->query() usage" '\$wpdb\s*->\s*query\s*\('
scan_pattern "INFO" "Direct \$wpdb->get_ usage" '\$wpdb\s*->\s*get_'

# ============================================================
# TIER 3: JavaScript vulnerability pattern scanning
# ============================================================

JS_FILES=$(find "$SOURCE_DIR" -name "*.js" -not -path "*/node_modules/*" -not -name "*.min.js" -type f 2>/dev/null)
if [ -n "$JS_FILES" ]; then
    echo "→ Running JavaScript vulnerability scan..."

    # HIGH — XSS vectors
    scan_pattern "HIGH" "innerHTML assignment (JS)" '\.innerHTML\s*=' "js"
    scan_pattern "HIGH" "outerHTML assignment (JS)" '\.outerHTML\s*=' "js"
    scan_pattern "HIGH" "document.write() (JS)" '\bdocument\.write\s*\(' "js"
    scan_pattern "HIGH" "document.writeln() (JS)" '\bdocument\.writeln\s*\(' "js"
    scan_pattern "HIGH" "eval() in JavaScript" '\beval\s*\(' "js"
    scan_pattern "HIGH" "Function() constructor (JS)" '\bnew\s+Function\s*\(' "js"

    # MEDIUM — jQuery XSS-prone methods
    scan_pattern "MEDIUM" "jQuery .html() with variable (JS)" '\.\s*html\s*\(\s*[^)"\x27]' "js"
    scan_pattern "MEDIUM" "jQuery .append() with variable (JS)" '\.\s*append\s*\(\s*[^)"\x27]' "js"
    scan_pattern "MEDIUM" "jQuery .prepend() with variable (JS)" '\.\s*prepend\s*\(\s*[^)"\x27]' "js"
    scan_pattern "MEDIUM" "jQuery .after() with variable (JS)" '\.\s*after\s*\(\s*[^)"\x27]' "js"
    scan_pattern "MEDIUM" "jQuery .before() with variable (JS)" '\.\s*before\s*\(\s*[^)"\x27]' "js"

    # MEDIUM — Dynamic script/resource loading
    scan_pattern "MEDIUM" "Dynamic script creation (JS)" 'createElement\s*\(\s*["\x27]script' "js"
    scan_pattern "MEDIUM" "setTimeout with string (JS)" '\bsetTimeout\s*\(\s*["\x27]' "js"
    scan_pattern "MEDIUM" "setInterval with string (JS)" '\bsetInterval\s*\(\s*["\x27]' "js"

    # LOW — Potential data exposure
    scan_pattern "LOW" "localStorage usage (JS)" '\blocalStorage\.' "js"
    scan_pattern "LOW" "postMessage usage (JS)" '\.postMessage\s*\(' "js"
else
    echo "→ No JavaScript files found, skipping JS scan."
fi

# ============================================================
# SUMMARY
# ============================================================

echo "→ Generating summary..."

# Count categories and individual matches per severity using awk
eval "$(awk '
/^\[/ { current = $0; sub(/\].*/, "", current); sub(/^\[/, "", current) }
/^\[/ { categories[current]++ }
/^  / { matches[current]++ }
END {
    for (s in categories) printf "%s_COUNT=%d\n", s, categories[s]
    for (s in matches) printf "%s_LINES=%d\n", s, matches[s]
}
' "$FINDINGS_FILE" | sed 's/^/export /')"

# Ensure all counts are valid numbers (default to 0)
: "${CRITICAL_COUNT:=0}" "${HIGH_COUNT:=0}" "${MEDIUM_COUNT:=0}" "${LOW_COUNT:=0}" "${INFO_COUNT:=0}"
: "${CRITICAL_LINES:=0}" "${HIGH_LINES:=0}" "${MEDIUM_LINES:=0}" "${LOW_LINES:=0}" "${INFO_LINES:=0}"

cat > "$OUTPUT_DIR/analysis-summary.txt" <<EOF
=== Static Analysis Summary ===

PHPCS (WordPress Security Sniffs):
  Errors:   ${PHPCS_ERRORS:-0}
  Warnings: ${PHPCS_WARNINGS:-0}

Grep Pattern Scan:
  CRITICAL: ${CRITICAL_COUNT} categories (${CRITICAL_LINES} matches)
  HIGH:     ${HIGH_COUNT} categories (${HIGH_LINES} matches)
  MEDIUM:   ${MEDIUM_COUNT} categories (${MEDIUM_LINES} matches)
  LOW:      ${LOW_COUNT} categories (${LOW_LINES} matches)
  INFO:     ${INFO_COUNT} categories (${INFO_LINES} matches)

Scanned: PHP files (PHPCS + grep), JavaScript files (grep)

See phpcs-results.json for detailed PHPCS output.
See grep-findings.txt for pattern match details.
EOF

echo ""
cat "$OUTPUT_DIR/analysis-summary.txt"
