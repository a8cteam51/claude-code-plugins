#!/usr/bin/env bash
#
# standards-audit.sh — enforce the machine-checkable standards for a generated
# block theme:
#   1. Block markup (templates/, parts/, patterns/) contains ONLY <!-- wp ... -->
#      comments. Any other HTML comment is a violation.
#   2. Custom CSS is minimal — report the footprint so it can be reviewed.
#   3. Block CSS is one file per block type, each enqueued via wp_enqueue_block_style().
#      Standalone layout: assets/css/blocks/<block>.css, enqueued from functions.php.
#      Template layout (a8csp-project-template theme): assets/css/src/blocks/<block>.scss,
#      built to assets/css/build/blocks/<block>.css and enqueued from functions.php or
#      includes/*.php. Stray, unbuilt, or unenqueued block stylesheets are violations.
#   4. No templates/front-page.html — the homepage must be a WordPress page set as
#      the static front page via Reading settings, not a template.
#   5. No blocks in the theme — no block.json anywhere under the theme. Blocks come from
#      the A8C Special Projects blocks monorepo, or (template mode, approved exclusions
#      only) the features mu-plugin.
#   6. No preset slug that collides with a class core uses as a flag: a palette entry named
#      text, link or border, or a font size named custom, restyles every block carrying
#      has-text-color, has-link-color, has-border-color or has-custom-font-size.
#   7. No colour function (rgb(), rgba(), hsl(), …) in a block's element, state or viewport
#      styles. WordPress compiles those on the server and drops such a declaration.
#   8. No fraction of a pixel: a value written in px is a whole number, in theme.json, in
#      block markup and in the theme's stylesheet sources. A breakpoint is the last whole
#      pixel of its range, and a finer value uses a relative unit.
#   9. Every core/post-content block in a template or part has a constrained layout, so a
#      block is as wide as the content column unless it is aligned wide or full, in the
#      editor as on the page.
#  10. Every core/group block has a name (metadata.name), in templates, parts, patterns and
#      page content, so that a person can read the tree in the markup and in the List View.
#  11. No setting written as a class. A has-* class in a block's className, a font family or
#      font size class with no fontFamily or fontSize attribute behind it, and a className
#      that the theme's own stylesheets select: each shows in the editor as an Additional
#      CSS class and in no control. A class hook is a registered block style (is-style-*).
#  12. Every file under parts/ is declared in theme.json templateParts with its area. Without
#      the area a header or footer part renders as a <div>, not as a landmark.
#  13. Standalone layout: no comment in style.css or a block stylesheet after the file's
#      header comment.
#   It also lists, for review, image blocks in templates and parts that point at a theme
#   file and reserve no space (no width and height, no aspectRatio).
#   A theme.json that is missing or does not parse is a failure of its own: checks 6 and 8
#   cannot read it, and WordPress ignores it.
#
# Usage: standards-audit.sh --theme-dir <dir> [--layout auto|standalone|template]
#                           [--content-dir <dir>]
# --content-dir adds a directory of page-content markup files (*.html) to checks 1, 7, 8, 10
# and 11, since page content lives in the database and not in the theme.
# Exits non-zero if stray comments, block-CSS organization violations, a front-page.html
# template, a block inside the theme, a reserved preset slug, a dropped colour, a fraction
# of a pixel, post content without a constrained layout, a group without a name, a setting
# written as a class, an undeclared template part, a stylesheet comment or an unreadable
# theme.json are found.
#
# Last line: H2BT_AUDIT_OK ... or H2BT_AUDIT_FAIL ..., on every exit path but a usage error.
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage: standards-audit.sh --theme-dir <dir> [--layout auto|standalone|template]
                          [--content-dir <dir>]

Scans <dir>/templates, <dir>/parts, <dir>/patterns for HTML comments that are not
Gutenberg block delimiters, measures the custom-CSS footprint, checks that block CSS is
one file per block type enqueued via wp_enqueue_block_style(), checks that the theme
ships no templates/front-page.html and no block.json, that no preset slug in theme.json
collides with a core flag class, that no element, state or viewport style holds a
colour function WordPress drops, that no value is a fraction of a pixel, that every
template gives post content a constrained layout, that every group block has a name, that
no setting is written as a class, that every template part is declared in theme.json, and
(standalone layout) that no stylesheet carries a comment after its file header.
Prints a report. Exits 1 on any violation, 0 otherwise.

