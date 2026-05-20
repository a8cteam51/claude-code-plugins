---
name: clone-into-existing-site
description: Converts an existing local WordPress Studio site's wp-content directory into a fresh clone of a GitHub repo while preserving the site's local runtime data (uploads, SQLite database, db.php drop-in, sqlite-database-integration mu-plugin, and all installed plugins and themes). Use when the user asks to "set up git on an existing site", "make this site's wp-content a git repo", "swap wp-content for <repo> on an existing site", "git-ify my Studio site's wp-content", "back the existing site with this repo", "point my local site at <repo>", "clone <repo> into an existing site without losing my uploads/database/plugins/themes", or describes any variant of converting an already-working local Studio site to be backed by a git repo. For brand-new sites with no local data to preserve, use clone-new-site instead.
---

# Convert an existing Studio site's wp-content into a git clone

Trigger when the user already has a working local WordPress site (typically created via Studio) and wants to replace its `wp-content` with a fresh clone of a GitHub repo, **without** losing local runtime data (uploads, the SQLite database, and the SQLite drop-in). For brand-new sites with no local state to preserve, use the `clone-new-site` skill instead.

All filesystem mutation, git auth preflight, runtime-data restoration, and `.gitignore` patching are delegated to `${CLAUDE_PLUGIN_ROOT}/scripts/clone-into-existing-site.sh`. Never re-implement these steps inline; that breaks the repeatability guarantee and risks losing the user's local data.

## Step 0 — extract the repo from the user's message

The user will reference the repo as one of:
- Full GitHub URL: `https://github.com/owner/repo` or `.git`
- SSH URL: `git@github.com:owner/repo.git`
- Shorthand: `owner/repo`

If no repo is identifiable, ask once via AskUserQuestion (free-text via "Other"). Do not guess.

## Step 1 — pick the target site

The script needs the **site root directory** (the dir that contains `wp-content/`), not `wp-content/` itself.

Detect candidate sites by parsing `studio site list --format json`:

```bash
studio site list --format json 2>/dev/null | jq -r '.[] | "\(.name)\t\(.path)"' 2>/dev/null
```

Then decide:

- **cwd is the root of a Studio site (cwd contains `wp-content/` and matches a path from `studio site list`)** → propose cwd as the target. State this in plain text and confirm before mutating.
- **`studio site list` returned one or more sites** → AskUserQuestion listing each `<name> (<path>)` as an option, plus an "Other" option for a custom path.
- **`studio site list` is empty / `studio` not on PATH / `jq` not installed** → AskUserQuestion with cwd as the recommended option and "Other" for free-text. If the user types a path, expand `~` to `$HOME` before passing it on.

Whatever path is chosen, before invoking the script verify it exists and contains a `wp-content/` directory. If it doesn't, surface that and ask again rather than guessing.

Also verify `<site>/wp-content-temp` does **not** already exist. If it does, stop and tell the user — they likely have a previous half-finished run and need to inspect/remove it manually. Do not delete it for them.

## Step 2 — confirm before mutating

State, in one line per fact:
- The resolved site path.
- The repo URL (or shorthand) to be cloned.
- What will happen: `wp-content` → `wp-content-temp`, fresh clone into `wp-content`, then `uploads/`, `database/`, `db.php`, `mu-plugins/sqlite-database-integration/`, and the contents of `plugins/` and `themes/` (per-child, so plugins/themes shipped by the repo aren't blown away wholesale — local copies win on conflict) moved back.

Do not invoke the script before the user has had a chance to object. A simple "Proceed? (yes/no)" via AskUserQuestion is appropriate.

## Step 3 — invoke the script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/clone-into-existing-site.sh" \
  --site-path "<resolved-site-path>" \
  --repo "<repo-as-given>"
```

Quote all values. Pass `--repo` exactly as the user gave it; the script handles `owner/repo` → URL normalisation.

The script:
1. Validates inputs, checks the repo with `git ls-remote` (private-repo auth failures surface here, before any rename).
2. Renames `<site>/wp-content` → `<site>/wp-content-temp`.
3. `git clone`s the repo into a fresh `<site>/wp-content`. If this fails, the script restores `wp-content` from `wp-content-temp` and exits non-zero.
4. Moves `uploads/`, `database/`, `db.php`, and `mu-plugins/sqlite-database-integration/` from `wp-content-temp` back into the new `wp-content` as whole units. For `plugins/` and `themes/`, moves each child individually (so the repo's own committed plugins/themes are preserved and only conflicting names are overwritten by the local copy). Missing items are silently skipped; existing items in the cloned repo at the same path are overwritten (runtime data wins).
5. Patches `<site>/wp-content/.gitignore` to ignore Studio-generated files (idempotent — prints `==> .gitignore patched` only if it actually wrote).
6. Installs the latest release of the `a8cteam51/safety-net` plugin into `wp-content/plugins/safety-net` (skipped if already present) and activates it via `studio wp --path <site> plugin activate safety-net`. The latest release tag is resolved from `https://api.github.com/repos/a8cteam51/safety-net/releases/latest` at runtime. This step is non-fatal: a failure prints a warning and leaves the rest of the conversion intact — the user can re-run `${CLAUDE_PLUGIN_ROOT}/scripts/install-safety-net.sh --target-dir <site>` manually.
7. Leaves `wp-content-temp` in place for the user to inspect and delete.

## Reporting

On success, emit a short summary:
- The site path.
- The repo that was cloned into `wp-content`.
- Which items were moved back (the script prints `moved:` / `skip:` lines — relay the moved set).
- Whether `.gitignore` was patched (only if the script printed `==> .gitignore patched`).
- Safety-net status from the script's final `safety-net:` line — either "installed and activated" or a note that the user should re-run `install-safety-net.sh` manually.
- A reminder that `wp-content-temp` is still on disk and should be deleted once the user has verified the site still works.

On non-zero exit, surface the script's stderr verbatim and stop. Do not try to repair partial state, retry, or work around the failure. If the user asks to recover:
- Pre-rename failure (e.g. repo auth): nothing to do — re-run after fixing the cause.
- Clone failure: the script already restored `wp-content`. Re-run after fixing the cause.
- Restore-step failure: tell the user the site is half-migrated. The new `wp-content` exists (cloned repo) and `wp-content-temp` still holds whichever items haven't been moved yet. They should inspect both before deciding to retry or revert by hand.
- Safety-net failure (script ran to completion but printed the safety-net warning): re-run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/install-safety-net.sh" --target-dir <site>` directly.

## Constraints

- Do not run `git clone`, `mv wp-content`, or `rm -rf wp-content-temp` outside the script.
- Do not delete `wp-content-temp` automatically — the user must decide when it's safe.
- Do not commit, push, or otherwise touch git history in the cloned repo.
- Do not pass flags or env vars to the script that are not in its `--help`.
