#!/usr/bin/env bash
# canvas.sh - local tools for AI Canvas pages. Touches no site: everything here runs on this computer.
#
# A canvas is a folder holding block.html, one complete Custom HTML block:
#
#   <!-- wp:html {"align":"full"} -->
#   <style data-wp-block-html="css"> ... </style>
#   <script data-wp-block-html="js"> ... </script>
#   <div class="canvas-NAME"> ... </div>
#   <!-- /wp:html -->
#
# The same block works under either page template: ai-canvas (the site's header and footer around it)
# or ai-canvas-blank (the page alone). Both wrap it in <main> and print no title.
#
# Usage: canvas.sh <command> DIR [args]     (DIR is the canvas folder, or its block.html)
#
#   lint DIR        check block.html against the rules WordPress enforces silently
#   preview DIR     lint, then build DIR/preview: index, alone, editor, theme, and phone .html
#   serve DIR [PORT]  serve DIR/preview on http://127.0.0.1:PORT (default 4173); run it in the background
#   keep DIR        snapshot block.html into DIR/history before a round of changes
#   undo DIR        put the latest snapshot back (the version undone is kept as DIR/undone.html)
#   hash DIR        sha256 and character count of the block, ignoring trailing newlines
#   copy DIR        lint, copy block.html to the system clipboard, read it back to confirm
#   paste DIR       snapshot, then replace block.html with the clipboard (a page copied from the site)
#   record DIR --site URL --id N --status S --template T   note where the canvas lives (DIR/site.txt)
#   status DIR      what was recorded at the last publish, and whether block.html changed since
#   contrast FG BG [FG BG ...]   WCAG contrast ratio for hex color pairs (no DIR)
#
# Needs bash and the system's standard tools. serve needs python3, php, or ruby.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPEN_TAG='<!-- wp:html {"align":"full"} -->'
CLOSE_TAG='<!-- /wp:html -->'

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# resolve DIR|FILE -> sets DIR and FILE
resolve() {
  local arg="${1:-}"
  [ -n "$arg" ] || die "Name the canvas folder (try: canvas.sh help)"
  if [ -f "$arg" ]; then DIR="$(cd "$(dirname "$arg")" && pwd)"; else
    [ -d "$arg" ] || die "No such canvas folder: $arg"
    DIR="$(cd "$arg" && pwd)"
  fi
  FILE="$DIR/block.html"
}

need_block() { [ -f "$FILE" ] || die "No block.html in $DIR"; }

sha() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 | cut -d' ' -f1; else sha256sum | cut -d' ' -f1; fi; }

# The block as the site stores and compares it: no carriage returns, no trailing newlines.
stored_form() { printf %s "$(tr -d '\r' < "$1")"; }

block_sha() { stored_form "$1" | sha; }

# Characters, not bytes: drop UTF-8 continuation bytes and count what is left.
block_chars() { stored_form "$1" | LC_ALL=C tr -d '\200-\277' | wc -c | tr -d ' '; }

# --- lint -------------------------------------------------------------------

