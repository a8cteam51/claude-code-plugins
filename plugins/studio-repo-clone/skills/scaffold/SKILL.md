---
name: scaffold-studio-site
description: Scaffolds a local WordPress Studio site from a GitHub repo by downloading WordPress, replacing wp-content with the cloned repo, and creating a Studio site via the studio CLI. Use when the user asks to "set up a Studio site", "scaffold a Studio site from <repo>", "spin up a local WordPress for <repo>", "create a Studio site using <github url>", "install WordPress with this repo as wp-content", "clone <repo> into a fresh WordPress install", "get a Studio site running with <repo>", "bootstrap a WordPress site from <repo>", "stand up a local WP site with wp-content from <repo>", or describes any variant of bootstrapping/getting-running a local WP Studio site whose wp-content comes from a specific repo.
---

# Scaffold a Studio site from a repo

Trigger when the user wants to set up a local WordPress site whose `wp-content` is a cloned GitHub repo, with Studio managing it. All filesystem mutation, git auth preflight, `.gitignore` patching, and Studio invocation are delegated to `${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh`. Never re-implement steps inline; that breaks the repeatability guarantee.

This is the same workflow as the `/studio-repo-clone:init` slash command, exposed via natural language.

## Step 0 — extract the repo from the user's message

The user will reference the repo as one of:
- Full GitHub URL: `https://github.com/owner/repo` or `.git`
- SSH URL: `git@github.com:owner/repo.git`
- Shorthand: `owner/repo`

If no repo is identifiable in the user's request, ask once via AskUserQuestion (free-text via "Other"). Do not guess a repo.

Derive the repo name from the URL (used as the suggested project name):
- `owner/repo` → `repo`
- `https://github.com/owner/repo(.git)?` → `repo`
- `git@github.com:owner/repo.git` → `repo`

## Step 1 — get the project name

The project name is used for both the root folder and the Studio site name, so it must be explicit. ALWAYS ask via AskUserQuestion, even if the user mentioned a name in their message — only skip if they very clearly stated one as the project name (e.g. "set up project FOO using repo X").

AskUserQuestion options:
1. `<repo-name>` (recommended)
2. (Other for custom name)

The chosen name MUST be a valid directory name: lowercase letters, digits, hyphens, underscores. If the user provides something invalid, slugify it (e.g. "My Cool Project" → "my-cool-project") and confirm the slug back.

## Step 2 — choose the target directory

Run `pwd` then `basename "$(pwd)"` and `ls -A "$(pwd)"` to detect cwd state.

- **cwd basename already equals the project name AND cwd is empty** → target = cwd. State this and proceed.
- **otherwise** → AskUserQuestion with:
  1. `<cwd>/<project-name>` (recommended)
  2. `~/Sites/<project-name>`
  3. (Other for custom path; must end in the project name to keep folder/name parity)

Expand `~` to `$HOME` before passing to the script. State the resolved target in plain text so the user can object before any mutation.

## Step 3 — ask about WP_DEBUG_LOG

`WP_DEBUG_LOG` is a near-universal want for local dev sites — without it, PHP errors go nowhere visible. Ask via AskUserQuestion:

1. `Yes — enable WP_DEBUG_LOG` (recommended)
2. `No — leave defaults`

If the user picks yes, pass `--debug-log` to the script. The script will run `studio site set --debug-log --path "<target>"` after the site is created.

## Step 4 — invoke the script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh" \
  --target-dir "<resolved-target>" \
  --repo "<repo-as-given>" \
  --site-name "<project-name>" \
  [--debug-log]
```

Quote all values. Pass `--repo` exactly as the user gave it; the script handles `owner/repo` → URL normalisation. Always pass `--site-name` explicitly with the project name so the Studio site matches the folder. Include `--debug-log` only when the user opted in at Step 3.

The script:
1. Validates inputs, checks `studio` CLI is on PATH, and runs `git ls-remote` against the repo URL so private-repo auth failures surface before any download.
2. Stages WordPress (download + SHA1 verify + unzip, dropping default `wp-content`) and `git clone`s the repo into staged `wp-content` — all in a temp dir.
3. Moves the staged tree into the target.
4. Appends a Studio-generated-files block to `<target>/wp-content/.gitignore` if those entries are missing (creates the file if absent). The script prints `==> .gitignore patched` when it does so.
5. Runs `studio site create --path <target> --name <site-name> --skip-browser` (Studio 1.8 is SQLite-only via the CLI; default WordPress and PHP versions).
6. If `--debug-log` was passed, runs `studio site set --debug-log --path <target>` to enable `WP_DEBUG_LOG`. A failure here leaves the site in place — the user can re-run the command manually.

If anything fails before step 3, the target dir is untouched. If the script created the target and failed mid-move, it removes the partial target. Step 5 and 6 failures leave files in place — Studio can be retried manually.

## Reporting

On success, emit a 4-7 line summary:
- Project name
- Target directory
- Repo cloned into wp-content
- Studio site name (= project name, DB: SQLite)
- If the script printed `==> .gitignore patched`, note that `wp-content/.gitignore` was updated to ignore Studio-generated files.
- If `--debug-log` was passed (script prints `debug log:  enabled`), note that `WP_DEBUG_LOG` is on.
- Point the user at the URL and admin credentials Studio printed to stdout.

On non-zero exit, surface the script's stderr verbatim and stop. Do not try to repair partial state, retry, or work around the failure. If the user asks to recover:
- Pre-Studio failure: delete the target dir and re-trigger the workflow.
- Studio-create failure: re-run `studio site create --path <target> --name <name> --skip-browser` directly.
- Debug-log failure (site already exists): re-run `studio site set --debug-log --path <target>` directly.

## Constraints

- Do not run `curl`, `unzip`, `rm -rf wp-content`, `git clone`, or `studio site create` outside the script.
- Do not pass flags or env vars to the script that are not in its `--help`.
- Do not commit, push, or otherwise touch git history in the cloned repo.
