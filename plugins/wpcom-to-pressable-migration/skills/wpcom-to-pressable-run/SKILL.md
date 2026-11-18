---
name: wpcom-to-pressable-run
version: 0.1.0
description: Walk a WordPress.com (Atomic) to Pressable site migration through its runbook - creating the Pressable site with the team51 CLI, the quarantine, a rehearsal Reprint pull run on Pressable, the final pull in the cutover window, switching deploys to Pressable's GitHub integration with the .deployignore allowlist, the DNS change, the new Jetpack connection, subscribers and decommission. Use this whenever someone wants to start, continue or check progress on a WordPress.com to Pressable migration that has been audited ("what's next for the example.org move to Pressable", "run the rehearsal pull", "do the cutover"). Needs a migrations/<domain>/ folder from the wpcom-to-pressable-audit skill; if there is none, run that first.
argument-hint: "<site domain> [step-id]"
---

# WordPress.com → Pressable run

Drive one site's migration from its generated runbook. Do the steps an agent can do, hand the person the ones only
they can do, verify each, and record progress.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"
python3 "$S/state.py" --dir "$D" status
```

If `$D/RUNBOOK.md` does not exist, run the `wpcom-to-pressable-audit` skill first. If the audit is more than a few
days old, or the window is close, re-run it.

## How to work

1. `python3 "$S/state.py" --dir "$D" next` names the next open step. Read it in `RUNBOOK.md`, with its **Verify** line.
2. Say which step you are on, who does it, and whether it touches the live site.
3. Do it, or hand it over with exactly what the person needs (links, IDs, values).
4. Run the verification. Only then: `python3 "$S/state.py" --dir "$D" done <step-id> "short note"`. Use `skip` with a
   reason when a step does not apply, `block` when it cannot proceed. Keep notes free of secrets.
5. After `decide` or `target`, rebuild: `python3 "$S/build_audit.py" --dir "$D"`. Commands in the runbook pick up the
   new values (the Pressable ID, its address and IPs, the new blog ID).

Work in order. The order encodes dependencies: the quarantine before the first pull, the final pull before the
allowlist (it reads the Pressable site's files), WordPress.com deployments off before the allowlist merges, the
integration connected before DNS, the copied Jetpack connection deleted before the quarantine comes off.

### Steps that change something

Before any command that writes to a site, DNS, a repo or a deploy, state the command and what it changes and get a
clear yes, every time. A yes for one step does not cover the next. The riskiest:

- anything on the live WordPress.com site: installing the Reprint plugin, authorising the token, the freeze;
- `run` with `step: db`, which replaces the Pressable database;
- `place`, which writes into Pressable's wp-content;
- merging the `.deployignore` PR and `pressable:connect-site-repository`;
- adding the domain on Pressable and changing DNS records;
- deleting the copied Jetpack options and removing the quarantine.

Read-only checks (`probe`, `status`, `help`, `place` with `dry_run`, the verify scripts) need no confirmation.

### When verification fails

Stop. Report what the check showed. Do not work around it. In the window, a failed gate means: remove the freeze if
there is one, tell the user, and investigate with the live site untouched. Nothing has changed for visitors until
`cut.add-domain`.

## The Reprint copy

`scripts/reprint_remote.php` runs on the Pressable site through `wp_eval.sh` and drives the Reprint client there. All
its state lives in one work directory under `/tmp` (outside the web root; it refuses anything inside `/srv/htdocs`):
`reprint.phar`, the private key, Reprint's state and the downloaded files. The database password comes from the site's
own constants and is never printed.

- `probe` - read-only environment check. `bgtest` then shows whether a background process outlives the WP-CLI call.
- `setup` - downloads `reprint.phar`, makes a key pair, prints the **Migration Token** to authorise on the live site.
- `run` (`step: files` | `db`) - runs the pull. On Pressable always pass `"foreground": true`: each WP-CLI call runs in
  its own container, so a background process dies when the call ends (2026-11-17). The call returns when the pull ends
  or at `max_seconds` (default 1800); run it again after a failure or a cut-off and Reprint resumes. `/tmp` persists.
  `files` pulls only wp-content, without WordPress.com's platform plugins (`--exclude-host-plugins`) and without the
  freeze mu-plugin. `db` imports straight into the Pressable database and rewrites the live URL to the temporary one.
- `status` - alive or not, exit code, the last progress line and the end of the log.
- `place` - copies the pulled wp-content into Pressable's, skipping both hosts' platform files, caches and the migration
  mu-plugins. Always `dry_run` first.
- `help` - a Reprint command's `--help`, to check flags against the installed client when something fails.
- `cleanup` - deletes the work directory. Only at decommission, or to start a pull over.

If a foreground run cannot finish either, run the pull on a laptop (`php reprint.phar pull-files` into a local folder, upload over SFTP, `wp db import`), and write down which in
`$D/notes.md`.

## Rules that hold throughout

- **The quarantine is on from before the first pull until `cut.jetpack`.** The pull copies the live site's Jetpack
  tokens; the quarantine keeps Jetpack offline on the copy so it cannot sync into the live blog ID. Never remove it
  before deleting `jetpack_options` and `jetpack_private_options`.
- **Never use Jetpack's identity-crisis "migrate" option, and never reconnect the old site.** Pressable gets a new
  blog ID; the old one stays with the old site, which keeps working at its WordPress.com address until decommission.
- **A database pull replaces every table.** Plugin activations and options set on Pressable after the last pull are
  lost; repeat them after the final pull.
- **The `.deployignore` allowlist is written from the Pressable site's files, after the final pull.** Pressable's GitHub
  integration deletes every server file the repo lacks unless the block protects it. The block must stay last in the
  file, and `!` lines outside it are removed. `pressable:connect-site-repository` refuses a branch that fails
  `prepare-site-repository --check`, and a site with an active DeployHQ server.
- **WordPress.com deployments come off before the allowlist merges.** They ignore its `!` lines and copy nothing.
- **Only the apex and `www` records change.** Mail, verification, other subdomains and their `atomic-domain` TXT records
  stay exactly as they are.
- **Secrets stay out of the conversation.** Copy keys and constants between sites inside one shell line.

## Untested steps

Most steps are marked **UNTESTED**: this direction has not been run end to end yet. When you reach one, say so. If
reality differs, do what works, with the user's agreement, and write what happened to `$D/notes.md` so
`scripts/runbook.py` and `scripts/checks.py` can be corrected.

## Useful commands

```bash
# WP-CLI. The argument order differs by host.
team51 wpcom:run-site-wp-cli-command <blog ID> '<wp command>' -n --no-ansi </dev/null
team51 pressable:run-site-wp-cli-command '<wp command>' <pressable ID> -n --no-ansi </dev/null

# Migration mu-plugins (install and remove write to the site)
"$S/mu_plugin.sh" status  <wpcom|pressable> <site> t51-migration-quarantine.php
"$S/mu_plugin.sh" install pressable <pressable ID> "$PLUGIN_DIR/assets/t51-migration-quarantine.php"
T51_FREEZE_MODE=frozen "$S/mu_plugin.sh" install wpcom <blog ID> "$PLUGIN_DIR/assets/t51-migration-freeze.php"
```

For checks at each stage use the `wpcom-to-pressable-verify` skill.

## Finishing a session

Run `state.py status` and tell the user what was done, the next open step and who it waits on, and anything blocked.
