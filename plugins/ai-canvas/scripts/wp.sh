#!/usr/bin/env bash
# Minimal WordPress REST client for the ai-canvas plugin. Needs only bash and curl.
#
# Credentials: one file per site in ~/.claude/ai-canvas/sites/<host> (mode 600),
# read by curl with -K so the Application Password never appears on a command line
# after add-site:
#
#   # site https://example.com
#   # login editor
#   user = "editor:xxxx xxxx xxxx xxxx"
#
# Content is sent as multipart form fields (curl -F), so no JSON encoding is needed.
# Undo uses WordPress revisions: `revisions` lists them, `restore` sends one back.
#
# Usage: wp.sh <command> [args]
#   sites                                   list saved sites
#   add-site URL USERNAME 'APP PASSWORD'    save credentials for a site
#   remove-site SITE
#   me SITE                                 verify credentials and capabilities
#   find SITE [--type page|post] [--search TERM] [--limit N]
#   get SITE ID [--type page|post] [--out FILE]   fetch the block content
#   create SITE --title T --content-file F [--type page|post] [--status publish|draft|private] [--slug S] [--template T] [--parent ID]
#   update SITE ID [--content-file F] [--title T] [--status S] [--slug S] [--template T] [--parent ID] [--type page|post]
#   revisions SITE ID [--type page|post]    list WordPress revisions (newest first)
#   restore SITE ID --revision RID [--type page|post]   put a revision's content back
#   trash SITE ID [--type page|post]
#   media SITE [--search TERM] [--limit N]  list images in the Media Library
#   upload SITE FILE [--title T] [--alt A]  upload an image
#   check SITE ID [--type page|post]        fetch the public URL and report render facts
#   templates SITE                          list the active theme's templates (slug, source, title)
#   template-get SITE SLUG [--out FILE]     print a template's block markup
#   template-ensure SITE                    create ai-canvas-framed and ai-canvas-blank if missing,
#                                           copying header/footer parts from the theme's page template
#   template-delete SITE SLUG               delete a custom template
#   contrast FG BG [FG BG ...]              WCAG contrast ratio for hex color pairs (no site needed)
#
# SITE is a saved host, or any unique part of a saved host or URL.

set -euo pipefail

CONFIG_DIR="${HOME}/.claude/ai-canvas"
SITES_DIR="${CONFIG_DIR}/sites"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# --- sites ------------------------------------------------------------------

site_url()   { sed -n 's/^# site //p' "$1" | head -n 1; }
site_login() { sed -n 's/^# login //p' "$1" | head -n 1; }

resolve_site() {
  # sets SITE_FILE, SITE_URL, SITE_HOST
  local name="$1" match="" f host
  [ -d "$SITES_DIR" ] || die "No sites are set up yet. Run the setup skill first."
  name="${name%/}"
  case "$name" in *://*) name="${name#*://}"; name="${name%%/*}";; esac
  for f in "$SITES_DIR"/*; do
    [ -f "$f" ] || continue
    host="$(basename "$f")"
    if [ "$host" = "$name" ]; then match="$f"; break; fi
    case "$host" in *"$name"*) if [ -n "$match" ]; then die "Ambiguous site '$1'; use the full host (see: wp.sh sites)"; fi; match="$f";; esac
  done
  [ -n "$match" ] || die "No site matches '$1'. Known sites: $(ls "$SITES_DIR" 2>/dev/null | tr '\n' ' ')"
  SITE_FILE="$match"
  SITE_HOST="$(basename "$match")"
  SITE_URL="$(site_url "$match")"
  [ -n "$SITE_URL" ] || die "Site file $match has no '# site' line"
}

cmd_sites() {
  [ -d "$SITES_DIR" ] && ls "$SITES_DIR" 2>/dev/null | grep -q . || { echo "No sites set up. Credentials live in $SITES_DIR"; return; }
  local f
  for f in "$SITES_DIR"/*; do
    [ -f "$f" ] || continue
    printf '%s\t%s\tuser=%s\n' "$(basename "$f")" "$(site_url "$f")" "$(site_login "$f")"
  done
}

cmd_add_site() {
  local url="${1:-}" login="${2:-}" pass="${3:-}" host f
  [ -n "$url" ] && [ -n "$login" ] && [ -n "$pass" ] || die "usage: add-site URL USERNAME 'APP PASSWORD'"
  url="${url%/}"
  case "$url" in *://*) ;; *) url="https://$url";; esac
  host="${url#*://}"; host="${host%%/*}"
  mkdir -p "$SITES_DIR"; chmod 700 "$CONFIG_DIR" "$SITES_DIR"
  f="$SITES_DIR/$host"
  umask 077
  printf '# site %s\n# login %s\nuser = "%s:%s"\n' "$url" "$login" "$login" "$pass" > "$f"
  chmod 600 "$f"
  echo "Saved credentials for $host ($url) to $f"
}

cmd_remove_site() { resolve_site "${1:-}"; rm -f "$SITE_FILE"; echo "Removed $SITE_HOST"; }

# --- http -------------------------------------------------------------------

# rest ROUTE [curl args...] -> sets BODY and HTTP (no subshell, so both survive)
rest() {
  local route="$1"; shift
  local tmp; tmp="$(mktemp)"
  HTTP="$(curl -sS -K "$SITE_FILE" -o "$tmp" -w '%{http_code}' -H 'Accept: application/json' "${SITE_URL}/?rest_route=${route}" "$@")" || { rm -f "$tmp"; die "Could not reach $SITE_URL"; }
  BODY="$(cat "$tmp")"; rm -f "$tmp"
}

fail_if_error() {
  # $1 body, $2 status
  case "$2" in
    2*) return 0;;
    401) die "The site rejected the username or Application Password (HTTP 401). Either the password is wrong, or the host strips the Authorization header before WordPress sees it.";;
    *) die "$(printf '%s' "$1" | sed -n 's/.*"code":"\([^"]*\)".*"message":"\([^"]*\)".*/\1: \2/p' | head -n 1) (HTTP $2)";;
  esac
}

