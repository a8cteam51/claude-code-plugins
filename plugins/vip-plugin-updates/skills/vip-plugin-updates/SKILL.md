---
name: vip-plugin-updates
version: 1.0.0
description: Turn a folder of downloaded WordPress plugin zips into one pull request per plugin against a VIP repo that vendors its plugins in git. Use this whenever someone wants to update the plugins on a VIP-hosted site whose plugin updates have to go through the repository - "update the plugins on store.a8c.com", "open the plugin update PRs", "I dropped the new plugin zips in this folder", "run the monthly plugin updates", "promote the plugin updates to production" - especially where the VIP dashboard cannot generate the PRs because the repo is not in the wpcomvip organisation. Handles premium/marketplace plugins, unreadable version headers, downgrades, and plugins that are not vendored yet.
argument-hint: "[repo path] [folder of plugin zips]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# VIP plugin updates

VIP sites deploy from a repository, and on these repos every plugin is vendored
in git. Updating a plugin means committing its new files - there is no other
mechanism. The VIP dashboard's plugin-update PR generator only works for repos
inside the `wpcomvip` organisation, so on repos owned elsewhere (for example
`Automattic/store.a8c.com`) that job is done here instead.

**The division of labour.** The person downloads the plugin zips - most are
premium, behind a WooCommerce.com or vendor login - and drops them in a folder.
They also merge the pull requests and test the site. Everything between those
two points is yours: unpack, compare versions, swap the files, branch, commit,
push, open one pull request per plugin, and sort out whatever is malformed.

**One pull request per plugin.** Never batch them together unless explicitly
asked. A plugin that breaks the site is then one revert, not an unpicking job.

**The branch decides what gets updated, not the drop folder.** The zips are
candidates; the list of plugins is whatever the target branch already carries.
A staged plugin the branch does not track is skipped - not added, not offered as
a new install. Branches legitimately carry different plugin sets, so the same
drop folder produces different work against the testing branch and production.

"Already there" means **git tracks files for it on that branch**, not that a
directory of that name exists on disk. A checkout of another branch leaves
directories behind - on `store.a8c.com`, `plugins/redirection/` sits on disk
while on `develop` holding nothing but a stray `.DS_Store`, because the plugin
lives on `master` only. The tooling asks git; so should you.

## What you need before starting

1. **The drop folder** - zips and/or already-unpacked plugin folders. Ask for
   the path if it was not given.
2. **A local working copy of the repo.** Ask for the path, or find it (commonly
   `~/GitHub/<repo-name>`). Do not clone into a temp directory without asking -
   the user may have local work in theirs.
3. **Which pass this is** - the testing branch (first pass) or production
   (second pass, after they have merged and tested). Default to the testing
   branch unless the branch is named or the drop folder holds a run summary from
   an earlier pass.

`gh` must be authenticated (`gh auth status`).

## Step 1 - Read the repo, do not assume it

```bash
scripts/detect_repo.sh --repo-path <repo> --format text
```

This reports the testing branch, the production branch, where plugins are
vendored, which label plugin-update PRs carry, any workflow guarding the
production branch, and whether the working tree carries uncommitted changes. Nothing is hardcoded
per site, so it works on a repo you have never seen.

Then **read the repo's own process docs** if it has any (the script lists them
under `Process docs`, typically `docs/plugin-updates.md`,
`docs/branches-and-deploys.md`, `readme.md`, `CLAUDE.md`, `AGENTS.md`). Where
the repo's documented process differs from this skill, **the repo wins** - say so
and follow it. Repos change their release flow; this skill is a default, not an
authority.

Two things to stop on:

- **Uncommitted tracked changes.** Report them (`git status --short`) and ask
  before doing anything. Never stash or discard someone's work. Untracked files
  elsewhere in the repo are fine and do not block a run - only untracked files
  *inside a plugin directory being updated* do, because they would be swept into
  that plugin's commit.