--layout auto (default) picks "template" when the theme has assets/sass/style.scss,
includes/, and .phpcs.xml (an a8csp-project-template theme), else "standalone".

--content-dir names a directory of page-content markup files (*.html), such as
<site-path>/.h2bt/pages. They get the comment, colour-function, whole-pixel, group-name
and class checks too.
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

# A run that cannot audit ends with the sentinel too, so that its last line is never read as a pass.
cannot_audit() { # cannot_audit <reason, no spaces> <message>
	echo "$2" >&2
	echo "H2BT_AUDIT_FAIL reason=$1"
	exit 1
}

theme_dir=""
layout="auto"
content_dir=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--theme-dir) need_value "$@"; theme_dir="$2"; shift 2 ;;
		--layout) need_value "$@"; layout="$2"; shift 2 ;;
		--content-dir) need_value "$@"; content_dir="$2"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$theme_dir" ]] || { echo "--theme-dir is required" >&2; exit 2; }
# Paths are reported, and matched, relative to the theme: a trailing slash would defeat both.
while [[ "$theme_dir" == */ && "$theme_dir" != "/" ]]; do theme_dir="${theme_dir%/}"; done
[[ -d "$theme_dir" ]] || cannot_audit theme-dir-not-found "Theme directory not found: $theme_dir"
[[ -z "$content_dir" || -d "$content_dir" ]] || cannot_audit content-dir-not-found "Content directory not found: $content_dir"
# Every check below passes on a directory that holds nothing to check, so make sure this is a theme.
[[ -f "$theme_dir/theme.json" || -f "$theme_dir/style.css" ]] || cannot_audit not-a-theme "Not a theme directory (no theme.json and no style.css): $theme_dir"
if [[ "$layout" == "auto" ]]; then
	if [[ -f "$theme_dir/assets/sass/style.scss" && -d "$theme_dir/includes" && -f "$theme_dir/.phpcs.xml" ]]; then
		layout="template"
	else
		layout="standalone"
	fi
fi
[[ "$layout" == "standalone" || "$layout" == "template" ]] || { echo "--layout must be auto, standalone, or template" >&2; exit 2; }
echo "Layout: $layout"
echo

echo "== Comment audit (block markup) =="
command -v perl >/dev/null 2>&1 || cannot_audit no-perl "perl is required for the comment audit"
violations=0
while IFS= read -r -d '' file; do
	# Strip wp block delimiters first, then flag any HTML comment that remains —
	# this catches stray comments that share a line with a wp delimiter. A delimiter whose
	# attributes wrap over several lines is one delimiter: the file is read whole, and each
	# delimiter is replaced by the line breaks it held so that line numbers stay true.
	matches="$(perl -0777 -ne 's{<!--\s*/?wp:.*?-->}{ my $kept = $&; $kept =~ tr/\n//cd; $kept }gse; my $number = 0; for my $line ( split /\n/, $_, -1 ) { $number++; print "$number\n" if $line =~ /<!--/; }' "$file" || true)"
	if [[ -n "$matches" ]]; then
		while IFS= read -r lineno; do
			[[ -z "$lineno" ]] && continue
			echo "  STRAY COMMENT  ${file#$theme_dir/}:${lineno}"
			violations=$((violations + 1))
		done <<<"$matches"
	fi
done < <(find "$theme_dir/templates" "$theme_dir/parts" "$theme_dir/patterns" ${content_dir:+"$content_dir"} \
	-type f \( -name '*.html' -o -name '*.php' \) -print0 2>/dev/null)

if [[ "$violations" -eq 0 ]]; then
	echo "  OK — no stray comments in block markup"
fi