json_field() { # json_field NAME <<< json  (first flat string/number value)
  sed -n "s/.*\"$1\":\"\{0,1\}\([^\",}]*\)\"\{0,1\}[,}].*/\1/p" | head -n 1 | sed 's#\\/#/#g'
}

collection() { case "${1:-page}" in page) echo /wp/v2/pages;; post) echo /wp/v2/posts;; *) die "--type must be page or post";; esac; }

# Decode a JSON string (already stripped of its surrounding quotes) to UTF-8 text.
# Sequential parser: handles \" \\ \/ \b \f \n \r \t and \uXXXX including
# surrogate pairs. Runs awk in the C locale so %c emits single bytes.
json_unescape() {
  LC_ALL=C awk '
    function hexval(h,  i, n) { n = 0; h = tolower(h); for (i = 1; i <= length(h); i++) n = n * 16 + index("0123456789abcdef", substr(h, i, 1)) - 1; return n }
    function utf8(cp) {
      if (cp < 128) return sprintf("%c", cp)
      if (cp < 2048) return sprintf("%c%c", 192 + int(cp / 64), 128 + cp % 64)
      if (cp < 65536) return sprintf("%c%c%c", 224 + int(cp / 4096), 128 + int(cp / 64) % 64, 128 + cp % 64)
      return sprintf("%c%c%c%c", 240 + int(cp / 262144), 128 + int(cp / 4096) % 64, 128 + int(cp / 64) % 64, 128 + cp % 64)
    }
    {
      out = ""; n = length($0); i = 1
      while (i <= n) {
        c = substr($0, i, 1)
        if (c != "\\") { out = out c; i++; continue }
        e = substr($0, i + 1, 1); i += 2
        if (e == "n") out = out "\n"
        else if (e == "t") out = out "\t"
        else if (e == "r") out = out "\r"
        else if (e == "b") out = out "\b"
        else if (e == "f") out = out "\f"
        else if (e == "u") {
          cp = hexval(substr($0, i, 4)); i += 4
          if (cp >= 55296 && cp <= 56319 && substr($0, i, 2) == "\\u") { lo = hexval(substr($0, i + 2, 4)); i += 6; cp = 65536 + (cp - 55296) * 1024 + (lo - 56320) }
          out = out utf8(cp)
        }
        else out = out e
      }
      printf "%s", out
    }'
}

urlencode() {
  LC_ALL=C awk -v s="$1" 'BEGIN {
    for (i = 0; i < 256; i++) ord[sprintf("%c", i)] = i
    out = ""
    for (i = 1; i <= length(s); i++) { c = substr(s, i, 1)
      if (c ~ /[A-Za-z0-9._~-]/) out = out c; else out = out sprintf("%%%02X", ord[c]) }
    printf "%s", out }'
}

# --- argument parsing helper ------------------------------------------------

