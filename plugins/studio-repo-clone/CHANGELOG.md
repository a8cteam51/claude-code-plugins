# Changelog

## [1.1.0] - 2026-05-15

### Changed
- Target-directory prompt now offers Studio's site directory as the recommended option. The orchestrator infers the user's effective Studio base by parsing `studio site list --format json` (most common parent of existing site paths), falling back to `$HOME/Studio` (Studio's documented default) when no sites exist or the CLI is unavailable. The previous `<cwd>/<project-name>` and `~/Sites/<project-name>` options remain available.

## [1.0.0] - 2026-05-13

### Added
- Initial release
- `/studio-repo-clone:init` command and natural-language skill for scaffolding a local WordPress Studio site whose `wp-content` is a cloned GitHub repo
- Deterministic `scaffold.sh` that downloads WordPress, SHA1-verifies the archive, clones the repo as `wp-content`, and creates a Studio site via the `studio` CLI (SQLite)
- Preflight `git ls-remote` check so private-repo auth failures surface before any filesystem work
- Automatic `.gitignore` patching for Studio-generated files (`/database`, `/db.php`, `/index.php`), anchored to the wp-content root so theme/plugin `index.php` files deeper in the tree are not affected
