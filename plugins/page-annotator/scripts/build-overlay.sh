#!/usr/bin/env bash
# Regenerate skills/annotate/assets/overlay.min.js from overlay.js.
# Run after every edit to overlay.js — the two files must stay in sync;
# the skill injects the minified copy.
#
# esbuild never minifies string contents, so a pre-pass collapses the
# insignificant whitespace inside the overlay's HTML/CSS template literal
# (the backtick string assigned to root.innerHTML) before esbuild runs.
# Template constraints (enforced by keeping the transform simple): no
# backticks or ${} interpolation inside it, and no text content spanning
# multiple lines.
set -euo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$PLUGIN_ROOT/skills/annotate/assets/overlay.js"
OUT="$PLUGIN_ROOT/skills/annotate/assets/overlay.min.js"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT
PRE="$BUILD_DIR/overlay.js"

node - "$SRC" "$PRE" <<'EOF'
const fs = require('fs');
const [src, out] = process.argv.slice(2);
const js = fs.readFileSync(src, 'utf8');

// Inside <style>, also drop spaces around punctuation — but never inside
// quoted strings (e.g. content or font names).
const minifyCss = (css) => css
  .split(/("[^"]*"|'[^']*')/)
  .map((seg, i) => i % 2 ? seg
    : seg.replace(/\s*([{};:,>])\s*/g, '$1').replace(/;}/g, '}'))
  .join('');

let found = false;
const pre = js.replace(/(root\.innerHTML = `)([^`]*)(`)/, (_, open, body, close) => {
  found = true;
  const collapsed = body.replace(/\s*\n\s*/g, ' ').trim();
  return open + collapsed.replace(/(<style>)(.*?)(<\/style>)/,
    (_, a, css, z) => a + minifyCss(css) + z) + close;
});
if (!found) throw new Error('root.innerHTML template not found — update the build transform');
fs.writeFileSync(out, pre);
EOF

npx --yes esbuild "$PRE" --minify --charset=utf8 --legal-comments=none --outfile="$OUT"
node --check "$OUT"
echo "Built overlay.min.js: $(wc -c < "$OUT" | tr -d ' ') bytes (source: $(wc -c < "$SRC" | tr -d ' ') bytes)"