TYPE=page; SEARCH=""; LIMIT=20; OUT=""; TITLE=""; CONTENT_FILE=""; STATUS=""; SLUG=""; TEMPLATE=""; ALT=""; PARENT=""
parse_opts() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --type) TYPE="$2"; shift 2;;
      --search) SEARCH="$2"; shift 2;;
      --limit) LIMIT="$2"; shift 2;;
      --out) OUT="$2"; shift 2;;
      --title) TITLE="$2"; shift 2;;
      --content-file) CONTENT_FILE="$2"; shift 2;;
      --status) STATUS="$2"; shift 2;;
      --slug) SLUG="$2"; shift 2;;
      --template) TEMPLATE="$2"; shift 2;;
      --alt) ALT="$2"; shift 2;;
      --parent) PARENT="$2"; shift 2;;
      *) die "Unknown option: $1";;
    esac
  done
}

# --- commands ---------------------------------------------------------------

cmd_me() {
  resolve_site "${1:-}"
  local body; rest '/wp/v2/users/me&context=edit'; body="$BODY"; fail_if_error "$body" "$HTTP"
  echo "site: $SITE_URL"
  echo "user: $(printf '%s' "$body" | json_field username)"
  echo "roles: $(printf '%s' "$body" | sed -n 's/.*"roles":\[\([^]]*\)\].*/\1/p' | tr -d '"')"
  local cap missing=""
  for cap in edit_pages publish_pages edit_posts publish_posts upload_files unfiltered_html edit_theme_options; do
    if printf '%s' "$body" | grep -q "\"$cap\":true"; then echo "$cap: yes"; else echo "$cap: NO"; missing="$missing $cap"; fi
  done
  echo "missing:${missing:- none}"
}

cmd_find() {
  resolve_site "${1:-}"; shift; parse_opts "$@"
  local q="$(collection "$TYPE")&context=edit&status=any&orderby=modified&order=desc&per_page=${LIMIT}&_fields=id,type,status,title.raw,slug,link,modified&_pretty=1"
  [ -n "$SEARCH" ] && q="$q&search=$(urlencode "$SEARCH")"
  local body; rest "$q"; body="$BODY"; fail_if_error "$body" "$HTTP"; printf '%s\n' "$body"
}

cmd_get() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$id" ] || die "usage: get SITE ID"
  local body; rest "$(collection "$TYPE")/${id}&context=edit&_fields=content.raw"; body="$BODY"; fail_if_error "$body" "$HTTP"
  local raw; raw="$(printf '%s' "$body" | sed -e 's/^{"content":{"raw":"//' -e 's/"}}$//')"
  if [ -n "$OUT" ]; then printf '%s' "$raw" | json_unescape > "$OUT"; echo "saved_to: $OUT ($(wc -c < "$OUT" | tr -d ' ') bytes)"
  else printf '%s' "$raw" | json_unescape; fi
}

print_item() { # print_item BODY  (flat _fields response)
  local b="$1"
  printf 'id: %s\ntype: %s\nstatus: %s\ntitle: %s\nslug: %s\nlink: %s\nedit_link: %s/wp-admin/post.php?post=%s&action=edit\n' \
    "$(printf '%s' "$b" | json_field id)" "$(printf '%s' "$b" | json_field type)" "$(printf '%s' "$b" | json_field status)" \
    "$(printf '%s' "$b" | json_field raw)" "$(printf '%s' "$b" | json_field slug)" "$(printf '%s' "$b" | json_field link)" \
    "$SITE_URL" "$(printf '%s' "$b" | json_field id)"
}

ITEM_FIELDS='_fields=id,type,status,title.raw,slug,link'

cmd_create() {
  resolve_site "${1:-}"; shift; parse_opts "$@"
  [ -n "$TITLE" ] && [ -n "$CONTENT_FILE" ] || die "usage: create SITE --title T --content-file F [--type page|post] [--status publish|draft|private]"
  [ -f "$CONTENT_FILE" ] || die "No such file: $CONTENT_FILE"
  set -- -F "title=$TITLE" -F "status=${STATUS:-publish}" -F "content=<$CONTENT_FILE"
  [ -n "$SLUG" ] && set -- "$@" -F "slug=$SLUG"
  [ -n "$PARENT" ] && set -- "$@" -F "parent=$PARENT"
  [ -n "$TEMPLATE" ] && set -- "$@" -F "template=$TEMPLATE"
  local body; rest "$(collection "$TYPE")&$ITEM_FIELDS" "$@"; body="$BODY"; fail_if_error "$body" "$HTTP"
  print_item "$body"
  # WordPress records no revision on create; re-saving the same content once
  # makes the first version restorable later.
  rest "$(collection "$TYPE")/$(printf '%s' "$body" | json_field id)&_fields=id" -F "content=<$CONTENT_FILE" >/dev/null || true
}

