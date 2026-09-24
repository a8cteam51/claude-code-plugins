#!/usr/bin/env bash
#
# detect-project-template.sh — decide whether a Studio site's wp-content is a git clone of a
# repository generated from a8cteam51/a8csp-project-template ("template mode"), and if so read
# the identifiers the template makes permanent: theme slug and text domain, the PHP prefix, the
# features mu-plugin, the PHP/WP/Node floors, and which of the template's example features are
# still present.
#
# Usage:
#   detect-project-template.sh --site-path <site>   # inspects <site>/wp-content
#   detect-project-template.sh --repo <dir>         # inspects <dir> directly
#
# Always exits 0 after a successful inspection (it is a probe, not a gate); 2 on usage errors.
# The last line is the machine-readable sentinel:
#   H2BT_TEMPLATE mode=template repo=<dir> theme_slug=<slug> ... (see --help)
#   H2BT_TEMPLATE mode=standalone reason=<why>
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  detect-project-template.sh --site-path <site>
  detect-project-template.sh --repo <wp-content-dir>

Prints the detected layout. In template mode the sentinel carries:
  repo, branch, theme_slug, theme_dir, theme_text_domain, prefix, features_slug,
  features_dir, features_text_domain, features_disabled, php_floor, wp_floor,
  node_engine, examples (template example features still present), allowlist
EOF
}

site_path=""
repo=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--site-path) site_path="${2:-}"; shift 2 ;;
		--repo) repo="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

if [[ -z "$repo" ]]; then
	[[ -n "$site_path" ]] || { echo "--site-path or --repo is required" >&2; usage >&2; exit 2; }
	repo="${site_path%/}/wp-content"
fi
[[ -d "$repo" ]] || { echo "Directory not found: $repo" >&2; exit 2; }
repo="$(cd "$repo" && pwd -P)"

standalone() {
	echo "H2BT_TEMPLATE mode=standalone reason=$1"
	exit 0
}

toplevel="$(git -C "$repo" rev-parse --show-toplevel 2>/dev/null || true)"
[[ -n "$toplevel" && "$(cd "$toplevel" && pwd -P)" == "$repo" ]] || standalone "not-a-git-clone"
[[ -f "$repo/mu-plugins/mu-loader.php" ]] || standalone "no-mu-loader"
if ! grep -q '"a8csp/configs"' "$repo/composer.json" 2>/dev/null && ! grep -q '"@a8csp/configs"' "$repo/package.json" 2>/dev/null; then
	standalone "no-a8csp-configs"
fi

# The theme is the one tracked directory under themes/.
theme_slugs="$(git -C "$repo" ls-files themes | awk -F/ 'NF > 2 { print $2 }' | sort -u)"
theme_count="$(printf '%s\n' "$theme_slugs" | grep -c . || true)"
[[ "$theme_count" -eq 1 ]] || standalone "expected-one-tracked-theme-found-${theme_count}"
theme_slug="$theme_slugs"
theme_dir="$repo/themes/$theme_slug"

# The features plugin is the tracked mu-plugins/<dir>/ whose entry file has a Plugin Name header.
features_slug=""
while IFS= read -r dir; do
	[[ -z "$dir" ]] && continue
	if grep -l 'Plugin Name:' "$repo/mu-plugins/$dir"/*.php >/dev/null 2>&1; then
		features_slug="$dir"
		break
	fi
done < <(git -C "$repo" ls-files mu-plugins | awk -F/ 'NF > 2 { print $2 }' | sort -u)
features_dir=""
[[ -n "$features_slug" ]] && features_dir="$repo/mu-plugins/$features_slug"

header() { # header <file> <name>: the value of a WordPress file-header line.
	sed -n "s/^[[:space:]*]*$2:[[:space:]]*//p" "$1" 2>/dev/null | head -1 | tr -d '\r'
}

prefix="$(python3 - "$theme_dir/.phpcs.xml" <<'PY' 2>/dev/null || true
import re, sys
try:
    xml = open(sys.argv[1]).read()
except OSError:
    sys.exit(0)
m = re.search(r'name="prefixes".*?<element value="([^"]+)"', xml, re.S)
print(m.group(1) if m else '')
PY
)"
theme_text_domain="$(header "$theme_dir/style.css" 'Text Domain')"
features_text_domain=""
features_disabled="no"
if [[ -n "$features_dir" ]]; then
	entry="$(grep -l 'Plugin Name:' "$features_dir"/*.php | head -1)"
	features_text_domain="$(header "$entry" 'Text Domain')"
	[[ -f "$features_dir/.disabled" ]] && features_disabled="yes"
fi

php_floor="$(header "$theme_dir/style.css" 'Requires PHP')"
wp_floor="$(header "$theme_dir/style.css" 'Requires at least')"
node_engine="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("engines",{}).get("node",""))' "$repo/package.json" 2>/dev/null || true)"

# Example features generation ships; each is removed by the recipe co-located in its file.
examples=()
[[ -n "$features_dir" && -f "$features_dir/includes/book-post-type.php" ]] && examples+=("book-cpt")
[[ -n "$features_dir" && -f "$features_dir/includes/book-cover-reminder.php" ]] && examples+=("book-cover-reminder")
[[ -f "$theme_dir/includes/plugin-woocommerce.php" ]] && examples+=("woocommerce-cart")
[[ -f "$theme_dir/patterns/footer-default.php" ]] && examples+=("footer-default-pattern")
[[ -f "$theme_dir/patterns/index-query.php" ]] && examples+=("index-query-pattern")
[[ -f "$theme_dir/templates/singular.html" ]] && examples+=("singular-template")
examples_csv="none"
if [[ ${#examples[@]} -gt 0 ]]; then
	examples_csv="$(IFS=,; echo "${examples[*]}")"
fi

allowlist="no"
[[ -f "$repo/.github/blocks-allowlist" ]] && allowlist="yes"
branch="$(git -C "$repo" branch --show-current 2>/dev/null || true)"

cat <<EOF
Template-mode repository: $repo
  branch:               ${branch:-<detached>}
  theme:                themes/$theme_slug (text domain ${theme_text_domain:-?}, PHP prefix ${prefix:-?})
  features mu-plugin:   ${features_slug:-<none>} (text domain ${features_text_domain:-?}, disabled: $features_disabled)
  floors:               PHP ${php_floor:-?}, WordPress ${wp_floor:-?}, Node ${node_engine:-?}
  template examples:    $examples_csv
  blocks allowlist:     $allowlist
EOF
echo "H2BT_TEMPLATE mode=template repo=$repo branch=${branch:-} theme_slug=$theme_slug theme_dir=$theme_dir theme_text_domain=$theme_text_domain prefix=$prefix features_slug=$features_slug features_dir=$features_dir features_text_domain=$features_text_domain features_disabled=$features_disabled php_floor=$php_floor wp_floor=$wp_floor node_engine=$node_engine examples=$examples_csv allowlist=$allowlist"
