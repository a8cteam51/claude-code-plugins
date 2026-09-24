#!/usr/bin/env bash
#
# template-checks.sh — run an a8csp-project-template repository's own quality gates the way CI
# runs them, from a Studio site whose wp-content is that repository.
#
# Why a mirror: the Studio site's wp-content also holds Studio's runtime files (the SQLite
# integration under mu-plugins/, db.php, uploads/). The repo's lint scripts scan whole
# directories and wp-env mounts them, so running in place reports hundreds of errors CI never
# sees. The checks run in a mirror holding only tracked + unignored files — what CI checks out.
# The mirror is synced in place (never deleted) so wp-env bind mounts keep their inodes.
#
# Gates, in order:
#   build        `npm run build` in the repo must leave every tracked/unignored file unchanged
#                (CI's "Build integrity": the committed tree is the deploy artifact)
#   blocks       every tracked block.json is listed in .github/blocks-allowlist (CI's "Blocks policy")
#   php_lint     `composer lint:php` (PHPCS, tests ruleset, PHPStan)
#   js_css_lint  `npm run lint` (ESLint, stylelint, package.json, README)
#   integration  `composer test:integration` in wp-env        (with --tests; needs Docker)
#   e2e          `npm run test:e2e` against the dev wp-env    (with --e2e; needs Docker)
#
# Usage:
#   template-checks.sh --repo <wp-content> [--tests] [--e2e] [--php-bin <php>] [--mirror-dir <dir>]
#
# Last line: H2BT_TEMPLATE_CHECKS_OK ... or H2BT_TEMPLATE_CHECKS_FAIL ... (exit 1).
#
set -uo pipefail