lint_messages() {
  LC_ALL=C awk -v open_tag="$OPEN_TAG" -v close_tag="$CLOSE_TAG" '
    function err(n, m) { printf "error: line %d: %s\n", n, m }
    function warn(n, m) { printf "warning: line %d: %s\n", n, m }
    {
      line = $0; low = tolower(line)
      if (index(line, "\r")) err(NR, "Windows line ending; save the file with Unix line endings")
      if (NR == 1 && line != open_tag) err(1, "the first line must be exactly " open_tag)
      if (line != "") { last = line; lastn = NR }
      if (line ~ /<!-- wp:/) opens++
      if (line ~ /<!-- \/wp:/) closes++

      if (mode == "") {
        if (line == "<style data-wp-block-html=\"css\">") { mode = "style"; styles++; next }
        if (line == "<script data-wp-block-html=\"js\">") { mode = "script"; scripts++; next }
        if (low ~ /<style/) err(NR, "the style tag goes on its own line, exactly <style data-wp-block-html=\"css\">, once")
        if (low ~ /<script/) err(NR, "the script tag goes on its own line, exactly <script data-wp-block-html=\"js\">, once, with no src")
        if (low ~ /<!doctype|<html[ >]|<head[ >]|<body[ >]|<meta[ >\/]|<link[ >\/]|<base[ >\/]/) err(NR, "document-level tag; the block is a fragment and the theme supplies the document")
        if (low ~ /<main[ >]/) err(NR, "<main> in the block; both AI Canvas templates already wrap the block in <main>")
        h1 += gsub(/<h1[ >]/, "&", low)
        if (low ~ /(src|href)="data:/) warn(NR, "data: URI; put images in the Media Library")
        next
      }

      if (line == "</" mode ">") { mode = ""; next }
      if (index(line, "<")) err(NR, "a < inside the " mode "; WordPress then rewrites every & that follows and breaks the " mode ". Flip the comparison (b > a) or restructure")
      if (mode == "style") {
        if (low ~ /@import/) err(NR, "@import; the block takes no external references")
        if (low ~ /url\(["\047]?data:/) warn(NR, "data: URI; put images in the Media Library")
        if (line ~ /^[^ \t@}\/]/ && line ~ /[{,]$/ && line !~ /^\.canvas-/ && line !~ /^\.editor-styles-wrapper \.canvas-/) warn(NR, "selector not prefixed with the root class: " line)
      }
    }
    END {
      if (NR == 0) { err(1, "block.html is empty"); exit }
      if (last != close_tag) err(lastn, "the last line must be exactly " close_tag)
      if (opens != 1 || closes != 1) err(1, "one wp:html block only; found " opens + 0 " opening and " closes + 0 " closing block comments")
      if (styles != 1) err(1, "exactly one style block; found " styles + 0)
      if (scripts > 1) err(1, "at most one script block; found " scripts)
      if (mode != "") err(NR, "the " mode " block is never closed")
      if (h1 != 1) err(1, "exactly one <h1>, since the AI Canvas templates print no page title; found " h1 + 0)
    }
  ' "$1"

  # Images, whatever lines their tags span.
  tr '\n' ' ' < "$1" | grep -o '<img[^>]*>' | while IFS= read -r tag; do
    short="$(printf '%s' "$tag" | cut -c1-90)"
    case "$tag" in *' alt='*) ;; *) printf 'error: image without alt (use alt="" only for decoration): %s\n' "$short";; esac
    case "$tag" in *' width='*) ;; *) printf 'warning: image without width and height: %s\n' "$short";; esac
  done || true
}

# run_lint FILE -> prints messages and a summary; returns 1 when there are errors
run_lint() {
  local messages errors warnings
  messages="$(lint_messages "$1")"
  errors="$(printf '%s\n' "$messages" | grep -c '^error:' || true)"
  warnings="$(printf '%s\n' "$messages" | grep -c '^warning:' || true)"
  [ -n "$messages" ] && printf '%s\n' "$messages"
  printf 'lint: %s errors, %s warnings\n' "$errors" "$warnings"
  [ "$errors" -eq 0 ]
}

cmd_lint() { resolve "${1:-}"; need_block; run_lint "$FILE"; }

# --- preview ----------------------------------------------------------------

