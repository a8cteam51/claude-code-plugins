---
description: Scaffolds a local WordPress site whose wp-content is a cloned repo, named by an explicit project name. Use when the user wants to set up a local WP site from an a8c repo for Studio.
argument-hint: <owner/repo|git-url> [project-name]
allowed-tools: Bash, AskUserQuestion
---

# /studio-repo-clone:init

Orchestrate the studio-repo-clone workflow. All filesystem mutations, git auth preflight, `.gitignore` patching, and Studio invocation are delegated to `${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh` — your job is to gather inputs, choose the target directory, and invoke the script. Never replicate the script's behaviour inline; that breaks the repeatability guarantee.

## Inputs

Parse `$ARGUMENTS` as up to two whitespace-separated tokens:
- Token 1: repo (`owner/repo` shorthand or git URL — required).
- Token 2 (optional): project name. If present, must be a valid directory name (lowercase, digits, hyphens, underscores).

If the repo is missing, ask via AskUserQuestion (free-text via "Other"). Do not proceed without one.

Derive the repo name from the URL (used as the suggested project name):
- `owner/repo` → `repo`
- `https://github.com/owner/repo(.git)?` → `repo`
- `git@github.com:owner/repo.git` → `repo`

## Step 1 — get the project name

The project name is used for both the root folder and the Studio site name.

- If token 2 was provided and is valid, use it. Confirm in plain text.
- Otherwise ask via AskUserQuestion:
  1. `<repo-name>` (recommended)
  2. (Other for custom name)

  If the user provides something invalid (spaces, uppercase, punctuation), slugify it (e.g. "My Cool Project" → "my-cool-project") and confirm the slug back before proceeding.

## Step 2 — choose the target directory

Run `pwd`, `basename "$(pwd)"`, and `ls -A "$(pwd)"`.

Also detect the user's effective Studio base directory from existing Studio sites — Studio has no CLI flag that exposes its install root, so we infer it from `studio site list`:

```bash
studio site list --format json 2>/dev/null \
  | jq -r '.[].path // empty' 2>/dev/null \
  | xargs -I {} dirname {} \
  | sort | uniq -c | sort -rn \
  | awk 'NR==1 {sub(/^[[:space:]]*[0-9]+[[:space:]]+/, ""); print}'
```

`jq` is used for JSON parsing (robust against escaped quotes / minified output), `xargs -I {}` preserves paths with spaces, and the `awk` strips the leading `uniq -c` count without splitting on whitespace inside the path.

If this prints a path, use it as `<studio-base>`. If empty (no sites yet, `studio` not on PATH, or `jq` not installed), fall back to `$HOME/Studio`, which is Studio's documented default.

- **cwd basename equals project name AND cwd is empty** → target = cwd. State this and proceed.
- **otherwise** → AskUserQuestion:
  1. `<studio-base>/<project-name>` (recommended — Studio's default location)
  2. `<cwd>/<project-name>`
  3. `~/Sites/<project-name>`
  4. (Other; must end in the project name to keep folder/site name parity.)

Expand `~` to `$HOME` before passing to the script. State the resolved target in plain text so the user can object before any mutation.

## Step 3 — ask about WP_DEBUG_LOG

`WP_DEBUG_LOG` is a near-universal want for local dev sites — without it, PHP errors go nowhere visible. Ask via AskUserQuestion:

1. `Yes — enable WP_DEBUG_LOG` (recommended)
2. `No — leave defaults`

If the user picks yes, pass `--debug-log` to the script. The script runs `studio site set --debug-log --path "<target>"` after the site is created.

## Step 4 — invoke the script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh" \
  --target-dir "<resolved-target>" \
  --repo "<token-1>" \
  --site-name "<project-name>" \
  [--debug-log]
```

Always quote all values. The script handles `owner/repo` → URL normalisation. Always pass `--site-name` explicitly with the project name so the Studio site matches the folder. Include `--debug-log` only when the user opted in at Step 3.

The script will:
1. Validate inputs, check `studio` CLI is on PATH, and run `git ls-remote` against the repo URL so private-repo auth failures surface before any download.
2. Stage the full layout in a temp dir (download zip → SHA1-verify → unzip → drop default wp-content → `git clone` repo into staged wp-content).
3. Move the staged tree into the target.
4. Append a Studio-generated-files block to `<target>/wp-content/.gitignore` if those entries are missing (creates the file if absent).
5. Run `studio site create --path <target> --name <site-name> --skip-browser` (Studio 1.8 is SQLite-only via the CLI; default WordPress and PHP versions).
6. If `--debug-log` was passed, run `studio site set --debug-log --path <target>` to enable `WP_DEBUG_LOG`. A failure here leaves the site in place — the user can re-run it manually.

If anything fails before step 3, the target directory is untouched. If the script created the target dir and then failed mid-move, it removes the partial target on the way out. Step 5 and 6 failures leave files in place — the user can rerun the Studio command manually.

## Reporting

On success, emit a 4-6 line summary:
- Project name
- Target directory
- Repo cloned into wp-content
- Studio site name (= project name, DB: SQLite)
- If `--debug-log` was passed (script prints `debug log:  enabled`), note that `WP_DEBUG_LOG` is on.
- Point the user at the URL and admin credentials Studio printed to stdout.

On non-zero exit, surface the script's stderr verbatim and stop. Do not try to repair partial state, retry, or work around the failure — repeatability requires the script to be the only mutator. If the user asks you to recover, suggest:
- Pre-Studio failure: delete the target dir and re-run `/studio-repo-clone:init`.
- Studio-create failure: re-run `studio site create --path <target> --name <name> --skip-browser` directly.
- Debug-log failure (site already exists): re-run `studio site set --debug-log --path <target>` directly.

## Constraints

- Do not run `curl`, `unzip`, `rm -rf wp-content`, `git clone`, or `studio site create` outside the script.
- Do not pass flags or env vars to the script that are not in its `--help`.
- Do not commit, push, or otherwise touch git history in the cloned repo.
