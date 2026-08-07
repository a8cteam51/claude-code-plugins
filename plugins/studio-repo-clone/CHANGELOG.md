# Changelog

## [1.3.0] - 2026-08-07

### Added

- `site-from-host` skill: build a local Studio mirror of a hosted Pressable or
  WPCOM site — repo as wp-content via `scaffold.sh`, plugins and (optionally) the
  database pulled with the team51 CLI (`*:download-site-plugins` /
  `*:download-site-database`), a `<name>.local` domain, BE Media from Production
  pointed at the source site for missing uploads, and a known local admin login.
- Six supporting scripts under `scripts/`: `pull-site-plugins.sh` (Pressable-first
  host detection), `merge-plugins.sh` (repo-tracked plugins win),
  `set-local-domain.sh`, `setup-media-fallback.sh`, `pull-database.sh` (imports via
  `studio import`, rewrites the source hostname, reactivates plugins the import
  deactivated — notably safety-net), and `ensure-admin-user.sh`.

## [1.2.0] - 2026-05-20

### Added
- Both setup flows now install and activate the [`a8cteam51/safety-net`](https://github.com/a8cteam51/safety-net) plugin into `wp-content/plugins/safety-net` after the rest of the setup completes, so fresh clones of production-derived `wp-content` can't accidentally email real users from a developer's laptop. The latest release tag is resolved dynamically from `https://api.github.com/repos/a8cteam51/safety-net/releases/latest` at runtime (no hardcoded version). Activation goes through `studio wp --path <target> plugin activate safety-net`. The install lives in a shared helper at `scripts/install-safety-net.sh` invoked by both `scaffold.sh` and `clone-into-existing-site.sh`. The step is idempotent (skips download if `plugins/safety-net/` already exists) and non-fatal (a failure prints a warning, the rest of the setup is preserved, and the user can re-run the helper directly).
- New `clone-into-existing-site` skill and accompanying `scripts/clone-into-existing-site.sh` for converting an already-running local Studio site's `wp-content` into a git clone without losing local runtime data. The script renames the existing `wp-content` to `wp-content-temp`, clones the repo into a fresh `wp-content`, then moves `uploads/`, `database/`, `db.php`, and `mu-plugins/sqlite-database-integration/` back from the temp copy as whole units. For `plugins/` and `themes/`, the script moves each child individually so plugins/themes committed to the repo aren't blown away wholesale — only per-child name conflicts are overwritten (local copies win). `wp-content-temp` is left in place for the user to inspect and delete; the script does not remove it. The cloned repo's `.gitignore` is patched with the Studio-generated runtime entries (`/database`, `/db.php`, `/index.php`, `/uploads`, `/mu-plugins/sqlite-database-integration`). On clone failure after the rename, `wp-content` is restored from `wp-content-temp` automatically.

### Changed
- Renamed the `scaffold` skill to `clone-new-site` and updated its `name:` frontmatter and description to disambiguate from the new `clone-into-existing-site` skill. The marketplace skill path now points to `./skills/clone-new-site`. The underlying `scripts/scaffold.sh` and `/studio-repo-clone:init` command are unchanged.

## [1.1.0] - 2026-05-15

### Added
- Setup now asks whether to enable `WP_DEBUG_LOG`. When the user opts in, `scaffold.sh` runs `studio site set --debug-log --path <target>` after `studio site create`, exposed via a new `--debug-log` flag on the script.

### Changed
- Target-directory prompt now offers Studio's site directory as the recommended option. The orchestrator infers the user's effective Studio base by parsing `studio site list --format json` with `jq` (most common parent of existing site paths, space-safe via `xargs -I {}`), falling back to `$HOME/Studio` (Studio's documented default) when no sites exist, the CLI is unavailable, or `jq` is not installed. The previous `<cwd>/<project-name>` and `~/Sites/<project-name>` options remain available.

### Fixed
- `scaffold.sh` no longer wipes the target directory when a Studio command fails. Previously a `studio site create` failure (Step 5) triggered the trap's `rm -rf` cleanup because `mutated_target` was still set, contradicting the documented "Studio failures leave files in place" behavior. The destructive-rollback window is now narrowly scoped to the `mv` itself — once the staged tree is moved into `$abs_target`, any subsequent failure (gitignore patch, `studio site create`, `studio site set --debug-log`) leaves the files alone so the user can fix the underlying issue and re-run the failing Studio command directly.

## [1.0.0] - 2026-05-13

### Added
- Initial release
- `/studio-repo-clone:init` command and natural-language skill for scaffolding a local WordPress Studio site whose `wp-content` is a cloned GitHub repo
- Deterministic `scaffold.sh` that downloads WordPress, SHA1-verifies the archive, clones the repo as `wp-content`, and creates a Studio site via the `studio` CLI (SQLite)
- Preflight `git ls-remote` check so private-repo auth failures surface before any filesystem work
- Automatic `.gitignore` patching for Studio-generated files (`/database`, `/db.php`, `/index.php`), anchored to the wp-content root so theme/plugin `index.php` files deeper in the tree are not affected