echo
echo "== Custom CSS footprint =="
# Lines of CSS a reviewer reads: comments (/* */, and // in SCSS) and blank lines excluded, so
# the theme-header comment in style.css does not count.
css_lines() {
	perl -0777 -ne 's{/\*.*?\*/}{}gs; s{^\s*//.*$}{}mg; print scalar( grep { /\S/ } split /\n/ ), "\n";' "$1"
}
total=0
found_css=0
if [[ "$layout" == "template" ]]; then
	footprint_find=( "$theme_dir/assets/sass" "$theme_dir/assets/css/src" -type f \( -name '*.scss' -o -name '*.css' \) )
else
	footprint_find=( "$theme_dir" -type f -name '*.css' )
fi
while IFS= read -r -d '' css; do
	found_css=1
	count="$(css_lines "$css")"
	total=$((total + count))
	echo "  ${css#$theme_dir/}: ${count} CSS lines"
done < <(find "${footprint_find[@]}" -print0 2>/dev/null | sort -z)

if [[ "$found_css" -eq 0 ]]; then
	echo "  (no stylesheet sources found)"
fi
echo "  TOTAL custom CSS lines: ${total}"
if [[ "$layout" == "template" ]]; then
	echo "  NOTE: counts the Sass/SCSS sources (built CSS is generated from them); lower is better."
else
	echo "  NOTE: comments and blank lines excluded; lower is better. Review each rule against the report."
fi

echo
echo "== Block CSS organization =="
css_org=0
functions_php="$theme_dir/functions.php"