cmd_update() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$id" ] || die "usage: update SITE ID [--content-file F] [--title T] [--status S]"
  set --
  [ -n "$CONTENT_FILE" ] && { [ -f "$CONTENT_FILE" ] || die "No such file: $CONTENT_FILE"; set -- "$@" -F "content=<$CONTENT_FILE"; }
  [ -n "$TITLE" ] && set -- "$@" -F "title=$TITLE"
  [ -n "$STATUS" ] && set -- "$@" -F "status=$STATUS"
  [ -n "$SLUG" ] && set -- "$@" -F "slug=$SLUG"
  [ -n "$PARENT" ] && set -- "$@" -F "parent=$PARENT"
  [ $# -gt 0 ] || die "Nothing to update: pass --content-file, --title, --status, --slug, --template, or --parent."
  local body; rest "$(collection "$TYPE")/${id}&$ITEM_FIELDS" "$@"; body="$BODY"; fail_if_error "$body" "$HTTP"
  print_item "$body"
}

cmd_revisions() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$id" ] || die "usage: revisions SITE ID"
  local body; rest "$(collection "$TYPE")/${id}/revisions&context=edit&per_page=${LIMIT}&_fields=id,modified,content.raw"; body="$BODY"; fail_if_error "$body" "$HTTP"
  echo "revision_id	modified	bytes   (newest first; the newest normally matches the current content)"
  printf '%s\n' "$body" | sed 's/},{/}\
{/g' | grep -v '^\[\]$' | while IFS= read -r line; do
    printf '%s\t%s\t%s\n' "$(printf '%s' "$line" | json_field id)" "$(printf '%s' "$line" | json_field modified)" \
      "$(printf '%s' "$line" | sed -e 's/^.*"raw":"//' -e 's/"}}[]}]*$//' | json_unescape | wc -c | tr -d ' ')"
  done
}

cmd_restore() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; REVISION=""
  while [ $# -gt 0 ]; do case "$1" in --revision) REVISION="$2"; shift 2;; --type) TYPE="$2"; shift 2;; *) die "Unknown option: $1";; esac; done
  [ -n "$id" ] && [ -n "$REVISION" ] || die "usage: restore SITE ID --revision RID"
  local body; rest "$(collection "$TYPE")/${id}/revisions/${REVISION}&context=edit&_fields=content.raw"; body="$BODY"; fail_if_error "$body" "$HTTP"
  # Re-send the still-JSON-escaped string verbatim; nothing needs decoding.
  local tmp; tmp="$(mktemp)"
  printf '{"content":%s}' "$(printf '%s' "$body" | sed -e 's/^{"content":{"raw":/ /' -e 's/}}$//' -e 's/^ //')" > "$tmp"
  rest "$(collection "$TYPE")/${id}&$ITEM_FIELDS" -H 'Content-Type: application/json' --data-binary "@$tmp"; rm -f "$tmp"; body="$BODY"; fail_if_error "$body" "$HTTP"
  print_item "$body"
  echo "restored_revision: $REVISION"
}

cmd_trash() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$id" ] || die "usage: trash SITE ID"
  local body; rest "$(collection "$TYPE")/${id}&$ITEM_FIELDS" -X DELETE; body="$BODY"; fail_if_error "$body" "$HTTP"
  print_item "$body"
}

# One media item per line, minus camera metadata and per-size file/mime/filesize noise.
media_clean() {
  sed -e 's/,"image_meta":{[^{}]*}//g' -e 's/"file":"[^"]*",//g' -e 's/"mime_type":"[^"]*",//g' -e 's/"filesize":[0-9]*,//g' -e 's#\\/#/#g' -e 's/},{"id":/}\
{"id":/g' -e 's/^\[//' -e 's/\]$//'; echo
}

cmd_media() {
  resolve_site "${1:-}"; shift; parse_opts "$@"
  local q="/wp/v2/media&media_type=image&per_page=${LIMIT}&_fields=id,title.rendered,alt_text,source_url,media_details"
  [ -n "$SEARCH" ] && q="$q&search=$(urlencode "$SEARCH")"
  local body; rest "$q"; body="$BODY"; fail_if_error "$body" "$HTTP"
  printf '%s' "$body" | media_clean
}

