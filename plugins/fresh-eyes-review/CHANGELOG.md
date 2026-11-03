# Changelog

## [1.0.0] - 2026-10-23

### Added
- Initial release.
- `fresh-eyes-review` skill (natural language) for re-examining a change made
  earlier in the session: re-reads the actual diff, audits callers of anything
  whose contract changed, verifies guessed names and shapes against ground
  truth, checks the change is additive, re-checks authorization boundaries and
  edge cases, confirms side effects and test coverage, then fixes what it finds
  and reports found-and-fixed, needs-a-decision and checked-clean separately.
