---
name: site-launch-comparison
version: 1.0.0
description: Capture full-page before/after screenshots of two versions of a website and build a self-contained side-by-side HTML comparison report. Use this whenever someone wants to compare two sites or two versions of a site visually — re-themes, redesigns, replatforms, staging-vs-production checks, "screenshot these pages for me", "show me what changed", design QA before or after a launch, or building a visual record to share with stakeholders. Works for WooCommerce/WordPress and for any other stack, and handles bot-check interstitials, cookie banners, lazy-loaded images, and shell time limits that break naive screenshot scripts.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Site launch comparison

Produce a visual before/after record of a site change: full-page screenshots of
matching URLs on two hosts, side by side in one HTML page the user can open,
scroll, and hand to stakeholders.

Typical framing: **before** is the old site (staging, UAT, the previous theme),
**after** is the new one (production, the new theme). Nothing is
WordPress-specific — any two hosts serving comparable URLs work.

## Locate the skill directory first

Every command below runs a bundled script. Determine the directory containing
this `SKILL.md` file and store it as `SKILL_DIR` — the user's working directory
is their project, not this skill, so bare relative paths will not resolve:

```bash
SKILL_DIR="<absolute path to the directory holding this SKILL.md>"
```

## Why this needs a script and not just a browser

Four things reliably ruin hand-rolled screenshot runs, and the bundled scripts
already handle all of them. Knowing they exist saves you from rediscovering
them the hard way:

- **Bot-check interstitials.** Many sites serve a "Checking your browser…" page
  to datacenter IPs. It clears in a few seconds, but a naive script screenshots
  the interstitial and reports success. `capture.py` waits for real content and
  validates page height before saving.
- **Shell time limits.** Agent shells are often capped at ~3 minutes per call,
  and background processes do **not** survive between calls, so a long capture
  job gets killed with nothing saved. `capture.py` is resumable and
  budget-limited: run it repeatedly until it prints `REMAINING 0`.
- **No root.** `playwright install-deps` calls sudo and fails in sandboxes.
  `setup_browser.sh` unpacks the shared libraries into a local prefix instead.
- **Overlays and lazy loading.** A cookie banner or newsletter modal on one
  side and not the other makes the comparison unreadable; lazy images render
  blank in a full-page shot. `capture.py` suppresses common overlays and
  pre-scrolls the page.

## Workflow

### 1. Confirm scope before capturing

Capture is the slow part, so settle these first. Ask about anything the user
hasn't already specified — ideally in one round, not one question at a time:

- The two URLs, and which is before vs after.
- A short label for each side ("old theme" / "new theme", "v1" / "v2"), used in
  the report header. Optional but makes the output far more legible later.
- Whether either site needs credentials (staging often does) — see
  `$SKILL_DIR/references/troubleshooting.md` for auth setup.
- Whether they want anything beyond the auto-discovered page set.

### 2. Set up the browser

```bash
bash "$SKILL_DIR/scripts/setup_browser.sh"
```

Idempotent and self-verifying — it launches Chromium at the end and fails loudly
if something is missing. Takes a couple of minutes the first time, seconds after.
It detects the platform: on macOS a plain Playwright install is enough, on Linux
with sudo it installs system packages, and on a rootless Linux sandbox it unpacks
Chromium's shared libraries into a local prefix.

It writes `/tmp/browser-env.sh`; **source that in every later call**, since each
shell invocation may start fresh:

```bash
source /tmp/browser-env.sh
```

### 3. Discover pages and agree on the list

```bash
python3 "$SKILL_DIR/scripts/discover_pages.py" <BEFORE_URL> <AFTER_URL> \
  --limit 14 --out <workdir>/config.json
```

Put `config.json` somewhere your file-editing tools can reach — your working or
output directory, not `/tmp`. In many setups `/tmp` belongs to the shell sandbox
only, and you'll be stuck editing the config through shell heredocs.

Skip discovery entirely when the user already named the pages; hand-write the
config instead. Discovery is for "capture the important pages", not for
"capture these three".

This intersects sitemaps and homepage nav from both sites, keeps only URLs that
return 200 on both, and ranks them so you get one of each template type — home,
listing, product, article, conversion path — rather than fifteen blog posts.

Read the generated `config.json`, show the user the proposed page list in your
reply, and let them add or drop entries before you spend time capturing. The
stderr output includes other shared paths that weren't selected, which is useful
when they ask "what about X?".

If discovery finds little or no overlap, the URL structure probably changed
between the two sites. Don't guess — ask the user for the paths that correspond,
and note that pages can be paired manually by editing `config.json`.

Edit `config.json` freely. Its shape:

