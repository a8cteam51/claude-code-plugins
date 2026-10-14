# Changelog

## [Unreleased]

### Changed
- VideoPress content and Jetpack plan gaps are reported as work for a person,
  like WooPayments. They no longer hold a site or count as decisions.
- Stats merge and subscriber migration are steps on every site.
- The staging site is its own last phase, after the DNS zone move, made with
  `team51 wpcom:clone-site`.
- Scope is the migration only. The migrated site stays Team 51-managed, so
  Atlantis is kept and checked, not removed, and the handover phase is gone.
- Deleting the Pressable site is gated on stats, subscribers, WooPayments and
  VideoPress being finished.

- The source step installs the Reprint exporter plugin and adds the public
  key the Migration Assistant shows. Jetpack's built-in exporter is not used.
- The site name passed to `wpcom:create-site` has no dashes, and the runbook
  gives the right temporary address.

- The Jetpack check no longer stops on the source's blog ID in the target's
  local `jetpack_options`; that is left by the copy. It checks connection
  health and the `out-of-sync-posts` sticker instead, and forbids
  disconnecting or reconnecting Jetpack. The parity and site comparisons
  report the ID as a note, not a failure.

- The copy runs once, inside the cutover window with the source frozen. The
  rehearsal sync, the final re-sync and the re-sync survival check are gone:
  a Migration Assistant run cannot be repeated against the same target. The
  runbook phases are now prepare, platform items, get ready (TTL, exporter,
  monitoring), then the window: freeze and copy, check the copy, go live.

### Added
- `REPORT.html`: the audit and the runbook as one self-contained page for a
  browser. Verdict, what the job involves (the cutover window step by step,
  what takes calendar time, the access and tools needed, what makes the site
  more than a standard migration), findings to expand, and the runbook with
  placeholders highlighted until the new site exists. Light and dark themes,
  readable on a phone, prints with everything expanded.
- `scripts/db_diff.py` (with `db_diff.php`): read-only row-level diff of every
  table, source against target, fingerprinted in SQL in buckets so it takes
  about six WP-CLI calls. Treats the site's host names as equal, separates
  gaps (data on the source missing or different on the target) from platform
  and target-only differences, and writes the gap rows as REPLACE statements
  for review. It is the go-live gate (`verify.db-diff`).
- `scripts/frontend/`: a front-end check. Samples pages from the source's
  sitemaps, snapshots them on both sides in headless Chrome (desktop and
  mobile, logged out, no proxy) and compares status, console errors, failed
  requests, assets, fonts, computed styles, layout, broken images and
  screenshots. Runbook steps after the first sync, before the freeze
  (baseline) and after cutover. Needs Node 20+, Google Chrome and
  `npm ci --prefix scripts/frontend`.
- A step after every sync to confirm in Blog RC that the WordPress.com cleanup
  finished, re-queue it if not, and check it did not remove the connection
  owner.
- A Jetpack connection repair on the new site after each sync, in the Jetpack
  debug tool: Restore User Connection, then Schedule Sync under Full Sync.
- Steps and findings for Team 51 monitoring: settings rows before and after
  cutover, a check that the new site reports the production domain before the
  old Jetpack connection goes, and a check that the new blog ID is picked up.
- Report notes on PHP fatals scanning and Poseidon site cloning, which do not
  cover WordPress.com sites, and on `plugin-autoupdate-filter`.

## [0.1.0] - 2026-10-10

### Added
- Initial draft for evaluation. Not yet used for a real migration.
- `migration-audit` skill: read-only audit of a Pressable site that writes a
  report, a manifest and a per-site runbook.
- `migration-run` skill: walks the runbook, records progress and decisions.
- `migration-verify` skill: parity, site comparison, URL crawl, stragglers.
- `migration-dns` skill: registrar and zone audit, cutover, zone comparison.
- `scripts/checks.py`: the check catalogue. `scripts/runbook.py`: the steps.
- `scripts/wpcom_facts.py`: subscriber count from the public WordPress.com API.
- `scripts/p2_extract.py`: pulls migration-relevant sentences out of project P2 posts.
- `assets/`: quarantine (target) and freeze (source) mu-plugins. Runtime
  filters only; neither writes to the database.
