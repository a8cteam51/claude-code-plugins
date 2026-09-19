# Changelog

## [1.0.0] - 2026-09-19

### Added
- Initial release.
- `vip-plugin-updates` skill: takes a folder of downloaded plugin zips and opens
  one pull request per plugin against a VIP repo that vendors its plugins in
  git, then hands back for the user to merge and test, and repeats the pass
  against the production branch.
- `scripts/detect_repo.sh` — works out the testing branch, production branch,
  plugins directory, PR label, production-branch guard workflows and process
  docs by reading the repo and GitHub. Nothing is configured per site, so it
  works on a repo it has never seen. Reads docs and workflows from the testing
  branch ref rather than the checkout, which may be sitting on production.
- `scripts/stage_updates.sh` — unpacks zips and copies loose folders into one
  clean staging directory: archive wrappers removed, `__MACOSX`/`.DS_Store`/
  `._*` stripped, duplicates and unpackable archives reported rather than
  guessed at. Layout is decided by where the `Plugin Name` header actually sits
  rather than by counting entries, so a wrapper directory shipped beside a
  stray `license.txt` and a flat plugin carrying an `includes/` directory are
  both read correctly. bash 3.2 compatible.
- The branch is the authority on what may be updated: a staged plugin with no
  counterpart tracked on the target branch is skipped rather than added, and
  "vendored" is decided by `git ls-files`, not by a directory existing on disk.
  Checkout leftovers from another branch are listed as ignored rather than
  mistaken for plugins. `open_plugin_pr.sh` enforces the same rule against the
  base branch and reports `skipped-not-on-branch`.
- `scripts/plugin_inventory.py` — reads plugin headers on a best-effort basis
  and falls back through version constants, `readme.txt` `Stable tag` and
  `composer.json`/`package.json` when the `Version:` header is a build
  placeholder or missing. Matches staged plugins to vendored ones by slug,
  slug-minus-version, `Plugin Name` or `Text Domain`, compares with a
  PHP-compatible `version_compare`, and flags downgrades, unvendored plugins,
  unreadable versions and updates that would delete files from the vendored
  copy.
- `scripts/open_plugin_pr.sh` — one plugin per run: branch off the remote base,
  replace the plugin directory, commit, push, open the PR, return to the
  starting branch. Versions are arguments rather than re-parsed, so a mangled
  header cannot break the run; a missing label is retried without it; an
  existing remote branch is skipped rather than clobbered; a failed
  `gh pr create` still leaves the commit pushed and says so. `--reuse-branch`
  commits onto the existing branch's tip rather than resetting it to the base.
- `references/troubleshooting.md` — unreadable version headers, slug
  mismatches, awkward zip layouts, `.gitignore` swallowing plugin files,
  vendored copies carrying local patches, `gh`/git failures, and recovering a
  half-finished run.
