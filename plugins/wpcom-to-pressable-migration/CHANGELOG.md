# Changelog

## [0.1.0] - 2026-11-17

### Added
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
  `wpcom_facts.py`, `db_diff.php`, `frontend/`.
- Adapted from it: `db_diff.py` (WordPress.com source, Pressable target, Pressable options as platform rows),
  `compare_sites.py` (WordPress.com leftovers on the target, the copied Jetpack connection), `state.py` (no space
  publishing; records the Pressable ID), `build_audit.py` (no HTML report).
- `assets/t51-migration-freeze.php` acts only on Atomic. `assets/t51-migration-quarantine.php` also keeps Jetpack in
  offline mode, so the copied connection cannot sync into the live blog ID.
