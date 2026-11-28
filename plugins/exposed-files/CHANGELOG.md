# Changelog

## [1.0.0] - 2026-11-28

### Added
- Initial release.
- `exposed-files` skill: runs the team51 CLI's `site:scan-exposed-files` on one site
  or the fleet, explains the risk of each public file, reports it, and guides the
  cleanup with `site:quarantine-exposed-files`, the content check and escalation.
