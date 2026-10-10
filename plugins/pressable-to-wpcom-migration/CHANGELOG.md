# Changelog

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