# A stylesheet no design would choose, to show which theme styles the block lets through.
theme_css() {
  cat <<'CSS'
body { margin: 0; color: #ff00aa; font-family: "Courier New", monospace; font-size: 22px; font-style: oblique 23deg; letter-spacing: 0.37em; line-height: 3; text-transform: capitalize; }
h1, h2, h3, h4, h5, h6 { margin: 3em 0; color: #ff00aa; font-family: "Courier New", monospace; font-style: oblique 23deg; font-weight: 100; letter-spacing: 0.37em; line-height: 3; text-transform: capitalize; }
a { color: #ff00aa; text-decoration: line-through; }
button, input, select, textarea { padding: 2em; border: 7px dashed #ff00aa; border-radius: 33px; background: #ff00aa; box-shadow: 0 0 0 9px #ff00aa; color: #ff00aa; font-family: "Courier New", monospace; font-style: oblique 23deg; letter-spacing: 0.37em; text-transform: capitalize; }
blockquote, cite, figcaption { color: #ff00aa; font-style: oblique 23deg; }
CSS
}

# page OUT TITLE BODY_ATTRS CSS_FILE BLOCK_FILE HTML_ATTRS
# The block sits inside <main>, as both templates place it. FRAMED=yes adds a stand-in site header and
# footer (the ai-canvas template); FRAMED=no leaves the page alone (ai-canvas-blank).
page() {
  {
    printf '<!DOCTYPE html>\n<html lang="en"%s>\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>%s</title>\n' "$6" "$2"
    printf '<script>window.__aiCanvasErrors = []; addEventListener("error", function (e) { window.__aiCanvasErrors.push(e.message); });</script>\n'
    printf '<style>\n'; cat "$4"
    printf '.ai-canvas-frame { margin: 0; padding: 18px 24px; background: #e7e7e7; color: #555; font: 14px/1.4 system-ui, sans-serif; letter-spacing: 0; text-transform: none; font-style: normal; }\n</style>\n</head>\n<body%s>\n' "$3"
    [ "$FRAMED" = yes ] && printf '<header class="ai-canvas-frame">Your site header appears here</header>\n'
    printf '<main>\n'; cat "$5"; printf '</main>\n'
    [ "$FRAMED" = yes ] && printf '<footer class="ai-canvas-frame">Your site footer appears here</footer>\n'
    printf '<script src="report.js"></script>\n</body>\n</html>\n'
  } > "$1"
}

cmd_preview() {
  resolve "${1:-}"; need_block
  local out="$DIR/preview" tmp name ok=0
  run_lint "$FILE" || ok=1
  mkdir -p "$out"
  tmp="$(mktemp -d)"
  name="$(basename "$DIR")"
  printf 'body { margin: 0; }\n' > "$tmp/plain.css"
  theme_css > "$tmp/theme.css"
  # What wp-admin shows: the same block with its script never run.
  awk '$0 == "<script data-wp-block-html=\"js\">" { skip = 1 } !skip { print } skip && $0 == "</script>" { skip = 0 }' "$FILE" > "$tmp/noscript.html"

  FRAMED=yes
  page "$out/index.html" "$name" "" "$tmp/plain.css" "$FILE" ""
  page "$out/editor.html" "$name (as wp-admin shows it)" ' class="editor-styles-wrapper"' "$tmp/plain.css" "$tmp/noscript.html" ""
  page "$out/theme.html" "$name (hostile theme)" "" "$tmp/theme.css" "$FILE" ' data-ai-canvas-theme'
  FRAMED=no
  page "$out/alone.html" "$name (no site header or footer)" "" "$tmp/plain.css" "$FILE" ""
  cat > "$out/phone.html" <<HTML
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>$name (phone width)</title>
<style>body { margin: 0; background: #777; } iframe { display: block; width: 390px; height: 844px; margin: 0; border: 0; background: #fff; }</style>
</head>
<body>
<iframe id="ai-canvas-phone" src="index.html" title="Phone-width preview"></iframe>
<script src="report.js"></script>
</body>
</html>
HTML
  cp "$ROOT/report.js" "$out/report.js"
  rm -rf "$tmp"
  printf 'preview: %s/{index,alone,editor,theme,phone}.html\n' "$out"
  return "$ok"
}

cmd_serve() {
  resolve "${1:-}"
  local port="${2:-4173}"
  [ -f "$DIR/preview/index.html" ] || die "No preview yet; run: canvas.sh preview $DIR"
  cd "$DIR/preview"
  printf 'Serving %s/preview at http://127.0.0.1:%s/ (index.html, alone.html, editor.html, theme.html, phone.html)\n' "$DIR" "$port"
  if command -v python3 >/dev/null 2>&1; then exec python3 -m http.server "$port" --bind 127.0.0.1
  elif command -v php >/dev/null 2>&1; then exec php -S "127.0.0.1:$port"
  elif command -v ruby >/dev/null 2>&1; then exec ruby -run -e httpd . -b 127.0.0.1 -p "$port"
  else die "No local web server found (python3, php, or ruby). The user can still open $DIR/preview/index.html directly."
  fi
}

# --- history ----------------------------------------------------------------

cmd_keep() {
  resolve "${1:-}"; need_block
  local stamp target n=1
  mkdir -p "$DIR/history"
  stamp="$(date +%Y%m%d-%H%M%S)"
  target="$DIR/history/$stamp.html"
  while [ -e "$target" ]; do n=$((n + 1)); target="$DIR/history/$stamp-$n.html"; done
  cp "$FILE" "$target"
  printf 'kept: history/%s\n' "$(basename "$target")"
}

cmd_undo() {
  resolve "${1:-}"; need_block
  local latest
  latest="$(ls "$DIR/history"/*.html 2>/dev/null | sort | tail -n 1 || true)"
  [ -n "$latest" ] || die "Nothing to undo: $DIR/history is empty"
  cp "$FILE" "$DIR/undone.html"
  mv "$latest" "$FILE"
  printf 'restored: history/%s (the version undone is in undone.html)\n' "$(basename "$latest")"
}

# --- clipboard --------------------------------------------------------------

win_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; elif command -v wslpath >/dev/null 2>&1; then wslpath -w "$1"; else printf '%s' "$1"; fi; }

clip_write() {
  if command -v pbcopy >/dev/null 2>&1; then pbcopy < "$1"
  elif command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "Set-Clipboard -Value ([IO.File]::ReadAllText('$(win_path "$1")', [Text.Encoding]::UTF8))"
  elif command -v wl-copy >/dev/null 2>&1; then wl-copy < "$1"
  elif command -v xclip >/dev/null 2>&1; then xclip -selection clipboard < "$1"
  elif command -v xsel >/dev/null 2>&1; then xsel --clipboard --input < "$1"
  else die "No clipboard tool found (pbcopy, powershell.exe, wl-copy, xclip, or xsel)"
  fi
}

clip_read() {
  if command -v pbpaste >/dev/null 2>&1; then pbpaste
  elif command -v powershell.exe >/dev/null 2>&1; then
    powershell.exe -NoProfile -Command "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-Clipboard -Raw"
  elif command -v wl-paste >/dev/null 2>&1; then wl-paste --no-newline
  elif command -v xclip >/dev/null 2>&1; then xclip -selection clipboard -o
  elif command -v xsel >/dev/null 2>&1; then xsel --clipboard --output
  else die "No clipboard tool found (pbpaste, powershell.exe, wl-paste, xclip, or xsel)"
  fi
}

cmd_hash() {
  resolve "${1:-}"; need_block
  printf 'sha256: %s\nchars: %s\n' "$(block_sha "$FILE")" "$(block_chars "$FILE")"
}

cmd_copy() {
  resolve "${1:-}"; need_block
  run_lint "$FILE" >/dev/null || { run_lint "$FILE" || true; die "Fix the lint errors before copying"; }
  local want got tmp
  clip_write "$FILE"
  want="$(block_sha "$FILE")"
  tmp="$(mktemp)"
  clip_read > "$tmp" 2>/dev/null || true
  got="$(block_sha "$tmp")"; rm -f "$tmp"
  if [ "$want" = "$got" ]; then echo "clipboard: confirmed"; else echo "clipboard: not confirmed (could not read it back identically; the hash check in the browser decides)"; fi
  printf 'sha256: %s\nchars: %s\n' "$want" "$(block_chars "$FILE")"
}

cmd_paste() {
  resolve "${1:-}"
  local tmp first last
  tmp="$(mktemp)"
  clip_read | tr -d '\r' > "$tmp" || true
  first="$(head -n 1 "$tmp")"
  last="$(awk 'NF { l = $0 } END { print l }' "$tmp")"
  case "$first" in '<!-- wp:html'*) ;; *) rm -f "$tmp"; die "The clipboard does not hold a wp:html block (it starts: $(printf '%s' "$first" | cut -c1-60))";; esac
  [ "$last" = "$CLOSE_TAG" ] || { rm -f "$tmp"; die "The clipboard does not end with $CLOSE_TAG; the page may hold more than one block"; }
  [ -f "$FILE" ] && cmd_keep "$DIR"
  { stored_form "$tmp"; printf '\n'; } > "$FILE"
  rm -f "$tmp"
  printf 'pasted: block.html\nsha256: %s\nchars: %s\n' "$(block_sha "$FILE")" "$(block_chars "$FILE")"
}

# --- site record ------------------------------------------------------------

cmd_record() {
  resolve "${1:-}"; need_block; shift
  local site="" id="" status="" template=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --site) site="${2:-}"; shift 2;;
      --id) id="${2:-}"; shift 2;;
      --status) status="${2:-}"; shift 2;;
      --template) template="${2:-}"; shift 2;;
      *) die "Unknown option: $1";;
    esac
  done
  [ -n "$site" ] && [ -n "$id" ] && [ -n "$status" ] && [ -n "$template" ] || die "usage: record DIR --site URL --id N --status draft|publish --template ai-canvas|ai-canvas-blank"
  case "$template" in ai-canvas|ai-canvas-blank) ;; *) die "--template must be ai-canvas or ai-canvas-blank";; esac
  case "$id" in *[!0-9]*) die "--id must be the page's number";; esac
  site="${site%/}"
  printf 'site=%s\nid=%s\nstatus=%s\ntemplate=%s\nsha256=%s\nrecorded=%s\n' "$site" "$id" "$status" "$template" "$(block_sha "$FILE")" "$(date +%Y-%m-%d)" > "$DIR/site.txt"
  printf 'recorded: %s page %s (%s, %s)\npreview: %s/?page_id=%s&preview=true\nedit: %s/wp-admin/post.php?post=%s&action=edit\n' "$site" "$id" "$status" "$template" "$site" "$id" "$site" "$id"
}

