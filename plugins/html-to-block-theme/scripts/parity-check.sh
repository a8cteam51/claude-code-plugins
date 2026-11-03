#!/usr/bin/env bash
#
# parity-check.sh — pixel-parity guard for a Studio site whose wp-content is an
# a8csp-project-template repository. Take a baseline, change code (port a theme into the
# template, run an auto-fixer such as `npm run format`, refactor CSS), then compare: every
# full-page screenshot must match the baseline exactly.
#
# Captures are deterministic by construction: reduced motion, CSS animations disabled, the page
# scrolled through so lazy images load, and localStorage seeded to suppress popups. Two
# baselines of an unchanged site are pixel-identical, so any difference is a real regression.
# The comparison allows no differing pixel and no colour tolerance, and compare never writes a
# baseline: a path or width that has none fails until --mode baseline is run for it.
#
# It drives the repository's own @playwright/test (a template devDependency) with the local
# Chrome (the skill already requires Chrome). Files live under <repo>/tests/.cache/h2bt-parity/,
# which the template's .gitignore already ignores.
#
# Usage:
#   parity-check.sh --repo <wp-content> --base-url <url> --paths "/,/about/" \
#     --mode baseline|compare [--widths 1440,390] [--local-storage key=value]...
#
# Last line: H2BT_PARITY_OK mode=<mode> shots=<n> or H2BT_PARITY_FAIL mode=<mode> ... (exit 1).
#
set -euo pipefail

usage() {
	cat <<'EOF'
Usage:
  parity-check.sh --repo <wp-content> --base-url <url> --paths "/,/about/" \
    --mode baseline|compare [--widths 1440,390] [--local-storage key=value]...

  --mode baseline   capture (or replace) the reference screenshots
  --mode compare    capture again and fail on any pixel difference from the baseline
  --widths          comma-separated viewport widths (default 1440,390)
  --local-storage   key=value pairs seeded before each page loads (repeatable), e.g. to mark a
                    newsletter popup as dismissed
EOF
}

# A flag that takes a value must be followed by one.
need_value() { [[ $# -ge 2 ]] || { echo "$1 needs a value" >&2; exit 2; }; }

repo=""
base_url=""
paths=""
mode=""
widths="1440,390"
storage=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--repo) need_value "$@"; repo="$2"; shift 2 ;;
		--base-url) need_value "$@"; base_url="$2"; shift 2 ;;
		--paths) need_value "$@"; paths="$2"; shift 2 ;;
		--mode) need_value "$@"; mode="$2"; shift 2 ;;
		--widths) need_value "$@"; widths="$2"; shift 2 ;;
		--local-storage) need_value "$@"; storage+=("$2"); shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$repo" && -d "$repo" ]] || { echo "--repo must name the template repository" >&2; exit 2; }
[[ -n "$base_url" && -n "$paths" ]] || { echo "--base-url and --paths are required" >&2; exit 2; }
[[ "$mode" == "baseline" || "$mode" == "compare" ]] || { echo "--mode must be baseline or compare" >&2; exit 2; }
repo="$(cd "$repo" && pwd -P)"

# Every failure after this point ends with the sentinel, so a caller that reads only the last
# line never mistakes a run that did not happen for one that passed.
fail() { # fail <reason, no spaces> <message>
	echo "$2" >&2
	echo "H2BT_PARITY_FAIL mode=$mode reason=$1"
	exit 1
}

[[ -d "$repo/node_modules/@playwright/test" ]] || fail no-playwright "No @playwright/test in $repo/node_modules; run npm ci there first."

work="$repo/tests/.cache/h2bt-parity"
mkdir -p "$work"
if ! git -C "$repo" check-ignore -q "$work/probe" 2>/dev/null; then
	fail not-ignored "$work is not git-ignored; refusing to write screenshots into the repository."
fi

# One screenshot per path and width. Playwright keeps only letters, digits and hyphens of a
# name, which made / and /home/, or /about/team/ and /about-team/, one file. So the name
# carries a short hash of the path as well as its readable form.
shots_json="$(python3 -c '
import hashlib, json, re, sys
paths = [p for p in sys.argv[1].split(",") if p]
widths = [w for w in sys.argv[2].split(",") if w]
def name(path):
    trimmed = path.strip("/")
    label = re.sub(r"[^A-Za-z0-9]+", "-", trimmed).strip("-") or "root"
    return "%s-%s" % (label, hashlib.md5(trimmed.encode()).hexdigest()[:8])
shots, seen = [], {}
for width in widths:
    if not width.isdigit():
        sys.exit("--widths must be whole numbers: " + width)
    for path in paths:
        shot = "%s-%s.png" % (name(path), width)
        if shot in seen:
            sys.exit("%s and %s would share the screenshot %s; check one of them in a separate run" % (seen[shot], path, shot))
        seen[shot] = path
        shots.append({"path": path, "width": int(width), "name": shot})
if not shots:
    sys.exit("--paths and --widths name no screenshot")