```json
{
  "project": "Acme Re-theme",
  "before": { "base": "https://staging.example.com", "label": "Before", "sublabel": "old-theme" },
  "after":  { "base": "https://example.com",         "label": "After",  "sublabel": "new-theme" },
  "viewports": [
    { "id": "desktop", "width": 1440, "height": 1000, "mobile": false },
    { "id": "mobile",  "width": 390,  "height": 844,  "mobile": true }
  ],
  "out": "/tmp/shots",
  "pages": [ { "slug": "01-home", "title": "Home", "path": "/" } ]
}
```

Both viewports are captured by default, and the report gets a desktop/mobile
toggle. Drop the mobile entry if the user only wants desktop — it roughly halves
the runtime.

To pair pages whose URLs differ between sites, give the page a `before_path`
alongside `path`; `path` is used for the after side. Everything else is the same.

A fully annotated config covering basic auth, cookies and mismatched URLs lives
at `$SKILL_DIR/examples/example-config.json`.

### 4. Capture, in a loop

```bash
source /tmp/browser-env.sh
BUDGET=90 python3 "$SKILL_DIR/scripts/capture.py" <workdir>/config.json
```

Each run captures what it can and exits cleanly before the shell timeout, then
prints how much is left. **Keep calling the same command until it prints
`REMAINING 0`.** A 14-page, two-viewport job is usually 6–10 runs; each shot
takes roughly 10–20 seconds.

`BUDGET` is seconds of capture work per run, and it needs headroom under the
shell's cap — the cap is often lower in practice than advertised (~135s where
180s is claimed), and a run that gets killed mid-screenshot wastes the whole
call. 90 is a safe default; lower it to 60 if you're seeing timeouts.

**If your shell has no timeout** (Claude Code on a normal machine, a local
terminal, CI), skip the manual loop entirely and let it run to completion:

```bash
BUDGET=0 bash "$SKILL_DIR/scripts/capture_all.sh" <workdir>/config.json
```

`BUDGET=0` means unlimited, and `capture_all.sh` re-invokes the capture until
nothing is left. Only fall back to calling `capture.py` once per shell call when
the environment actually caps call duration.

Reading the output as it goes:

- `OK` lines show page height and file size — a plausible height (thousands of
  pixels) means a real render.
- `RETRY` / `FAIL` name the page and reason. A page that fails twice is usually
  genuinely different, not flaky — check it manually before dropping it.
- `WARM` failures are usually harmless; the per-page challenge wait still runs.

Don't run this in the background hoping to poll it later. The process will not
survive to the next call.

### 5. Build the report

```bash
python3 "$SKILL_DIR/scripts/build_report.py" <workdir>/config.json --dest <output-folder>
```

Writes `comparison.html` plus `full/` (full-resolution PNGs) and `web/`
(downscaled JPEGs the HTML actually loads, so the page opens fast while clicking
through to full quality still works).

Add `--no-full` when size matters more than full-resolution click-through; it
drops the PNGs and omits the link rather than leaving it dangling. Don't
hand-delete `full/` after the fact — that's how you ship a report whose
click-throughs all 404.

Two things it surfaces that are easy to miss by eye:

- **Duplicate URLs get merged.** Sites often serve one page at several paths
  (`/shop/` and `/products/`, `/cart/` and `/checkout/` when empty). Identical
  captures collapse into a single row listing every URL it covers.
- **Identical before/after pages get a badge.** Usually that means the migration
  skipped the page — worth raising with the user rather than leaving buried.

### 6. Verify before handing it over

Screenshot jobs fail quietly, so confirm rather than assume. Open the report in
headless Chromium and check that every image loaded:

```bash
source /tmp/browser-env.sh
python3 - <<'PY'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_context(viewport={"width":1500,"height":1100}).new_page()
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("file://<ABS_PATH>/comparison.html", wait_until="load"); pg.wait_for_timeout(3500)
    print("images:", pg.evaluate("document.images.length"),
          "broken:", pg.evaluate("[...document.images].filter(i=>i.complete&&i.naturalWidth===0).length"),
          "rows:", pg.evaluate("document.querySelectorAll('section.cmp').length"))
    print("errors:", errs[:3])
    pg.screenshot(path="/tmp/report-preview.png")
    b.close()
PY
```

Broken should be 0. Then actually **look** at `/tmp/report-preview.png` and at a
couple of the captures — an image can load fine and still be a blank hero or a
half-rendered page. This catch step is worth the minute it costs.

Finally, tell the user the total size and whether the destination is inside a git
repo. These folders run to 100 MB+, and quietly adding that to a repo is the kind
of thing people would rather have been warned about. Suggest gitignoring `full/`
if so.

## Reporting back

Present `comparison.html` and keep the summary short: how many page pairs and
viewports, then anything genuinely surprising — pages that came out identical,
pages that had to be dropped, redirects that collapsed two URLs into one. Skip
the play-by-play; the report speaks for itself.

## When things go wrong

See `$SKILL_DIR/references/troubleshooting.md` for authentication (basic auth,
cookies, staging passwords), sites that never clear the bot challenge, blank or
short captures, very long pages, region blocks, and comparing sites whose URLs
don't line up.