if [[ "$layout" == "template" ]]; then
	# Sources under assets/css/src/blocks/, built into assets/css/build/blocks/, enqueued from
	# functions.php or includes/*.php (the template loads every includes/*.php file).
	php_sources=( "$functions_php" )
	while IFS= read -r -d '' inc; do php_sources+=( "$inc" ); done < <(find "$theme_dir/includes" -maxdepth 1 -type f -name '*.php' -print0 2>/dev/null)
	if [[ -d "$theme_dir/assets/css/src/blocks" ]] && ! grep -qs "wp_enqueue_block_style" "${php_sources[@]}"; then
		echo "  MISSING     no theme PHP file calls wp_enqueue_block_style()"
		css_org=$((css_org + 1))
	fi
	while IFS= read -r -d '' src; do
		base="$(basename "$src" .scss)"
		built="$theme_dir/assets/css/build/blocks/$base.css"
		if [[ ! -f "$built" ]]; then
			echo "  UNBUILT     ${src#$theme_dir/} — no assets/css/build/blocks/$base.css (run the build)"
			css_org=$((css_org + 1))
		elif grep -qsF "$base.css" "${php_sources[@]}"; then
			echo "  OK          ${src#$theme_dir/} -> assets/css/build/blocks/$base.css (enqueued)"
		else
			echo "  UNENQUEUED  ${src#$theme_dir/} — $base.css is not referenced in functions.php or includes/*.php"
			css_org=$((css_org + 1))
		fi
	done < <(find "$theme_dir/assets/css/src/blocks" -type f -name '*.scss' -print0 2>/dev/null | sort -z)

	while IFS= read -r -d '' css; do
		rel="${css#$theme_dir/}"
		case "$rel" in
			style.css|style-rtl.css|style-editor.css) ;;
			assets/sass/*.scss|assets/sass/*/*.scss) ;;
			assets/css/src/blocks/*.scss) ;;
			assets/css/build/blocks/*.css)
				[[ -f "$theme_dir/assets/css/src/blocks/$(basename "$css" .css).scss" ]] || {
					echo "  ORPHAN      ${rel} — built block CSS with no assets/css/src/blocks/ source"
					css_org=$((css_org + 1))
				}
				;;
			assets/css/src/*.scss|assets/css/build/*.css)
				echo "  PER-PURPOSE ${rel} — not block CSS; allowed, list it in the report with what enqueues it"
				;;
			*)
				echo "  STRAY       ${rel} — block CSS goes in assets/css/src/blocks/<block>.scss; root styles in assets/sass/"
				css_org=$((css_org + 1))
				;;
		esac
	done < <(find "$theme_dir" -path "$theme_dir/node_modules" -prune -o -type f \( -name '*.css' -o -name '*.scss' \) -print0 2>/dev/null)

	if [[ "$css_org" -eq 0 ]]; then
		echo "  OK — block CSS is one Sass source per block type, built and enqueued via wp_enqueue_block_style()"
	fi
else
	blocks_css_dir="$theme_dir/assets/css/blocks"

	# 1. Every per-block stylesheet must be enqueued via wp_enqueue_block_style() in functions.php.
	if [[ -d "$blocks_css_dir" && -n "$(find "$blocks_css_dir" -type f -name '*.css' -print 2>/dev/null | head -1)" ]]; then
		if [[ ! -f "$functions_php" ]]; then
			echo "  MISSING     functions.php — block CSS files exist but cannot be enqueued"
			css_org=$((css_org + 1))
		elif ! grep -q "wp_enqueue_block_style" "$functions_php"; then
			echo "  MISSING     functions.php never calls wp_enqueue_block_style()"
			css_org=$((css_org + 1))
		fi
		while IFS= read -r -d '' bcss; do
			base="$(basename "$bcss")"
			if [[ -f "$functions_php" ]] && grep -qF "$base" "$functions_php"; then
				echo "  OK          ${bcss#$theme_dir/} (enqueued)"
			else
				echo "  UNENQUEUED  ${bcss#$theme_dir/} — not referenced in functions.php"
				css_org=$((css_org + 1))
			fi
		done < <(find "$blocks_css_dir" -type f -name '*.css' -print0 2>/dev/null)
	fi

	# 2. Block CSS must be one file per block type under assets/css/blocks/. Flag strays.
	#    Allowed elsewhere: only the theme-header style.css. Themes contain no blocks, so no
	#    block-bundled CSS either (see the theme blocks check).
	while IFS= read -r -d '' css; do
		rel="${css#$theme_dir/}"
		case "$rel" in
			style.css) ;;
			assets/css/blocks/*.css) ;;
			*)
				echo "  STRAY       ${rel} — block CSS must be one file per block type under assets/css/blocks/"
				css_org=$((css_org + 1))
				;;
		esac
	done < <(find "$theme_dir" -type f -name '*.css' -print0 2>/dev/null)

	if [[ "$css_org" -eq 0 ]]; then
		echo "  OK — block CSS is one file per block type, each enqueued via wp_enqueue_block_style()"
	fi
fi

echo
echo "== Front-page template check =="
front_page=0
if [[ -f "$theme_dir/templates/front-page.html" ]]; then
	echo "  FORBIDDEN   templates/front-page.html — set a page as the front page via Reading settings instead"
	front_page=1
else
	echo "  OK — no templates/front-page.html"
fi

echo
echo "== Theme blocks check =="
theme_blocks=0
while IFS= read -r -d '' block_json; do
	echo "  FORBIDDEN   ${block_json#$theme_dir/} — blocks never live in a theme; reuse or build them in the blocks monorepo"
	theme_blocks=$((theme_blocks + 1))
done < <(find "$theme_dir" -name node_modules -prune -o -name block.json -type f -print0)
if [[ "$theme_blocks" -eq 0 ]]; then
	echo "  OK — no block.json in the theme"
fi

echo
echo "== Preset slugs, block attributes and pixel values =="
command -v python3 >/dev/null 2>&1 || cannot_audit no-python3 "python3 is required for the theme.json and block attribute checks"
# The report goes through a file: bash 3.2 misparses a here-document inside $( ).
attr_report="$(mktemp "${TMPDIR:-/tmp}/h2bt-audit.XXXXXX")"
python3 - "$theme_dir" "$content_dir" "$layout" >"$attr_report" <<'PY' || { rm -f "$attr_report"; cannot_audit attribute-checks-crashed "The theme.json and block attribute checks failed to run."; }
import json
import os
import re
import sys

theme_dir, content_dir, layout = sys.argv[1], sys.argv[2], sys.argv[3]
reserved = dropped = review = subpixel = unconstrained = invalid = unnamed = 0
class_hooks = undeclared = css_comments = 0
# So that a page of forty groups does not bury the rest of the report.
UNNAMED_SHOWN = 8
COMMENTS_SHOWN = 8

# A value written in pixels is a whole number of pixels: 767.98px, 0.5px and -.75px are not.
# 1.0px is: its fraction is nothing.
SUBPIXEL = re.compile(r'(?<![\w.])-?\d*\.\d+px\b')
POST_CONTENT = re.compile(r'<!--\s+wp:(?:core/)?post-content(?:\s+(\{.*?\}))?\s+/?-->', re.S)

# What a pixel rule does not speak about: a comment, the geometry of a drawing, an embedded file.
CSS_COMMENT = re.compile(r'/\*.*?\*/', re.S)
SCSS_LINE_COMMENT = re.compile(r'(?<![:\w"\'(])//[^\n]*')
INLINE_SVG = re.compile(r'<svg\b.*?</svg>', re.S | re.I)
DATA_URI = re.compile(r'url\(\s*["\']?data:.*?\)', re.S | re.I)

