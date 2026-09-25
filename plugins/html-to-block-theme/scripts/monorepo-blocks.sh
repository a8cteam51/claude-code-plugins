#!/usr/bin/env bash
#
# monorepo-blocks.sh — work with the A8C Special Projects blocks monorepo
# (a8cteam51/special-projects-blocks-monorepo) from an html-to-block-theme run.
#
#   catalog  List every plugin in the monorepo with its blocks, descriptions, screenshot and
#            latest release, from a cached clone refreshed on each call. Read this before
#            planning any custom block.
#   install  Install monorepo plugins on a Studio site from their latest release ZIP, the way
#            production installs them, and activate them.
#   clone    Clone the monorepo into a Studio site's wp-content/plugins and activate its
#            autoloader, to build a new block (the autoloader loads only plugins with build/).
#
# Each subcommand ends with a sentinel line (H2BT_MONOREPO_*) the caller greps for.
#
# Requires git and python3. Release lookups use `gh` when it is installed and signed in,
# otherwise the public GitHub REST API.
#
set -euo pipefail

repo="${H2BT_BLOCKS_MONOREPO:-a8cteam51/special-projects-blocks-monorepo}"
repo_url="https://github.com/${repo}.git"
clone_name="special-projects-blocks-monorepo"

usage() {
	cat <<'EOF'
Usage:
  monorepo-blocks.sh catalog [--cache-dir <dir>]
  monorepo-blocks.sh install --site-path <site> <plugin-dir> [<plugin-dir>...]
  monorepo-blocks.sh clone --site-path <site>

catalog   Prints one tab-separated line per monorepo plugin:
            plugin-dir  blocks  latest-release  screenshot  description
          "blocks" lists every block.json name; "-" marks a plugin that extends core blocks
          without registering its own. Ends with H2BT_MONOREPO_CATALOG plugins=<n> cache=<dir>.
          The cache defaults to ${XDG_CACHE_HOME:-~/.cache}/h2bt/special-projects-blocks-monorepo.

install   For each plugin directory, installs its latest release ZIP with
          `studio wp plugin install <url> --activate` and prints
          H2BT_MONOREPO_INSTALL plugin=<dir> version=<version>. Refuses a plugin that is also
          built in a monorepo clone on the same site, which would register its blocks twice.

clone     Clones the monorepo into <site>/wp-content/plugins/special-projects-blocks-monorepo
          (or fetches it when present) and activates the autoloader. Prints
          H2BT_MONOREPO_CLONE dir=<path>. Build new blocks there with `npm run new-block`.
EOF
}

# Prints every release tag of the monorepo, one per line.
release_tags() {
	if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
		gh release list --repo "$repo" --limit 1000 --json tagName --jq '.[].tagName'
		return
	fi
	local page=1 body
	while :; do
		body="$(curl -fsSL "https://api.github.com/repos/${repo}/releases?per_page=100&page=${page}")" || {
			echo "Could not list releases for ${repo} (GitHub API)." >&2
			return 1
		}
		printf '%s' "$body" | python3 -c 'import json,sys; [print(r["tag_name"]) for r in json.load(sys.stdin)]'
		[[ "$(printf '%s' "$body" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))')" -lt 100 ]] && break
		page=$((page + 1))
	done
}

# Reads tags on stdin; prints "<plugin-dir>\t<latest version>" per plugin, by version order.
latest_versions() {
	python3 -c '
import re, sys
best = {}
for tag in sys.stdin.read().split():
    if "@" not in tag:
        continue
    plugin, version = tag.rsplit("@", 1)
    key = tuple(int(n) for n in re.findall(r"\d+", version))
    if plugin not in best or key > best[plugin][0]:
        best[plugin] = (key, version)
for plugin, (_, version) in sorted(best.items()):
    print(f"{plugin}\t{version}")
'
}

