# Changelog

## [0.1.0] - 2026-11-17

### Added
- From the first rehearsal (thinkbiggerinnovation.com): pulls run in the foreground, because each Pressable WP-CLI call
  runs in its own container and a background process dies with it. The pull source is the `?reprint-api` address the
  Reprint Server screen shows. `place` skips symlinks (Atomic links Jetpack, Akismet, Gutenberg and page-optimize into
  wp-content, and Reprint follows them) and lists them in `symlinks_skipped`. A database pull flushes the object cache,
  which otherwise served the pre-import options. `compare_sites.py` treats WordPress.com's mu-plugins and REST
  namespaces as expected, and Jetpack's offline-only gaps as notes while quarantined. `db_diff.php` treats `\/` and `/`
  as equal, because Reprint's URL rewrite unescapes JSON slashes.
- From the first audit (thinkbiggerinnovation.com): the audit runs WP-CLI calls to the Atomic source one at a time
  (two at once failed to connect), checks drift with `file_hashes.php` against the deploy branch, finds the connected
  WordPress.com deployment with `wpcom:site:deployment:webhook:list`, and records the staging blog from the repo's
  custom properties. A related WordPress.com site the audit can answer for carries its own severity, and
  `decom.wpcom-sites` retires the old blogs.
- `scripts/zone_snapshot.py`: WordPress.com's DNS screen has no export, so the zone is rebuilt from a list of names
  (from screenshots) with every value queried from the name server, and compared again after the domain is detached
  (`--diff`). Handles delegations, wildcards and long TXT values. thinkbiggerinnovation.com's zone has 76 records.
- PHP stays at Pressable's default when the partner agrees; the Atlantis key copy is skipped when the source has no
  Atlantis messages (the only thing it encrypts), and uses `--anchor`/`--placement=before` when it is needed.
  `rehearse.users` re-syncs the concierge password after the import replaces the users table.
- Initial draft, for thinkbiggerinnovation.com (T51ENG-2541). Not yet run end to end.
- `wpcom-to-pressable-audit`: read-only audit of a WordPress.com Atomic site that writes a report and a per-site runbook.
- `wpcom-to-pressable-run`: walks the runbook, records progress and decisions.
- `wpcom-to-pressable-verify`: site comparison, parity, database diff, URL crawl, front end, stragglers.
- `scripts/reprint_remote.php`: runs the Reprint client on the Pressable site through WP-CLI (probe, background test,
  setup and key generation, resumable file and database pulls, placing wp-content, cleanup). Keeps everything in a work
  directory outside the web root and never prints the database password or the private key.
- `scripts/checks.py` and `scripts/runbook.py` for this direction: WordPress.com platform code, plugins Atomic manages,
  the new Jetpack blog ID, subscribers, stats only where the module was on, paid Jetpack products, a freeze only when the
  activity log says the site is busy, WordPress.com-hosted DNS and the `atomic-domain` TXT check, WordPress.com
  deployments, the Pressable allowlist and GitHub integration.
- Copied from `pressable-to-wpcom-migration` unchanged: `wp_eval.sh`, `site_audit.php`, `web_root.php`, `parity.php`,
  `compare_parity.py`, `url_check.py`, `mu_plugin.sh`, `mu_plugin.php`, `dns_audit.py`, `dns_compare.py`,
  `wpcom_facts.py`, `db_diff.php`, `file_hashes.php`, `frontend/`.
- Adapted from it: `db_diff.py` (WordPress.com source, Pressable target, Pressable options as platform rows),
  `compare_sites.py` (WordPress.com leftovers on the target, the copied Jetpack connection), `state.py` (no space
  publishing; records the Pressable ID), `build_audit.py` (no HTML report).
- `assets/t51-migration-freeze.php` acts only on Atomic. `assets/t51-migration-quarantine.php` also keeps Jetpack in
  offline mode, so the copied connection cannot sync into the live blog ID.