cmd_upload() {
  resolve_site "${1:-}"; local file="${2:-}"; shift 2; parse_opts "$@"
  [ -f "$file" ] || die "No such file: $file"
  set -- -F "file=@$file"
  [ -n "$TITLE" ] && set -- "$@" -F "title=$TITLE"
  [ -n "$ALT" ] && set -- "$@" -F "alt_text=$ALT"
  local body; rest '/wp/v2/media&_fields=id,title.rendered,alt_text,source_url,media_details' "$@"; body="$BODY"; fail_if_error "$body" "$HTTP"
  printf '%s' "$body" | media_clean
}

cmd_check() {
  resolve_site "${1:-}"; local id="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$id" ] || die "usage: check SITE ID"
  local body; rest "$(collection "$TYPE")/${id}&_fields=link,status"; body="$BODY"; fail_if_error "$body" "$HTTP"
  local link status; link="$(printf '%s' "$body" | json_field link)"; status="$(printf '%s' "$body" | json_field status)"
  local tmp code; tmp="$(mktemp)"
  code="$(curl -sS -o "$tmp" -w '%{http_code}' -A 'ai-canvas-check' "$link")" || code=000
  yn() { grep -q "$1" "$tmp" && echo yes || echo no; }
  echo "link: $link"
  echo "status: $status"
  echo "http: $code"
  echo "public: $([ "$code" = 200 ] && [ "$status" = publish ] && echo yes || echo no)"
  echo "alignfull_wrapper: $(yn 'class="wp-block-html alignfull"')"
  echo "style_tag_present: $(yn 'data-wp-block-html="css"')"
  echo "script_tag_present: $(yn 'data-wp-block-html="js"')"
  echo "script_was_escaped: $(yn '&lt;script')"
  # wptexturize turns & into &#038; inside anything it takes for a tag, and a bare < in the script opens one.
  echo "script_ampersand_rewritten: $(awk '/data-wp-block-html="js"/ { f = 1 } f && /&#038;/ { hit = 1 } f && /<\/script>/ { f = 0 } END { print hit ? "yes" : "no" }' "$tmp")"
  rm -f "$tmp"
}

# --- templates (block themes; needs edit_theme_options) ---------------------

template_fail_hint() {
  case "$HTTP" in 401|403) case "$BODY" in *rest_cannot_manage_templates*) die "This site's connection user cannot manage templates (needs the Administrator role / edit_theme_options).";; esac;; esac
}

cmd_templates() {
  resolve_site "${1:-}"
  rest '/wp/v2/templates&_fields=slug,source,is_custom,title.rendered,theme'; template_fail_hint; fail_if_error "$BODY" "$HTTP"
  printf 'slug\tsource\tcustom\ttitle\n'
  printf '%s\n' "$BODY" | sed 's/},{/}\
{/g' | grep -v '^\[\]$' | while IFS= read -r line; do
    printf '%s\t%s\t%s\t%s\n' "$(printf '%s' "$line" | json_field slug)" "$(printf '%s' "$line" | json_field source)" \
      "$(printf '%s' "$line" | json_field is_custom)" "$(printf '%s' "$line" | json_field rendered)"
  done
}

active_theme() { # sets THEME (stylesheet slug of the active theme)
  [ -n "${THEME:-}" ] && return 0
  rest '/wp/v2/themes&status=active&_fields=stylesheet'; template_fail_hint; fail_if_error "$BODY" "$HTTP"
  THEME="$(printf '%s' "$BODY" | json_field stylesheet)"
  [ -n "$THEME" ] || die "Could not determine the active theme"
}

template_raw() { # template_raw SLUG -> decoded block markup on stdout (empty if no such template)
  active_theme
  rest "/wp/v2/templates/${THEME}//$(urlencode "$1")&_fields=content.raw"; template_fail_hint
  [ "$HTTP" = 404 ] && return 0
  fail_if_error "$BODY" "$HTTP"
  printf '%s' "$BODY" | sed -e 's/^{"content":{"raw":"//' -e 's/"}}$//' | json_unescape
}

cmd_template_get() {
  resolve_site "${1:-}"; local slug="${2:-}"; shift 2; parse_opts "$@"
  [ -n "$slug" ] || die "usage: template-get SITE SLUG [--out FILE]"
  local content; content="$(template_raw "$slug")"
  [ -n "$content" ] || die "No template with slug '$slug' on the active theme"
  if [ -n "$OUT" ]; then printf '%s\n' "$content" > "$OUT"; echo "saved_to: $OUT"; else printf '%s\n' "$content"; fi
}