# A class a stylesheet selects, the class attributes of a block's own HTML, and the two
# typography preset classes, whose attribute has the same name on every block.
CLASS_SELECTOR = re.compile(r'\.(-?[_a-zA-Z][\w-]*)')
CLASS_ATTRIBUTE = re.compile(r'\bclass="([^"]*)"')
NEXT_DELIMITER = re.compile(r'<!--\s+/?wp:')
TYPOGRAPHY_CLASS = re.compile(r'^has-(.+)-(font-family|font-size)$')
TYPOGRAPHY_ATTRIBUTE = {'font-family': 'fontFamily', 'font-size': 'fontSize'}
# Classes that are not the theme's hooks even when its stylesheet selects them: a registered
# style, what core itself writes into className (an embed's aspect ratio), core's hidden text.
CORE_CLASS = ('is-style-', 'wp-', 'screen-reader-text')


def blanked(pattern, text):
    """Blank out what a pattern matches, keeping its line breaks so that line numbers stay true."""
    return pattern.sub(lambda match: re.sub(r'[^\n]', ' ', match.group(0)), text)


def report_subpixel(label, text):
    """Print each fraction of a pixel in a file, with the lines it is on, and return how many."""
    text = blanked(DATA_URI, text)
    if label.endswith(('.css', '.scss')):
        text = blanked(CSS_COMMENT, text)
        if label.endswith('.scss'):
            text = blanked(SCSS_LINE_COMMENT, text)
    elif label.endswith(('.html', '.php')):
        text = blanked(INLINE_SVG, text)
    found = {}
    for number, line in enumerate(text.split('\n'), 1):
        for value in SUBPIXEL.findall(line):
            if float(value[:-2]) == int(float(value[:-2])):
                continue
            found.setdefault(value, []).append(number)
    for value, lines in sorted(found.items()):
        shown = ', '.join(str(number) for number in lines[:6]) + (', …' if len(lines) > 6 else '')
        print('  SUBPIXEL    %s: %s (line %s) — write a whole number of pixels, or a relative unit' % (label, value, shown))
    return sum(len(lines) for lines in found.values())

# A preset's class is .has-<slug>-color (or -font-size), printed with !important. These slugs
# produce the class core itself adds as a flag to any block with a text colour, a link colour,
# a border colour or a custom font size, so the preset would restyle every such block.
RESERVED = (
    (('settings', 'color', 'palette'), {'text': 'has-text-color', 'link': 'has-link-color', 'border': 'has-border-color'}),
    (('settings', 'typography', 'fontSizes'), {'custom': 'has-custom-font-size'}),
)

try:
    with open(os.path.join(theme_dir, 'theme.json'), encoding='utf-8') as handle:
        theme_json = json.load(handle)
except (OSError, ValueError) as error:
    theme_json = None
    invalid = 1
    print('  INVALID     theme.json could not be read (%s) — WordPress ignores a theme.json that does not parse, and the preset slugs and its pixel values were not checked' % error)

