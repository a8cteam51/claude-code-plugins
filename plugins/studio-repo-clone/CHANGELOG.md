# Changelog

## [1.1.0] - 2026-05-15

### Added
- Setup now asks whether to enable `WP_DEBUG_LOG`. When the user opts in, `scaffold.sh` runs `studio site set --debug-log --path <target>` after `studio site create`, exposed via a new `--debug-log` flag on the script.

### Fixed
- `scaffold.sh` no longer wipes the target directory when a Studio command fails. Previously a `studio site create` failure (Step 5) triggered the trap's `rm -rf` cleanup because `mutated_target` was still set, contradicting the documented "Studio failures leave files in place" behavior. The destructive-rollback window is now narrowly scoped to the `mv` itself — once the staged tree is moved into `$abs_target`, any subsequent failure (gitignore patch, `studio site create`, `studio site set --debug-log`) leaves the files alone so the user can fix the underlying issue and re-run the failing Studio command directly.

## [1.0.0] - 2026-05-13

### Added
- Initial release
- `/studio-repo-clone:init` command and natural-language skill for scaffolding a local WordPress Studio site whose `wp-content` is a cloned GitHub repo
- Deterministic `scaffold.sh` that downloads WordPress, SHA1-verifies the archive, clones the repo as `wp-content`, and creates a Studio site via the `studio` CLI (SQLite)
- Preflight `git ls-remote` check so private-repo auth failures surface before any filesystem work
- Automatic `.gitignore` patching for Studio-generated files (`/database`, `/db.php`, `/index.php`), anchored to the wp-content root so theme/plugin `index.php` files deeper in the tree are not affected