- **A guard workflow on the production branch.** If one exists, read it. A
  common pattern is a required check that only lets the testing branch open PRs
  into production - there, per-plugin production PRs will fail CI, and the
  second pass is a single promotion PR from the testing branch instead. Tell the
  user what the guard requires rather than working around it.

## Step 2 - Stage the drop folder

```bash
scripts/stage_updates.sh --source <drop-folder> [--force]
```

Unpacks every zip and copies every loose folder into `<drop-folder>/.staged`,
one clean directory per plugin: archive wrappers removed, `__MACOSX`,
`.DS_Store` and `._*` stripped, flat archives (files at the zip root) given a
slug from the archive name. `--force` replaces a previous staging run.

Read the `WARN` lines. Anything it could not unpack needs you, not another run.

## Step 3 - Inventory and compare

First put the working copy on the branch you are targeting. The inventory reads
the vendored plugins from the working tree, so comparing against the wrong
branch produces wrong "old" versions - and those go in the PR titles:

```bash
git -C <repo> fetch origin
git -C <repo> checkout <base-branch>
git -C <repo> pull --ff-only
```

```bash
scripts/plugin_inventory.py --staged <drop-folder>/.staged \
  --repo-plugins <repo>/plugins --format text
```

For every staged plugin it reports the vendored version, the new version, and a
status. Use `--format json` when you want the full record (match method, version
sources, per-plugin notes, files the update would delete).

Version comparison follows PHP's `version_compare`, so `1.10 > 1.9` and
`2.0.0-rc.1 < 2.0.0` behave the way WordPress does.

Statuses, and what each one means for you:

| Status | Meaning | Default action |
| --- | --- | --- |
| `upgrade` | New version is higher | Open a PR |
| `same` | Already at this version | Skip silently |
| `downgrade` | New version is **lower** | Stop, ask - see below |
| `not-on-branch` | Git tracks no such plugin on this branch | **Skip it.** Do not add it, and do not ask whether to |
| `unknown-new-version` | Could not read the new version | Resolve it yourself - see below |
| `unknown-old-version` | Could not read the vendored version | Resolve it yourself |
| `unknown-both-versions` | Neither readable | Resolve, or hand back |

`not-on-branch` is a skip, not a question. Report it in the summary - "X was in
the folder but is not on this branch, skipped" - and move on. Someone routinely
downloads a few more zips than the branch needs, and a plugin that is on
production but not on the testing branch (or the reverse) is ordinary. Adding a
plugin to a site is a different job with a different decision behind it, usually
a VIP code review; it is not part of this workflow. `open_plugin_pr.sh` refuses
it as well, and its `--allow-new-plugin` flag exists only for a human who has
explicitly asked for that - never reach for it on your own.

The inventory also lists directories that are on disk but untracked on this
branch, under "On disk but untracked here, ignored". Those are checkout
leftovers. Mention them once so the user can clean them up; never treat one as a
vendored plugin.

A line prefixed `!` needs review even when the status looks fine - most often
because the update would **delete files that exist in the vendored copy**. Check
those before copying:

```bash
git -C <repo> log --oneline -8 -- plugins/<slug>
```

Commits there that are not plugin updates mean someone patched the vendored copy
by hand. Overwriting silently drops that patch. Surface it, name the files and
the commits, and ask - do not re-apply a patch on your own initiative.

## Step 4 - Agree the plan before touching git

Show a short table: plugin, old → new, action, and anything unresolved. Include
the skips so the list is complete. Then get a yes. A dry run makes the branch
names concrete if that helps:

```bash
scripts/open_plugin_pr.sh --repo-path <repo> --base-branch <branch> \
  --slug <slug> --src <staged>/<slug> --new-version <ver> --old-version <ver> \
  --name "<Plugin Name>" --dry-run
```

## Step 5 - One pull request per plugin

For each approved plugin, run once:

