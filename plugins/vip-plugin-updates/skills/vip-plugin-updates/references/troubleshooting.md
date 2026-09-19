# Troubleshooting

Symptoms you will actually hit, and what to do. Everything here assumes the
scripts in `../scripts/`.

## The version cannot be read

`plugin_inventory.py` already falls back through the `Version:` header, a
`*_VERSION` constant in the main file, `readme.txt`'s `Stable tag`, and
`composer.json` / `package.json`. When it still reports `unknown-new-version`,
or reports a version you do not trust, find the real one yourself:

```bash
S=<drop-folder>/.staged/<slug>
grep -riE '^\s*\*?\s*Version:' "$S"/*.php | head            # header, any main file
grep -rniE "VERSION'?\s*,\s*'[0-9]" "$S"/*.php | head       # version constants
grep -iE '^(Stable tag|Version):' "$S"/readme.txt           # wp.org readme
sed -n '1,20p' "$S"/changelog.txt 2>/dev/null               # topmost changelog entry
ls <drop-folder>                                            # the zip name often carries it
```

Common shapes that break naive parsing, and what they mean:

| Header value | What it is | What to use |
| --- | --- | --- |
| `@@VERSION@@`, `{{VERSION}}`, `%%VERSION%%` | Unreplaced build placeholder | The constant, readme, or zip name |
| `Version: 1.2.3 // updated` | Trailing comment | `1.2.3` |
| `Version:1.2.3` (no space), CRLF endings | Formatting | `1.2.3` - the parser handles both |
| Header in `class-plugin.php`, not `<slug>.php` | Non-standard main file | Fine, note which file it came from |
| Two files with `Plugin Name:` | Bundled sub-plugin | Confirm which is the real main file |

Then pass it explicitly: `--new-version 1.2.3`. **Do not edit the plugin's files
to make the header parse.** The vendored copy must be what the vendor shipped -
a hand-edited header is a bug someone will chase for an hour a year from now.
If you genuinely cannot establish a version, say so and hand that one plugin
back; do the rest.

## The staged folder name is not the vendored folder name

Zips unpack to `woocommerce-waitlist-3.0.0/`, `plugin_name/`, or a vendor's
marketing name. The inventory matches on slug, slug-minus-version, `Plugin Name`
and `Text Domain`, and tells you which it used (`matched_by`). The destination
is `--slug`; the source is `--src`. When they differ:

```bash
scripts/open_plugin_pr.sh --slug woocommerce-waitlist \
  --src <drop-folder>/.staged/woocommerce-waitlist-3.0.0 ...
```

Getting this backwards creates a second copy of the plugin under a new folder
name, and WordPress will load both. If a PR ever shows a whole plugin added
rather than modified, that is what happened - close it, delete the branch
(`git push origin --delete <branch>`), and redo it.

## The plugin is not vendored yet (`new-plugin`)

Installing a plugin is not the same job as updating one: it needs a decision
about whether the site should run it at all, and usually a VIP code review. Stop
and ask. If the answer is yes, it is still one PR, but say plainly in the body
that this adds a new plugin rather than updating one.

## The new version is lower than the vendored one (`downgrade`)

Real causes, in rough order of likelihood: an old zip in the drop folder; the
vendored copy is a beta or a patched build; the versions come from different
sources (header vs `Stable tag`) and disagree; a vendor reset their numbering.
Report which sources produced each number and ask. Never downgrade a payment,
checkout or shipping plugin without an explicit yes.

## The update would delete files (`local_only_files`)

The copy is `rsync --delete` - deliberately, because that is how a plugin update
works. But if someone patched the vendored copy by hand, that patch is in those
files:

```bash
git -C <repo> log --oneline -10 -- plugins/<slug>
git -C <repo> show <suspicious-commit> -- plugins/<slug>
```