if theme_json is not None:
    for path, slugs in RESERVED:
        node = theme_json
        for key in path:
            node = node.get(key, {}) if isinstance(node, dict) else {}
        for preset in node if isinstance(node, list) else []:
            slug = preset.get('slug') if isinstance(preset, dict) else None
            if slug in slugs:
                print('  RESERVED    theme.json %s slug "%s" — its class .%s is a flag core adds to blocks; name the preset by role'
                      % ('.'.join(path), slug, slugs[slug]))
                reserved += 1
    if reserved == 0:
        print('  OK — no preset slug collides with a core flag class')
    with open(os.path.join(theme_dir, 'theme.json'), encoding='utf-8') as handle:
        subpixel += report_subpixel('theme.json', handle.read())

    # WordPress takes a part's area from theme.json, by the part's slug, and its tag from the area.
    listed = theme_json.get('templateParts')
    declared = {part.get('name') for part in (listed if isinstance(listed, list) else [])
                if isinstance(part, dict) and isinstance(part.get('area'), str)}
    parts_dir = os.path.join(theme_dir, 'parts')
    for root, _, names in os.walk(parts_dir):
        for name in sorted(names):
            if not name.endswith('.html'):
                continue
            slug = os.path.relpath(os.path.join(root, name), parts_dir)[:-5].replace(os.sep, '/')
            if slug not in declared:
                print('  UNDECLARED  parts/%s.html is not in theme.json templateParts — without its area a header or footer part renders as a <div>; add {"name":"%s","title":"<its name in the editor>","area":"header | footer | uncategorized"}'
                      % (slug, slug))
                undeclared += 1
    if undeclared == 0:
        print('  OK — every template part is declared in theme.json with its area')

DELIMITER = re.compile(r'<!--\s+wp:([a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)?)(?:\s+(\{.*?\}))?\s+/?-->', re.S)
COLOR_FUNCTION = re.compile(r'\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(', re.I)
KEPT_FUNCTION = re.compile(r'(?:\b(?:var|calc|min|max|minmax|clamp)|-gradient)\($', re.I)


def without_kept_functions(value):
    """Drop var(), calc() and the like, and gradients, with whatever they contain: WordPress keeps those."""
    out, index = [], 0
    while index < len(value):
        if value[index] == '(' and KEPT_FUNCTION.search(value[:index + 1]):
            depth, index = 1, index + 1
            while index < len(value) and depth:
                depth += {'(': 1, ')': -1}.get(value[index], 0)
                index += 1
            continue
        out.append(value[index])
        index += 1
    return ''.join(out)


def server_compiled(node, path, inside):
    """Yield string values under an element, state (:hover) or viewport (@mobile) key."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from server_compiled(value, path + [key], inside or key == 'elements' or key[:1] in (':', '@'))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from server_compiled(value, path + [str(index)], inside)
    elif isinstance(node, str) and inside and COLOR_FUNCTION.search(without_kept_functions(node)):
        yield '.'.join(path), node


def markup_files():
    for folder in ('templates', 'parts', 'patterns'):
        for root, _, names in os.walk(os.path.join(theme_dir, folder)):
            for name in sorted(names):
                if name.endswith(('.html', '.php')):
                    full = os.path.join(root, name)
                    yield full, os.path.relpath(full, theme_dir), folder != 'patterns'
    if content_dir:
        for root, _, names in os.walk(content_dir):
            for name in sorted(names):
                if name.endswith('.html'):
                    full = os.path.join(root, name)
                    yield full, full, False


def stylesheet_sources():
    """The stylesheets a person edits: not node_modules, not build output, not Sass's root output."""
    generated = ('style.css', 'style-rtl.css', 'style-editor.css') if layout == 'template' else ()
    for root, folders, names in os.walk(theme_dir):
        folders[:] = [folder for folder in folders if folder not in ('node_modules', 'build', 'vendor')]
        for name in sorted(names):
            if name.endswith(('.css', '.scss')) and not (root == theme_dir and name in generated):
                yield os.path.join(root, name)


styled_classes = set()
for full in stylesheet_sources():
    try:
        with open(full, encoding='utf-8', errors='replace') as handle:
            sheet = blanked(CSS_COMMENT, blanked(DATA_URI, handle.read()))
    except OSError:
        continue
    styled_classes.update(CLASS_SELECTOR.findall(sheet))