print(json.dumps(shots))
' "$paths" "$widths")" || { echo "H2BT_PARITY_FAIL mode=$mode reason=bad-paths-or-widths"; exit 1; }
shot_names="$(python3 -c 'import json,sys; print("\n".join(shot["name"] for shot in json.loads(sys.argv[1])))' "$shots_json")"

if [[ "$mode" == "compare" ]]; then
	missing=""
	while IFS= read -r name; do
		[[ -f "$work/snapshots/$name" ]] || missing="$missing $name"
	done <<<"$shot_names"
	[[ -z "$missing" ]] || fail no-baseline "No baseline for:$missing (under $work/snapshots). Run --mode baseline for these paths and widths, on the unchanged site, first."
fi

cat >"$work/playwright.config.js" <<'EOF'
const { defineConfig } = require( '@playwright/test' );

module.exports = defineConfig( {
	testDir: __dirname,
	testMatch: 'parity.spec.js',
	outputDir: __dirname + '/results',
	snapshotPathTemplate: __dirname + '/snapshots/{arg}{ext}',
	fullyParallel: false,
	workers: 1,
	retries: 0,
	reporter: 'line',
	timeout: 180000,
	// Compare never writes a screenshot: a missing baseline is a failure, not a new baseline.
	updateSnapshots: process.env.H2BT_PARITY_MODE === 'baseline' ? 'all' : 'none',
	use: { channel: process.env.H2BT_PARITY_CHANNEL || 'chrome' },
} );
EOF

cat >"$work/parity.spec.js" <<'EOF'
const { test, expect } = require( '@playwright/test' );

const baseUrl = process.env.H2BT_PARITY_BASE_URL.replace( /\/$/, '' );
const shots = JSON.parse( process.env.H2BT_PARITY_SHOTS );
const storage = JSON.parse( process.env.H2BT_PARITY_STORAGE || '{}' );

{
	for ( const { path, width, name } of shots ) {
		test( `${ path } at ${ width }px`, async ( { browser } ) => {
			const context = await browser.newContext( {
				viewport: { width, height: width > 600 ? 900 : 844 },
				deviceScaleFactor: 1,
				reducedMotion: 'reduce',
			} );
			await context.addInitScript( ( entries ) => {
				for ( const [ key, value ] of Object.entries( entries ) ) {
					try {
						window.localStorage.setItem( key, value );
					} catch ( error ) {}
				}
			}, storage );
			const page = await context.newPage();
			// networkidle can hang on sites with long-lived requests; load plus a scroll-through
			// (so lazy images start) is enough.
			await page.goto( baseUrl + path, { waitUntil: 'load', timeout: 60000 } );
			await page.evaluate( async () => {
				await document.fonts.ready;
				const step = Math.max( 200, Math.floor( window.innerHeight * 0.6 ) );
				for ( let y = 0; y < document.documentElement.scrollHeight; y += step ) {
					window.scrollTo( 0, y );
					await new Promise( ( resolve ) => setTimeout( resolve, 60 ) );
				}
				window.scrollTo( 0, 0 );
				await Promise.race( [
					Promise.all(
						[ ...document.images ].map( ( image ) =>
							image.complete
								? null
								: new Promise( ( resolve ) => {
										image.onload = image.onerror = resolve;
								  } )
						)
					),
					new Promise( ( resolve ) => setTimeout( resolve, 5000 ) ),
				] );
			} );
			await page.waitForTimeout( 1000 );
			// Both limits are needed for an exact match: without threshold: 0 Playwright
			// accepts a pixel whose colour moved by up to a fifth of the scale.
			await expect( page ).toHaveScreenshot( name, {
				fullPage: true,
				animations: 'disabled',
				caret: 'hide',
				maxDiffPixels: 0,
				threshold: 0,
				timeout: 60000,
			} );
			await context.close();
		} );
	}
}
EOF

storage_json="$(python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "${storage[@]+"${storage[@]}"}")"
args=( playwright test --config "$work/playwright.config.js" )

set +e
( cd "$repo" && H2BT_PARITY_MODE="$mode" H2BT_PARITY_BASE_URL="$base_url" H2BT_PARITY_SHOTS="$shots_json" H2BT_PARITY_STORAGE="$storage_json" ./node_modules/.bin/"${args[@]}" ) >"$work/last-run.log" 2>&1
status=$?
set -e

# The screenshots this run was about, not every file an earlier run left in the directory.
wanted=0
shots=0
while IFS= read -r name; do
	wanted=$((wanted + 1))
	[[ -f "$work/snapshots/$name" ]] && shots=$((shots + 1))
done <<<"$shot_names"

if [[ "$status" -eq 0 && "$shots" -eq "$wanted" ]]; then
	echo "H2BT_PARITY_OK mode=$mode shots=$shots dir=$work/snapshots"
	exit 0
fi
sed 's/\x1b\[[0-9;]*m//g' "$work/last-run.log" | grep -E '✘|Error:|pixels? \(ratio|different|No such file|not found' | head -40 || true
echo "Diff images (expected / actual / diff) are under $work/results."
echo "H2BT_PARITY_FAIL mode=$mode shots=$shots of $wanted log=$work/last-run.log"
exit 1