cmd_catalog() {
	local cache_dir="${XDG_CACHE_HOME:-$HOME/.cache}/h2bt/${clone_name}"
	while [[ $# -gt 0 ]]; do
		case "$1" in
			--cache-dir) cache_dir="${2:-}"; shift 2 ;;
			*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
		esac
	done

	if [[ -d "$cache_dir/.git" ]]; then
		git -C "$cache_dir" fetch -q --depth 1 origin trunk
		git -C "$cache_dir" checkout -q --detach FETCH_HEAD
	else
		mkdir -p "$(dirname "$cache_dir")"
		git clone -q --depth 1 "$repo_url" "$cache_dir"
	fi

	local versions
	versions="$(release_tags | latest_versions)" || versions=""

	VERSIONS="$versions" python3 - "$cache_dir" <<'PY'
import glob, json, os, re, sys

root = sys.argv[1]
latest = dict(line.split("\t", 1) for line in os.environ.get("VERSIONS", "").splitlines() if "\t" in line)
count = 0
for plugin in sorted(os.listdir(root)):
    entry = os.path.join(root, plugin, f"{plugin}.php")
    if plugin.startswith(".") or not os.path.isfile(entry):
        continue
    names, descriptions = [], []
    for path in sorted(glob.glob(os.path.join(root, plugin, "src", "**", "block.json"), recursive=True)):
        try:
            data = json.load(open(path))
        except (OSError, ValueError):
            continue
        if data.get("name"):
            names.append(data["name"])
        if data.get("description"):
            descriptions.append(data["description"])
    if not descriptions:
        header = open(entry, encoding="utf-8", errors="replace").read(4000)
        match = re.search(r"^\s*\*?\s*Description:\s*(.+)$", header, re.M)
        if match:
            descriptions.append(match.group(1).strip())
    screenshot = "yes" if os.path.isfile(os.path.join(root, plugin, "screenshot.png")) else "no"
    description = " | ".join(dict.fromkeys(descriptions)) or "-"
    print("\t".join([plugin, ",".join(names) or "-", latest.get(plugin, "unreleased"), screenshot, description]))
    count += 1
print(f"H2BT_MONOREPO_CATALOG plugins={count} cache={root}")
PY
}

cmd_install() {
	local site_path="" plugins=()
	while [[ $# -gt 0 ]]; do
		case "$1" in
			--site-path) site_path="${2:-}"; shift 2 ;;
			-*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
			*) plugins+=("$1"); shift ;;
		esac
	done
	[[ -n "$site_path" && -d "$site_path" ]] || { echo "--site-path must name the Studio site directory" >&2; exit 2; }
	[[ ${#plugins[@]} -gt 0 ]] || { echo "Name at least one monorepo plugin directory" >&2; exit 2; }
	command -v studio >/dev/null 2>&1 || { echo "The studio CLI is required" >&2; exit 1; }

	local versions plugin version url clone_build
	versions="$(release_tags | latest_versions)"
	for plugin in "${plugins[@]}"; do
		clone_build="$site_path/wp-content/plugins/${clone_name}/${plugin}/build"
		if [[ -d "$clone_build" ]]; then
			echo "H2BT_MONOREPO_INSTALL_FAIL plugin=${plugin} reason=\"also built in the monorepo clone (${clone_build}); remove that build or skip the ZIP\""
			exit 1
		fi
		version="$(printf '%s\n' "$versions" | awk -F'\t' -v p="$plugin" '$1 == p { print $2 }')"
		if [[ -z "$version" ]]; then
			echo "H2BT_MONOREPO_INSTALL_FAIL plugin=${plugin} reason=\"no release found\""
			exit 1
		fi
		url="https://github.com/${repo}/releases/download/${plugin}@${version}/${plugin}.zip"
		studio wp plugin install "$url" --activate --force --path="$site_path" 2>&1 | grep -v -i 'deprecated' || true
		if ! studio wp plugin is-active "$plugin" --path="$site_path" >/dev/null 2>&1; then
			echo "H2BT_MONOREPO_INSTALL_FAIL plugin=${plugin} reason=\"not active after install from ${url}\""
			exit 1
		fi
		echo "H2BT_MONOREPO_INSTALL plugin=${plugin} version=${version}"
	done
}

cmd_clone() {
	local site_path=""
	while [[ $# -gt 0 ]]; do
		case "$1" in
			--site-path) site_path="${2:-}"; shift 2 ;;
			*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
		esac
	done
	[[ -n "$site_path" && -d "$site_path/wp-content/plugins" ]] || { echo "--site-path must name a Studio site with wp-content/plugins" >&2; exit 2; }
	command -v studio >/dev/null 2>&1 || { echo "The studio CLI is required" >&2; exit 1; }

	local dir="$site_path/wp-content/plugins/${clone_name}"
	if [[ -d "$dir/.git" ]]; then
		git -C "$dir" fetch -q origin
	else
		git clone -q "$repo_url" "$dir"
	fi
	studio wp plugin activate "$clone_name" --path="$site_path" 2>&1 | grep -v -i 'deprecated' || true
	studio wp plugin is-active "$clone_name" --path="$site_path" >/dev/null 2>&1 || {
		echo "H2BT_MONOREPO_CLONE_FAIL dir=${dir} reason=\"autoloader not active\""
		exit 1
	}
	echo "H2BT_MONOREPO_CLONE dir=${dir}"
}

subcommand="${1:-}"
[[ $# -gt 0 ]] && shift
case "$subcommand" in
	catalog) cmd_catalog "$@" ;;
	install) cmd_install "$@" ;;
	clone) cmd_clone "$@" ;;
	-h|--help|"") usage ;;
	*) echo "Unknown subcommand: $subcommand" >&2; usage >&2; exit 2 ;;
esac