```bash
scripts/open_plugin_pr.sh \
  --repo-path   <repo> \
  --base-branch <testing-branch> \
  --slug        <vendored-slug> \
  --src         <drop-folder>/.staged/<staged-slug> \
  --name        "<Plugin Name>" \
  --old-version <old> --new-version <new> \
  --plugins-dir <plugins-dir-from-step-1> \
  --label       "<label-from-step-1>"
```

Each run branches off the remote base branch, replaces
`<plugins-dir>/<slug>/` wholesale (`rsync --delete`, so files dropped by the new
release are dropped here too), commits, pushes, opens the PR, and returns you to
the branch you started on. Branch name defaults to
`update/<slug>-<version>-<base>`. Versions are arguments, not something the
script re-parses, so a plugin with a mangled header is a value you supply rather
than a crash.

It prints `RESULT <status> <slug> <branch> <url>`:

- `created` - done.
- `skipped-branch-exists` - the branch is already on the remote. Check whether
  that PR already covers this update before doing anything else; pass
  `--reuse-branch` only if you are deliberately adding to an existing branch -
  it commits onto that branch's tip rather than rebuilding it from the base.
- `skipped-no-changes` - the files are identical to the base branch. Usually
  means it is already applied; confirm and move on.
- `pushed-no-pr` - the commit is pushed but `gh pr create` failed. The work is
  safe; open the PR with `gh pr create` and report what failed.
- `dry-run` - nothing happened.

Run them one at a time and read each RESULT. If one fails, keep going with the
rest and report the failure at the end - a single bad plugin must not strand the
batch.

## Step 6 - Hand back, and stop

You do not merge. You do not test the site. Post a summary:

- A table of PRs opened, with links, old → new versions.
- Anything skipped, and why.
- Anything still unresolved and needing a decision.
- The exact next step: merge these, deploy lands on the testing site, test it,
  then come back for the production pass.

Write the same summary to `<drop-folder>/update-run.md` (append, do not
overwrite) so the second pass has the history. Keep the `.staged` folder - the
production pass reuses it.

## Step 7 - The production pass

Only after the user confirms the testing site is good. Re-check the repo's
process first (Step 1), because this is where repos differ most:

- **Per-plugin production PRs** (the common case on repos with no guard, such as
  `store.a8c.com`): repeat Step 5 with `--base-branch <production-branch>`.
  Branch names pick up the base branch, so they will not collide with the
  testing ones. Check out the production branch and re-run the inventory before
  opening anything (Step 3) - do not reuse the testing pass's results. The two
  branches carry different plugin sets and different versions, so a plugin
  skipped as `same` or `not-on-branch` on the testing pass can be a real update
  here, and vice versa.
- **Promotion PR** (repos whose guard workflow requires it): open a single PR
  from the testing branch into production, for example
  `gh pr create --base <prod> --head <testing> --title "Release: <testing> to <prod>"`.
  That PR carries every commit not yet on production, including other people's,
  so list what it contains in the body. Merge strategy is the repo's call - if
  its docs say merge commit, say so in the handoff.

Then hand back again and stop. The user merges and checks production.

## Rules

- **Never merge a PR**, never push to a testing or production branch directly,
  never force-push.
- **Only touch plugins that are in the drop folder *and* already on the branch.**
  Do not update anything else you notice is out of date, and never add a plugin
  the branch does not carry - mention both instead.
- **Never "fix" a plugin's code** to make a version parse. Correct the value you
  pass to the script; leave the vendor's files byte-for-byte as shipped.
- **Stop and ask** on: downgrades, vendored copies with local patches, and
  anything the repo's own docs contradict. Plugins the branch does not carry are
  skipped rather than asked about.
- Prefer the scripts over hand-rolled git: they are idempotent and each run is
  isolated to one plugin.

For symptoms and their fixes - unreadable `Version:` headers, slug mismatches,
zip layouts, `gh` failures, partially completed runs - see
[references/troubleshooting.md](references/troubleshooting.md).