Update commits are expected. Anything else - a hotfix, a hardcoded API endpoint,
a removed nag - means the new version drops someone's work. Surface it with the
file list and the commits; let the user decide whether it is reapplied, and let
them do it or tell you to.

## The repo's .gitignore swallows plugin files

Some VIP repos ignore `node_modules/`, build output, or specific plugin folders.
Ignored files never reach the commit, so the deployed plugin is missing pieces
while the PR looks clean. Check before opening the PR:

```bash
cd <repo>
(cd <drop-folder>/.staged/<slug> && find . -type f) \
  | sed 's|^\./|plugins/<slug>/|' \
  | git check-ignore --stdin -v
```

Any output is a file that will not be committed, with the rule that excludes it.
Junk (`.DS_Store`, source maps) is fine. Anything the plugin needs at runtime is
not - report it rather than editing `.gitignore` yourself.

## Zip layouts that need a hand

- **Double-nested** (`plugin.zip` → `plugin/plugin/`): stage it, then point
  `--src` at the inner directory.
- **A bundle of several plugins**: `stage_updates.sh` warns and skips it. Unpack
  it yourself, move each plugin into the drop folder as its own directory, and
  re-run staging with `--force`.
- **Zips containing zips** (common with marketplace downloads that include
  docs): unpack the inner plugin zip into the drop folder and delete the wrapper.
- **`.tar.gz` / `.tgz`**: not handled. `tar xzf` it into the drop folder first.
- **Nothing staged at all**: the drop folder probably holds loose plugin files
  rather than a folder per plugin. Put them under `<slug>/` and re-run.

## `gh` and git failures

| Symptom | Cause | Fix |
| --- | --- | --- |
| `could not add label` | Label does not exist in this repo | The script retries without it; pick a real label from `detect_repo.sh` output or leave it off |
| `a pull request for branch ... already exists` | Re-run of a completed plugin | Check the existing PR covers this version, then move on |
| `RESULT pushed-no-pr` | Push worked, PR did not | `gh pr create --base <base> --head <branch> --title ... --body ...`; the commit is safe |
| `Branch ... already exists on origin` | An earlier run, or last month's | Look at the PR for that branch first; `--reuse-branch` only if you mean to add to it |
| `Protected branch update failed` | Pushing at a base branch | Never push to the base branch - the script does not; check your `--base-branch` |
| `Working tree has uncommitted tracked changes` | Modified tracked files would ride along on the update branch | Show `git status --short` and ask. Do not stash for them |
| `Untracked files inside plugins/<slug> would be committed` | Someone's scratch file sits in the plugin being updated | Show the paths and ask; `--allow-dirty` only if they genuinely belong in the commit |
| Required check fails on a production PR | A guard workflow restricts what may target production | Read the workflow. Usually the production pass is a promotion PR from the testing branch, not per-plugin PRs |

## Recovering a half-finished run

Every run is one plugin, so recovery is per plugin, and the scripts are
idempotent: re-running a plugin whose branch already exists skips it rather than
making a mess.

```bash
gh pr list --repo <owner/repo> --search "update/" --state open   # what exists now
git -C <repo> branch -a --list 'update/*'                        # local leftovers
git -C <repo> checkout <testing-branch>                          # get back to a sane state
git push origin --delete <branch>                                # abandon a bad branch
git -C <repo> branch -D <branch>                                 # and its local copy
```

If a run was interrupted mid-copy, the working tree may hold a partial plugin on
an update branch. `git checkout <testing-branch>` then `git branch -D` the
update branch and start that plugin again - do not try to repair the tree by
hand.

## Verifying what you shipped

```bash
gh pr list --repo <owner/repo> --state open --search "Update" --limit 30
git -C <repo> show <branch>:plugins/<slug>/<slug>.php | grep -i '^ \* Version:'
```

After the user merges and the deploy lands, the version in WP Admin > Plugins is
the real check. Ask them to confirm it rather than assuming a green PR means a
live plugin.
