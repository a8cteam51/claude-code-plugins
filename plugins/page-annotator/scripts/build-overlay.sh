#!/usr/bin/env bash
# Regenerate skills/annotate/assets/overlay.min.js from overlay.js.
# Run after every edit to overlay.js — the two files must stay in sync;
# the skill injects the minified copy.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$PLUGIN_ROOT/skills/annotate/assets/overlay.js"
OUT="$PLUGIN_ROOT/skills/annotate/assets/overlay.min.js"

npx --yes esbuild "$SRC" --minify --charset=utf8 --legal-comments=none --outfile="$OUT"
node --check "$OUT"
echo "Built overlay.min.js: $(wc -c < "$OUT" | tr -d ' ') bytes (source: $(wc -c < "$SRC" | tr -d ' ') bytes)"
