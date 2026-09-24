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

repo=""
base_url=""
paths=""
mode=""
widths="1440,390"
storage=()
while [[ $# -gt 0 ]]; do
	case "$1" in
		--repo) repo="${2:-}"; shift 2 ;;
		--base-url) base_url="${2:-}"; shift 2 ;;
		--paths) paths="${2:-}"; shift 2 ;;
		--mode) mode="${2:-}"; shift 2 ;;
		--widths) widths="${2:-}"; shift 2 ;;
		--local-storage) storage+=("${2:-}"); shift 2 ;;
		-h|--help) usage; exit 0 ;;
		*) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
	esac
done

[[ -n "$repo" && -d "$repo" ]] || { echo "--repo must name the template repository" >&2; exit 2; }
[[ -n "$base_url" && -n "$paths" ]] || { echo "--base-url and --paths are required" >&2; exit 2; }
[[ "$mode" == "baseline" || "$mode" == "compare" ]] || { echo "--mode must be baseline or compare" >&2; exit 2; }
repo="$(cd "$repo" && pwd -P)"
[[ -d "$repo/node_modules/@playwright/test" ]] || { echo "No @playwright/test in $repo/node_modules; run npm ci there first." >&2; exit 1; }

work="$repo/tests/.cache/h2bt-parity"
mkdir -p "$work"
if ! git -C "$repo" check-ignore -q "$work/probe" 2>/dev/null; then
	echo "$work is not git-ignored; refusing to write screenshots into the repository." >&2
	exit 1
fi
if [[ "$mode" == "compare" && ! -d "$work/snapshots" ]]; then
	echo "No baseline under $work/snapshots; run with --mode baseline first." >&2
	exit 1
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
	use: { channel: process.env.H2BT_PARITY_CHANNEL || 'chrome' },
} );
EOF

cat >"$work/parity.spec.js" <<'EOF'
const { test, expect } = require( '@playwright/test' );

const baseUrl = process.env.H2BT_PARITY_BASE_URL.replace( /\/$/, '' );
const paths = process.env.H2BT_PARITY_PATHS.split( ',' ).filter( Boolean );
const widths = process.env.H2BT_PARITY_WIDTHS.split( ',' ).map( Number );
const storage = JSON.parse( process.env.H2BT_PARITY_STORAGE || '{}' );

const shotName = ( path, width ) =>
	( path.replace( /^\/|\/$/g, '' ).replace( /[^a-z0-9]+/gi, '-' ) || 'home' ) + '-' + width + '.png';

for ( const width of widths ) {
	for ( const path of paths ) {
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
			await expect( page ).toHaveScreenshot( shotName( path, width ), {
				fullPage: true,
				animations: 'disabled',
				caret: 'hide',
				maxDiffPixels: 0,
				timeout: 60000,
			} );
			await context.close();
		} );
	}
}
EOF

storage_json="$(python3 -c 'import json,sys; print(json.dumps(dict(a.split("=",1) for a in sys.argv[1:])))' "${storage[@]+"${storage[@]}"}")"
args=( playwright test --config "$work/playwright.config.js" )
[[ "$mode" == "baseline" ]] && args+=( --update-snapshots=all )

set +e
( cd "$repo" && H2BT_PARITY_BASE_URL="$base_url" H2BT_PARITY_PATHS="$paths" H2BT_PARITY_WIDTHS="$widths" H2BT_PARITY_STORAGE="$storage_json" ./node_modules/.bin/"${args[@]}" ) >"$work/last-run.log" 2>&1
status=$?
set -e

shots="$(find "$work/snapshots" -name '*.png' 2>/dev/null | wc -l | tr -d ' ')"
if [[ "$status" -eq 0 ]]; then
	echo "H2BT_PARITY_OK mode=$mode shots=$shots dir=$work/snapshots"
	exit 0
fi
sed 's/\x1b\[[0-9;]*m//g' "$work/last-run.log" | grep -E '✘|Error:|pixels? \(ratio|different' | head -40
echo "Diff images (expected / actual / diff) are under $work/results."
echo "H2BT_PARITY_FAIL mode=$mode shots=$shots log=$work/last-run.log"
exit 1
