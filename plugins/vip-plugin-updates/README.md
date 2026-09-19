# vip-plugin-updates

Open **one pull request per plugin** against a WordPress VIP repo that vendors
its plugins in git, from a folder of zips you downloaded.

Say to Claude:

> The new plugin zips for the swag store are in ~/Downloads/store-plugins —
> open the update PRs against develop.

…and it unpacks them, compares each against the vendored copy, shows you what it
plans to do, then branches, commits, pushes and opens a PR per plugin.

## Why this exists

VIP sites deploy from a repository, and on these repos every plugin is committed
— updating one means committing its new files. VIP's dashboard can generate
those PRs, but only for repos inside the `wpcomvip` organisation. Repos owned
elsewhere (`Automattic/store.a8c.com`, `Automattic/mercantile.wordpress.org`)
have to do it by hand, every month, for a dozen plugins at a time.

## The split

**You**: download the zips (most are premium — WooCommerce.com and vendor
logins), drop them in a folder, then merge the PRs and test the site.

**Claude**: unzip, match each plugin to its vendored copy, compare versions, swap
the files, branch, commit, push, open the PRs, and sort out whatever is
malformed.

## The rule that matters

**The branch decides what gets updated, not the folder of zips.** The zips are
candidates. Whatever the target branch already vendors is the list. Branches
legitimately carry different plugin sets, so the same folder produces different
work against the testing branch and production — and nothing gets added to a
branch that does not already have it.

## The flow

1. Drop the zips in a folder.
2. Claude reads the repo — testing branch, production branch, plugins directory,
   PR label, any workflow guarding production — and reads the repo's own process
   docs, which win over the skill's defaults.
3. Claude stages and inventories everything, and shows you the plan: plugin,
   old → new, action. The branch decides the list — a zip with no counterpart
   tracked on that branch is skipped, never added. Downgrades, unreadable
   versions and updates that would delete files stop for a decision.
4. On your yes, one PR per plugin against the testing branch.
5. **You** merge and test the staging site.
6. Claude runs the production pass — per-plugin PRs against the production
   branch, or a single promotion PR where the repo's guard workflow requires it.
7. **You** merge and check production.

## What it handles that a script does not

- `Version: @@VERSION@@` and other unreplaced build placeholders — falls back to
  version constants, `readme.txt`'s `Stable tag`, `composer.json`, the zip name,
  and asks rather than guessing when none of them agree.
- Zips that unpack to `slug-1.2.3/`, to a flat pile of files, or to a wrapper
  directory, plus the `__MACOSX` and `.DS_Store` debris macOS adds.
- Staged folder names that do not match the vendored slug — matched by slug,
  `Plugin Name` or `Text Domain`.
- Vendored copies someone patched by hand: the update would delete those files,
  so it says which files and which commits before anything is overwritten.
- Plugins the branch does not carry. Vendored means **git tracks it on that
  branch**, not that a directory exists — a checkout of another branch leaves
  directories behind, and `ls` then lies about what the branch contains. Those
  are skipped, not offered as new installs: adding a plugin to a site is a
  different decision, usually with a VIP code review behind it.
- Downgrades.
- Repos it has never seen: branches, plugins directory, label and guards are all
  read from the repo, not configured here.

## Requirements

- `git`, `rsync`, `unzip`, `python3`
- `gh`, authenticated (`gh auth status`), with push access to the repo
- A local working copy of the target repo

## Not in scope

Downloading the plugins (they are behind vendor logins), merging pull requests,
and testing the site. Those stay with you on purpose.