for full, label, theme_file in markup_files():
    try:
        with open(full, encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError:
        continue
    subpixel += report_subpixel(label, text)
    unnamed_here = 0
    if theme_file:
        for match in POST_CONTENT.finditer(text):
            try:
                attrs = json.loads(match.group(1)) if match.group(1) else {}
            except ValueError:
                attrs = {}
            block_layout = attrs.get('layout') if isinstance(attrs, dict) else None
            # "inherit": true is the older spelling of the constrained layout.
            if not isinstance(block_layout, dict) or not (block_layout.get('type') == 'constrained' or block_layout.get('inherit') is True):
                print('  FULL WIDTH  %s:%d post-content has no constrained layout — give it "layout":{"type":"constrained"} and align the wider sections of the content'
                      % (label, text.count('\n', 0, match.start()) + 1))
                unconstrained += 1
    for match in DELIMITER.finditer(text):
        try:
            attrs = json.loads(match.group(2)) if match.group(2) else {}
        except ValueError:
            continue
        if not isinstance(attrs, dict):
            continue
        name = match.group(1)[5:] if match.group(1).startswith('core/') else match.group(1)
        line = text.count('\n', 0, match.start()) + 1
        if name == 'group':
            metadata = attrs.get('metadata')
            group_name = metadata.get('name') if isinstance(metadata, dict) else None
            if not isinstance(group_name, str) or not group_name.strip():
                unnamed += 1
                unnamed_here += 1
                if unnamed_here <= UNNAMED_SHOWN:
                    print('  UNNAMED     %s:%d group has no name — add "metadata":{"name":"<what it is>"}, such as "Hero" or "Feature card"'
                          % (label, line))
        class_name = attrs.get('className') if isinstance(attrs.get('className'), str) else ''
        for token in class_name.split():
            if token.startswith('has-'):
                print('  CLASS HOOK  %s:%d %s className "%s" — a setting written as a class shows in no editor control; set the block\'s own attribute (fontFamily, fontSize, textColor, backgroundColor, style.typography.textAlign) and drop the class'
                      % (label, line, name, token))
                class_hooks += 1
            elif not token.startswith(CORE_CLASS) and token in styled_classes:
                print('  CLASS HOOK  %s:%d %s className "%s" is a hook for the theme\'s stylesheet — use the block\'s own attribute, or register it as a block style and apply is-style-<slug>'
                      % (label, line, name, token))
                class_hooks += 1
        # The block's own HTML runs to the next delimiter. A preset class there with no attribute
        # behind it validates, and the editor then reads it as an Additional CSS class.
        following = NEXT_DELIMITER.search(text, match.end())
        own_html = text[match.end():following.start() if following else len(text)]
        for classes in CLASS_ATTRIBUTE.findall(own_html):
            for token in classes.split():
                preset = TYPOGRAPHY_CLASS.match(token)
                if not preset or token == 'has-custom-font-size' or token in class_name.split():
                    continue
                attribute = TYPOGRAPHY_ATTRIBUTE[preset.group(2)]
                if attribute not in attrs:
                    print('  CLASS HOOK  %s:%d %s has the class "%s" and no %s attribute — the editor shows it as an Additional CSS class, not in the typography control; set "%s" to the preset\'s slug'
                          % (label, line, name, token, attribute, attribute))
                    class_hooks += 1
        for where, value in server_compiled(attrs.get('style'), ['style'], False):
            print('  DROPPED     %s:%d %s %s = %s — WordPress drops a colour function here; write eight-digit hex'
                  % (label, line, name, where, value))
            dropped += 1
        # An image block with no attributes at all is the plainest image that points at a theme file.
        if theme_file and name == 'image' and 'id' not in attrs:
            if not (('width' in attrs and 'height' in attrs) or 'aspectRatio' in attrs):
                print('  REVIEW      %s:%d image points at a theme file and has no width and height, and no aspectRatio — it reserves no space while it loads'
                      % (label, line))
                review += 1
    if unnamed_here > UNNAMED_SHOWN:
        print('  UNNAMED     %s: and %d more groups without a name' % (label, unnamed_here - UNNAMED_SHOWN))

for full in stylesheet_sources():
    try:
        with open(full, encoding='utf-8', errors='replace') as handle:
            subpixel += report_subpixel(os.path.relpath(full, theme_dir), handle.read())
    except OSError:
        continue

# Template layout: its Sass partials are the repository's, and stylelint is their gate.
if layout == 'standalone':
    sheets = [os.path.join(theme_dir, 'style.css')]
    blocks_dir = os.path.join(theme_dir, 'assets', 'css', 'blocks')
    if os.path.isdir(blocks_dir):
        sheets += [os.path.join(blocks_dir, name) for name in sorted(os.listdir(blocks_dir)) if name.endswith('.css')]
    for full in sheets:
        try:
            with open(full, encoding='utf-8', errors='replace') as handle:
                sheet = blanked(DATA_URI, handle.read())
        except OSError:
            continue
        # The comment that opens a file is its header: the theme header, or a line that names the file.
        header = re.match(r'\s*/\*.*?\*/', sheet, re.S)
        lines = [sheet.count('\n', 0, match.start()) + 1 for match in CSS_COMMENT.finditer(sheet, header.end() if header else 0)]
        for number in lines[:COMMENTS_SHOWN]:
            print('  CSS COMMENT %s:%d — a stylesheet carries no comment after its file header; the reason for a rule goes in the report'
                  % (os.path.relpath(full, theme_dir), number))
        if len(lines) > COMMENTS_SHOWN:
            print('  CSS COMMENT %s: and %d more comments' % (os.path.relpath(full, theme_dir), len(lines) - COMMENTS_SHOWN))
        css_comments += len(lines)

if class_hooks == 0:
    print('  OK — no setting written as a class, and no unregistered class hook')
if layout == 'standalone' and css_comments == 0:
    print('  OK — no stylesheet comment after a file header')
if dropped == 0:
    print('  OK — no colour function in element, state or viewport styles')
if subpixel == 0:
    print('  OK — every pixel value is a whole number of pixels')
if unconstrained == 0:
    print('  OK — every post-content block has a constrained layout')
if review == 0:
    print('  OK — every theme-file image in a template or part reserves its space')
if unnamed == 0:
    print('  OK — every group block has a name')
print('COUNTS %d %d %d %d %d %d %d %d %d %d' % (reserved, dropped, review, subpixel, unconstrained, invalid, unnamed, class_hooks, undeclared, css_comments))
PY
sed '$d' "$attr_report"
read -r _ reserved_slugs dropped_colors image_review subpixel_values post_content_layout theme_json unnamed_groups class_hooks template_parts css_comments < <(tail -1 "$attr_report")
rm -f "$attr_report"

echo
if [[ "$violations" -gt 0 || "$css_org" -gt 0 || "$front_page" -gt 0 || "$theme_blocks" -gt 0 || "$reserved_slugs" -gt 0 || "$dropped_colors" -gt 0 || "$subpixel_values" -gt 0 || "$post_content_layout" -gt 0 || "$theme_json" -gt 0 || "$unnamed_groups" -gt 0 || "$class_hooks" -gt 0 || "$template_parts" -gt 0 || "$css_comments" -gt 0 ]]; then
	echo "H2BT_AUDIT_FAIL layout=${layout} stray_comments=${violations} css_org=${css_org} front_page=${front_page} theme_blocks=${theme_blocks} reserved_slugs=${reserved_slugs} dropped_colors=${dropped_colors} subpixel_values=${subpixel_values} post_content_layout=${post_content_layout} theme_json=${theme_json} unnamed_groups=${unnamed_groups} class_hooks=${class_hooks} template_parts=${template_parts} css_comments=${css_comments} image_review=${image_review} css_lines=${total}"
	exit 1
fi
echo "H2BT_AUDIT_OK layout=${layout} stray_comments=0 css_org=0 front_page=0 theme_blocks=0 reserved_slugs=0 dropped_colors=0 subpixel_values=0 post_content_layout=0 theme_json=0 unnamed_groups=0 class_hooks=0 template_parts=0 css_comments=0 image_review=${image_review} css_lines=${total}"
