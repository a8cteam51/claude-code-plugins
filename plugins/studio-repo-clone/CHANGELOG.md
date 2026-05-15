# Changelog

## [1.1.0] - 2026-05-15

### Added
- Setup now asks whether to enable `WP_DEBUG_LOG`. When the user opts in, `scaffold.sh` runs `studio site set --debug-log --path <target>` after `studio site create`, exposed via a new `--debug-log` flag on the script.

### Changed
- `scaffold.sh` no longer destroys the target directory if a post-create Studio command (e.g. `studio site set --debug-log`) fails. The destructive-rollback window now ends at successful `studio site create`, matching the documented "Studio failures leave files in place" behavior.

## [1.0.0] - 2026-05-13

### Added
- Initial release
- `/studio-repo-clone:init` command and natural-language skill for scaffolding a local WordPress Studio site whose `wp-content` is a cloned GitHub repo
- Deterministic `scaffold.sh` that downloads WordPress, SHA1-verifies the archive, clones the repo as `wp-content`, and creates a Studio site via the `studio` CLI (SQLite)
- Preflight `git ls-remote` check so private-repo auth failures surface before any filesystem work
- Automatic `.gitignore` patching for Studio-generated files (`/database`, `/db.php`, `/index.php`), anchored to the wp-content root so theme/plugin `index.php` files deeper in the tree are not affected