template_create() { # template_create SLUG TITLE DESCRIPTION FILE
  rest '/wp/v2/templates&_fields=slug,is_custom,status' -F "slug=$1" -F "title=$2" -F "description=$3" -F "content=<$4"; template_fail_hint; fail_if_error "$BODY" "$HTTP"
  echo "created: $1"
}

cmd_template_ensure() {
  resolve_site "${1:-}"
  local page tmp_head tmp_foot tmp
  page="$(template_raw page)"
  [ -n "$page" ] || die "The active theme has no 'page' template; is it a block theme?"
  tmp="$(mktemp -d)"
  # Template-part blocks before the first post-content block are the header side; after it, the footer side.
  printf '%s\n' "$page" | awk '/wp:post-content/ { seen = 1 } /<!-- wp:template-part / && !seen' > "$tmp/head"
  printf '%s\n' "$page" | awk '/wp:post-content/ { seen = 1; next } /<!-- wp:template-part / && seen' > "$tmp/foot"
  [ -s "$tmp/head" ] || echo "note: no header template part found in the theme's page template; the framed template will have no header" >&2
  [ -s "$tmp/foot" ] || echo "note: no footer template part found in the theme's page template; the framed template will have no footer" >&2
  {
    cat "$tmp/head"
    printf '<!-- wp:group {"tagName":"main","layout":{"type":"constrained"}} -->\n<main class="wp-block-group"><!-- wp:post-content {"align":"full","layout":{"type":"constrained"}} /--></main>\n<!-- /wp:group -->\n'
    cat "$tmp/foot"
  } > "$tmp/framed.html"
  printf '<!-- wp:post-content {"layout":{"type":"constrained"}} /-->\n' > "$tmp/blank.html"
  local existing; existing="$(template_raw ai-canvas-framed)"
  if [ -n "$existing" ]; then echo "exists: ai-canvas-framed"; else
    template_create ai-canvas-framed "AI Canvas (with header and footer)" "Site header, the page content, site footer. No page title." "$tmp/framed.html"; fi
  existing="$(template_raw ai-canvas-blank)"
  if [ -n "$existing" ]; then echo "exists: ai-canvas-blank"; else
    template_create ai-canvas-blank "AI Canvas (blank)" "Only the page content. No header, footer, or page title." "$tmp/blank.html"; fi
  echo "header_parts: $(grep -c . "$tmp/head" | tr -d ' ')"
  echo "footer_parts: $(grep -c . "$tmp/foot" | tr -d ' ')"
  rm -rf "$tmp"
}

cmd_template_delete() {
  resolve_site "${1:-}"; local slug="${2:-}"
  [ -n "$slug" ] || die "usage: template-delete SITE SLUG"
  active_theme
  rest "/wp/v2/templates/${THEME}//$(urlencode "$slug")&_fields=id,source"; template_fail_hint
  [ "$HTTP" = 404 ] && die "No template with slug '$slug'"
  fail_if_error "$BODY" "$HTTP"
  case "$BODY" in *'"source":"custom"'*) ;; *) die "Template '$slug' comes from the theme, not a custom one; refusing to delete";; esac
  rest "/wp/v2/templates/${THEME}//$(urlencode "$slug")&force=true&_fields=deleted" -X DELETE; template_fail_hint; fail_if_error "$BODY" "$HTTP"
  echo "deleted: $slug"
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
  sites) cmd_sites "$@";;
  add-site) cmd_add_site "$@";;
  remove-site) cmd_remove_site "$@";;
  me) cmd_me "$@";;
  find) cmd_find "$@";;
  get) cmd_get "$@";;
  create) cmd_create "$@";;
  update) cmd_update "$@";;
  revisions) cmd_revisions "$@";;
  restore) cmd_restore "$@";;
  trash) cmd_trash "$@";;
  media) cmd_media "$@";;
  upload) cmd_upload "$@";;
  check) cmd_check "$@";;
  templates) cmd_templates "$@";;
  template-get) cmd_template_get "$@";;
  template-ensure) cmd_template_ensure "$@";;
  template-delete) cmd_template_delete "$@";;
  contrast) cmd_contrast "$@";;
  -h|--help|help|"") sed -n '2,37p' "$0" | sed 's/^# \{0,1\}//';;
  *) die "Unknown command: $cmd (try: wp.sh help)";;
esac