field() { sed -n "s/^$1=//p" "$DIR/site.txt" | head -n 1; }

cmd_status() {
  resolve "${1:-}"; need_block
  local now; now="$(block_sha "$FILE")"
  printf 'local sha256: %s\n' "$now"
  if [ ! -f "$DIR/site.txt" ]; then echo "site: not on a site yet"; return 0; fi
  printf 'site: %s\nid: %s\nstatus: %s\ntemplate: %s\nrecorded: %s\nrecorded sha256: %s\n' "$(field site)" "$(field id)" "$(field status)" "$(field template)" "$(field recorded)" "$(field sha256)"
  if [ "$now" = "$(field sha256)" ]; then echo "local: same as the last publish"; else echo "local: changed since the last publish"; fi
}

# --- contrast ---------------------------------------------------------------

cmd_contrast() {
  [ $# -ge 2 ] && [ $(( $# % 2 )) -eq 0 ] || die "usage: contrast FG BG [FG BG ...] (hex colors: #rgb or #rrggbb)"
  local c
  for c in "$@"; do
    case "${c#\#}" in *[!0-9a-fA-F]*|"") die "Not a hex color: $c (use #rgb or #rrggbb; flatten transparent colors onto their background first)";; esac
    case "${#c}${c}" in 4\#*|7\#*|3[!#]*|6[!#]*) ;; *) die "Not a hex color: $c (use #rgb or #rrggbb; flatten transparent colors onto their background first)";; esac
  done
  printf '%s\n' "$@" | awk '
    function hex(h,  i, n) { h = tolower(h); n = 0; for (i = 1; i <= length(h); i++) n = n * 16 + index("0123456789abcdef", substr(h, i, 1)) - 1; return n }
    function lin(v) { v /= 255; return (v <= 0.04045) ? v / 12.92 : exp(2.4 * log((v + 0.055) / 1.055)) }
    function lum(c) {
      sub(/^#/, "", c)
      if (length(c) == 3) c = substr(c,1,1) substr(c,1,1) substr(c,2,1) substr(c,2,1) substr(c,3,1) substr(c,3,1)
      return 0.2126 * lin(hex(substr(c,1,2))) + 0.7152 * lin(hex(substr(c,3,2))) + 0.0722 * lin(hex(substr(c,5,2)))
    }
    function verdict(ok) { return ok ? "pass" : "FAIL" }
    NR % 2 == 1 { fg = $0; next }
    {
      a = lum(fg); b = lum($0); if (b > a) { t = a; a = b; b = t }
      # Truncate, never round up: 4.499 must not read as 4.5.
      r = int((a + 0.05) / (b + 0.05) * 100) / 100
      printf "%s on %s: %.2f:1  text %s (4.5)  large-text/ui %s (3)  aaa-text %s (7)\n", fg, $0, r, verdict(r >= 4.5), verdict(r >= 3), verdict(r >= 7)
    }'
}

# --- dispatch ---------------------------------------------------------------

cmd="${1:-}"; shift || true
case "$cmd" in
  lint) cmd_lint "$@";;
  preview) cmd_preview "$@";;
  serve) cmd_serve "$@";;
  keep) cmd_keep "$@";;
  undo) cmd_undo "$@";;
  hash) cmd_hash "$@";;
  copy) cmd_copy "$@";;
  paste) cmd_paste "$@";;
  record) cmd_record "$@";;
  status) cmd_status "$@";;
  contrast) cmd_contrast "$@";;
  -h|--help|help|"") awk 'NR == 1 { next } /^#/ { sub(/^# ?/, ""); print; next } { exit }' "$0";;
  *) die "Unknown command: $cmd (try: canvas.sh help)";;
esac
