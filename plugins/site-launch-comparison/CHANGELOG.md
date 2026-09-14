# Changelog

## [1.0.0] - 2026-08-14

### Added
- Initial release.
- `site-launch-comparison` skill (natural language) for capturing full-page
  before/after screenshots of two versions of a website and assembling a
  self-contained side-by-side HTML report.
- `scripts/setup_browser.sh` — cross-platform headless Chromium install.
  Detects the platform: a plain Playwright install on macOS, `install-deps`
  where sudo works, and on a rootless Linux sandbox it downloads and unpacks
  Chromium's shared libraries into a local prefix rather than calling sudo.
  Self-verifying — launches Chromium at the end and fails loudly.
- `scripts/discover_pages.py` — intersects both sites' sitemaps and homepage
  nav, keeps only paths returning 200 on both, and ranks them so the proposed
  set covers one of each template type (home, listing, product, article,
  conversion path) instead of many near-duplicates. Demotes taxonomy archives
  and legacy variants.
- `scripts/capture.py` — resumable, budget-limited full-page capture at desktop
  and mobile viewports. Waits out bot-check interstitials and validates page
  height before saving, so a challenge page is never stored as a screenshot.
  Suppresses cookie banners, chat widgets and modals, and pre-scrolls each page
  so lazy-loaded images render. Supports HTTP basic auth, cookie injection, and
  pages whose URL differs between the two sites via `before_path`.
- `scripts/capture_all.sh` — loops `capture.py` until nothing is outstanding,
  for shells with no call timeout.
- `scripts/build_report.py` — assembles `comparison.html` with a desktop/mobile
  toggle, independently scrolling panels, and click-through to full-resolution
  PNGs. Merges pages served at several URLs into one row and flags pages whose
  before and after are pixel-identical. `--no-full` omits the PNGs and the
  click-through link rather than leaving it dangling.
- `references/troubleshooting.md` — authentication, hosts that never clear the
  bot challenge, blank or short captures, very long pages, mismatched URL
  structures, and output size.
- `examples/example-config.json` — annotated configuration.