usage() {
	cat <<'EOF'
Usage:
  template-checks.sh --repo <wp-content> [--tests] [--e2e] [--php-bin <php>] [--mirror-dir <dir>]

  --repo        The template repository (the Studio site's wp-content).
  --tests       Also run the PHPUnit integration suite in wp-env (Docker must be running).
  --e2e         Also run the Playwright end-to-end suite against the dev wp-env.
  --php-bin     PHP CLI to use for Composer. Default: `php` if it meets the repo's floor,
                else the newest Studio-bundled PHP (~/.studio/php-bin/*/php) that does.
  --mirror-dir  Where to keep the tracked-files mirror. Default: a stable per-repo
                directory under ${TMPDIR:-/tmp}/h2bt-template-checks/.
EOF
}

repo=""
run_tests=0
run_e2e=0
php_bin=""
mirror=""
while [[ $# -gt 0 ]]; do
	case "$1" in
		--repo) repo="${2:-}"; shift 2 ;;
		--tests) run_tests=1; shift ;;
		--e2e) run_e2e=1; shift ;;
		--php-bin) php_bin="${2:-}"; shift 2 ;;
		--mirror-dir) mirror="${2:-}"; shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$repo" && -d "$repo" ]] || { echo "--repo must name an existing directory" >&2; exit 2; }
repo="$(cd "$repo" && pwd -P)"
[[ -f "$repo/package.json" && -f "$repo/composer.json" ]] || { echo "Not a template repository (no package.json/composer.json): $repo" >&2; exit 2; }

if [[ -z "$mirror" ]]; then
	mirror="${TMPDIR:-/tmp}/h2bt-template-checks/$(basename "$(dirname "$repo")")-$(printf '%s' "$repo" | cksum | cut -d' ' -f1)"
fi
logs="$mirror.logs"
mkdir -p "$mirror" "$logs"

# --- Toolchain -------------------------------------------------------------------------------

version_ge() { # version_ge <have> <need>: true when have >= need (numeric dotted compare)
	[[ "$(printf '%s\n%s\n' "$2" "$1" | sort -t. -k1,1n -k2,2n -k3,3n | head -1)" == "$2" ]]
}

php_floor="$(python3 -c 'import json,re,sys; r=json.load(open(sys.argv[1])).get("require",{}).get("php",""); m=re.search(r"(\d+\.\d+)",r); print(m.group(1) if m else "")' "$repo/composer.json" 2>/dev/null || true)"
php_ok() { [[ -x "$1" ]] && version_ge "$("$1" -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;' 2>/dev/null)" "${php_floor:-0}"; }

if [[ -z "$php_bin" ]]; then
	# Prefer `php` on PATH; otherwise the newest Studio-bundled CLI that meets the floor.
	if command -v php >/dev/null 2>&1 && php_ok "$(command -v php)"; then
		php_bin="$(command -v php)"
	else
		best=""
		for candidate in "$HOME"/.studio/php-bin/*/php; do
			[[ -x "$candidate" ]] && php_ok "$candidate" || continue
			have="$("$candidate" -r 'echo PHP_VERSION;')"
			if [[ -z "$best" ]] || version_ge "$have" "$("$best" -r 'echo PHP_VERSION;')"; then best="$candidate"; fi
		done
		php_bin="$best"
	fi
fi
if [[ -z "$php_bin" ]] || ! php_ok "$php_bin"; then
	echo "No PHP CLI >= ${php_floor} found. Pass --php-bin, or switch any Studio site to PHP ${php_floor} once (studio site set --php ${php_floor}) so Studio downloads its binary." >&2
	echo "H2BT_TEMPLATE_CHECKS_FAIL toolchain=php"
	exit 1
fi
export PATH="$(dirname "$php_bin"):$PATH"

node_floor="$(python3 -c 'import json,re,sys; r=json.load(open(sys.argv[1])).get("engines",{}).get("node",""); m=re.search(r"(\d+)",r); print(m.group(1) if m else "0")' "$repo/package.json" 2>/dev/null || echo 0)"
node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
if [[ "$node_major" -lt "$node_floor" ]]; then
	echo "Node ${node_major} is below the repo's engines floor (${node_floor}). Switch first (e.g. nvm use ${node_floor})." >&2
	echo "H2BT_TEMPLATE_CHECKS_FAIL toolchain=node"
	exit 1
fi
[[ -d "$repo/vendor" ]] || { echo "Run \`composer packages-install\` in $repo first." >&2; echo "H2BT_TEMPLATE_CHECKS_FAIL toolchain=vendor"; exit 1; }
[[ -d "$repo/node_modules" ]] || { echo "Run \`npm ci\` in $repo first." >&2; echo "H2BT_TEMPLATE_CHECKS_FAIL toolchain=node_modules"; exit 1; }
echo "==> PHP $("$php_bin" -r 'echo PHP_VERSION;') ($php_bin), Node $(node -v)"

# Bash 3.2-compatible (macOS /bin/bash): one result_<gate> variable per gate, no associative arrays.
failed=0
record() { # record <gate> <status> [log]
	printf -v "result_$1" '%s' "$2"
	if [[ "$2" == "fail" ]]; then
		failed=1
		echo "  FAIL  $1 — last lines of ${3:-}:"
		[[ -n "${3:-}" ]] && tail -25 "$3" | sed 's/\x1b\[[0-9;]*m//g; s/^/        /'
	else
		echo "  $(printf '%s' "$2" | tr '[:lower:]' '[:upper:]')  $1"
	fi
}

tracked_hashes() {
	( cd "$repo" && git ls-files -co --exclude-standard -z | xargs -0 shasum 2>/dev/null | sort -k2 )
}

# --- build: byte-stable rebuild -------------------------------------------------------------

echo "==> build integrity"
before="$logs/hashes-before.txt"; after="$logs/hashes-after.txt"
tracked_hashes >"$before"
if ( cd "$repo" && npm run build ) >"$logs/build.log" 2>&1; then
	tracked_hashes >"$after"
	if diff -q "$before" "$after" >/dev/null; then
		record build pass
	else
		diff "$before" "$after" | grep '^[<>]' | awk '{print $3}' | sort -u >"$logs/build-changed.txt"
		echo "The rebuild changed these files; commit the rebuilt output (CI rebuilds and fails on any difference):" >>"$logs/build-changed.txt"
		record build fail "$logs/build-changed.txt"
	fi
else
	record build fail "$logs/build.log"
fi

# --- blocks: allowlist ----------------------------------------------------------------------

echo "==> blocks policy"
allowed=""
[[ -f "$repo/.github/blocks-allowlist" ]] && allowed="$(sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$repo/.github/blocks-allowlist")"
: >"$logs/blocks.log"
while IFS= read -r block_json; do
	[[ -z "$block_json" ]] && continue
	grep -qxF -- "$block_json" <<<"$allowed" || echo "UNLISTED $block_json — add it to .github/blocks-allowlist" >>"$logs/blocks.log"
done < <(cd "$repo" && git ls-files -co --exclude-standard | grep -E '(^|/)block\.json$')
if [[ -s "$logs/blocks.log" ]]; then record blocks fail "$logs/blocks.log"; else record blocks pass; fi

# --- mirror ---------------------------------------------------------------------------------

staging="$mirror.staging"
rm -rf "$staging" && mkdir -p "$staging"
( cd "$repo" && git ls-files -co --exclude-standard -z | rsync -a --from0 --files-from=- ./ "$staging/" )
rsync -a --delete --exclude=/vendor --exclude=/node_modules --exclude=/tests/.cache "$staging/" "$mirror/"
rm -rf "$staging"
if [[ "$run_tests" -eq 1 ]]; then
	# The tests container cannot follow a symlink out of its mount, so vendor/ is a real copy.
	[[ -L "$mirror/vendor" ]] && rm "$mirror/vendor"
	rsync -a --delete "$repo/vendor/" "$mirror/vendor/"
elif [[ ! -e "$mirror/vendor" ]]; then
	ln -s "$repo/vendor" "$mirror/vendor"
fi
[[ -e "$mirror/node_modules" ]] || ln -s "$repo/node_modules" "$mirror/node_modules"

# --- lint -----------------------------------------------------------------------------------

echo "==> PHP lint (PHPCS, tests ruleset, PHPStan)"
if ( cd "$mirror" && composer lint:php ) >"$logs/php-lint.log" 2>&1; then record php_lint pass; else record php_lint fail "$logs/php-lint.log"; fi

echo "==> JS + CSS lint"
if ( cd "$mirror" && npm run lint ) >"$logs/js-css-lint.log" 2>&1; then record js_css_lint pass; else record js_css_lint fail "$logs/js-css-lint.log"; fi

# --- tests ----------------------------------------------------------------------------------

docker_up() { docker info >/dev/null 2>&1; }

# wp-env names containers after the config's directory, so this mirror's containers start with
# wp-env-<mirror basename>. Anything else publishing the port is another checkout of the repo
# (or another project): wp-env start then fails, and Playwright silently reuses that other
# server for end-to-end runs. Refuse rather than test the wrong site.
port_owner_conflict() { # port_owner_conflict <config file> <log>
	local port owners
	port="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("port",""))' "$mirror/$1" 2>/dev/null || true)"
	[[ -n "$port" ]] || return 1
	owners="$(docker ps --filter "publish=$port" --format '{{.Names}}' 2>/dev/null | grep -v "^wp-env-$(basename "$mirror")-" || true)"
	[[ -n "$owners" ]] || return 1
	{
		echo "Port $port is published by another environment: $owners"
		echo "Stop it first (\`npx wp-env stop\` in its checkout, or \`docker stop <name>\`), or set another port in an untracked .wp-env.override.json."
	} >"$2"
	return 0
}

result_integration="skipped"
if [[ "$run_tests" -eq 1 ]]; then
	echo "==> integration tests (wp-env)"
	if ! docker_up; then
		echo "Docker is not running." >"$logs/integration.log"
		record integration fail "$logs/integration.log"
	elif port_owner_conflict .wp-env.tests.json "$logs/integration.log"; then
		record integration fail "$logs/integration.log"
	elif ( cd "$mirror" && composer test:integration ) >"$logs/integration.log" 2>&1; then
		record integration pass
	else
		record integration fail "$logs/integration.log"
	fi
fi

result_e2e="skipped"
if [[ "$run_e2e" -eq 1 ]]; then
	echo "==> end-to-end tests (wp-env + Playwright)"
	theme_slug="$(cd "$repo" && git ls-files themes | awk -F/ 'NF > 2 { print $2 }' | sort -u | head -1)"
	if ! docker_up; then
		echo "Docker is not running." >"$logs/e2e.log"
		record e2e fail "$logs/e2e.log"
	elif port_owner_conflict .wp-env.json "$logs/e2e.log"; then
		record e2e fail "$logs/e2e.log"
	else
		# A first start answers HTTP before afterStart has activated the theme; wait for it so
		# the theme smoke does not race the activation.
		( cd "$mirror" && npm run wp-env:start ) >"$logs/e2e.log" 2>&1
		for _ in $(seq 1 60); do
			active="$(cd "$mirror" && ./node_modules/.bin/wp-env run cli wp option get stylesheet 2>/dev/null | tr -d '\r' | tail -1)"
			[[ "$active" == "$theme_slug" ]] && break
			sleep 2
		done
		if ( cd "$mirror" && npm run test:e2e ) >>"$logs/e2e.log" 2>&1; then record e2e pass; else record e2e fail "$logs/e2e.log"; fi
	fi
fi

summary="build=${result_build:-} blocks=${result_blocks:-} php_lint=${result_php_lint:-} js_css_lint=${result_js_css_lint:-} integration=${result_integration} e2e=${result_e2e} mirror=$mirror logs=$logs"
if [[ "$failed" -eq 1 ]]; then
	echo "H2BT_TEMPLATE_CHECKS_FAIL $summary"
	exit 1
fi
echo "H2BT_TEMPLATE_CHECKS_OK $summary"
