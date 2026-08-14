# site-launch-comparison

Capture full-page **before/after screenshots of two versions of a website** and
build a self-contained, side-by-side HTML report you can open, scroll, and hand
to a client.

Say to Claude:

> We just re-themed the client's store. The old site is still at
> https://staging.example.com and the new one is live at https://www.example.com
> — grab before/after screenshots of the main pages and put them in one page I
> can send the client.

…and it proposes a page list for you to approve, captures both sites at desktop
and mobile, and hands back a single `comparison.html`.

Built for relaunches — re-themes, redesigns, replatforms — and equally useful
for routine staging-vs-production design QA. Stack-agnostic: WordPress /
WooCommerce, a static site, or anything else serving HTML.

## What it does

1. **Proposes a page list.** Intersects both sites' `sitemap.xml` and homepage
   nav, keeps only paths that return 200 on *both*, and ranks them so you get
   one of each template type — home, listing, product, article, conversion path
   — rather than fifteen blog posts. Shown for approval before anything slow
   happens.
2. **Captures every page full-height** at 1440px and 390px.
3. **Builds one HTML file** with a desktop/mobile toggle, independently
   scrolling before/after panels, and click-through to full-resolution PNGs.

Two things the report surfaces that are easy to miss by eye: pages served at
several URLs (`/shop/` and `/products/`, `/cart/` and `/checkout/` when empty)
are merged into a single row, and pages whose before and after are
pixel-identical get a badge — usually a page the migration skipped.

## Why not just a screenshot script

Four things reliably break hand-rolled runs, and handling them is most of the
value here:

- **Bot-check interstitials.** Plenty of hosts serve "Checking your browser…"
  to datacenter IPs. It clears after a few seconds, but a naive script captures
  the interstitial and reports success — a whole run of identical blank images
  that looks fine in the logs. Captures are validated for real content and
  plausible page height before being saved.
- **Shell time limits.** Agent shells often cap a call at a couple of minutes,
  and background processes don't survive between calls, so a long capture gets
  killed with nothing written. Capture is resumable and budget-limited.
- **No root.** `playwright install-deps` shells out to `sudo` and fails in
  sandboxes. Setup detects this and unpacks Chromium's libraries locally.
- **Overlays and lazy loading.** A cookie banner on one side and not the other
  makes a comparison unreadable, and lazy images render blank in a full-page
  shot. Both are handled.

## Requirements

- Python 3.9+, plus `playwright` and `pillow` — installed by the bundled setup
  script, which also fetches Chromium
- macOS, Linux, or WSL

Roughly 10–20 seconds per screenshot. A 14-page, two-viewport run takes about
15 minutes and produces 100–200 MB of PNGs, so keep the output out of git or
pass `--no-full`.

## Install

```bash
/plugin install site-launch-comparison@a8cteam51-claude-code-plugins
```

## Usage

Natural language is the intended path — describe the comparison and the skill
takes over. If you already know which pages you want, say so and it skips
discovery:

> Compare https://staging.example.com against https://www.example.com on
> `/`, `/shop/` and `/about/`. Desktop only.

### Running the scripts directly

The skill drives these for you, but they're ordinary CLI tools. From the skill
directory:

```bash
# 1. One-time browser setup (writes /tmp/browser-env.sh)
bash scripts/setup_browser.sh
source /tmp/browser-env.sh

# 2. Propose a page list
python3 scripts/discover_pages.py https://staging.example.com https://www.example.com \
  --limit 14 --out config.json

# 3. Capture (BUDGET=0 runs to completion; omit it in a timeout-capped shell)
BUDGET=0 bash scripts/capture_all.sh config.json

# 4. Build the report
python3 scripts/build_report.py config.json --dest ./report
open ./report/comparison.html
```

`examples/example-config.json` is a fully annotated config covering HTTP basic
auth, cookie injection, viewports, and pages whose URL changed between the two
sites.

## Troubleshooting

See [references/troubleshooting.md](skills/site-launch-comparison/references/troubleshooting.md)
for authentication on gated staging sites, hosts that never clear the bot
challenge, blank or short captures, very long pages, and comparing sites whose
URL structures don't line up.

## Known limits

- Page ranking during discovery is heuristic. It skips taxonomy archives and
  obvious legacy variants, but an unusually structured site may need the
  proposed list edited — which is why it's shown for approval first.
- Pre-scrolling stops at 45,000px; longer pages capture their top portion.
- Sites with A/B tests, rotating heroes or live counters will differ between
  the two captures for reasons unrelated to the redesign.
- If a host blocks the machine outright rather than challenging it, there's no
  workaround here by design.
