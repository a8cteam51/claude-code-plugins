---
name: migration-run
version: 0.1.0
description: Walk a Pressable to WordPress.com site migration through its runbook - preparing the target, syncing with Reprint via the Migration Assistant, platform items, rehearsal, the cutover freeze and DNS switch, post-cutover tasks (stats, subscribers, payments), decommission and handover. Use this whenever someone wants to start, continue, resume or check progress on a site migration that has already been audited ("what's next for the example.org migration", "run the cutover", "continue the migration"), or asks how to do a specific migration step. Needs a migrations/<domain>/ folder from the migration-audit skill; if there is none, run that skill first.
argument-hint: "<site domain> [step-id]"
---

# Migration run

Drive one site's migration from its generated runbook. You do the steps an
agent can do, hand the person the ones only they can do, verify each, and
record progress so anyone can pick it up later.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"
python3 "$S/state.py" --dir "$D" status
```

If `$D/RUNBOOK.md` does not exist, stop and run the `migration-audit` skill.
If the audit is more than a few days old, or the site is about to be cut over,
re-run it first: sites change.

## Starting a run

Nothing has to be supplied up front. The source blog ID is already in the
audit. The target site does not exist yet: creating it is a runbook step, and
its address and blog ID are recorded then (`state.py target`), after which the
runbook is rebuilt with those values in every command and link. The partner's
WordPress.com username is only needed at handover.

So the first session usually goes: confirm the report's "Needs an answer" list
is empty or answered, agree a cutover window, then prepare the target. If the
report has open blockers, stop there and say what they are waiting on.

Tell the user where they are in plain terms before each step: what is about to
happen, whether it touches the live site, and what you need from them.

## How to work

1. `python3 "$S/state.py" --dir "$D" next` names the next open step. Read that
   step in `RUNBOOK.md`: its body, and its **Verify** line.
2. Say which step you are on and who does it.
3. Do it, or hand it over (see below).
4. Run the verification. Only then:
   `python3 "$S/state.py" --dir "$D" done <step-id> "short note"`.
   Use `skip` with a reason when a step does not apply, `block` when it cannot
   proceed.
5. After any `decide` or `target` command, rebuild so the runbook picks up the
   new values: `python3 "$S/build_audit.py" --dir "$D"`.

Work in order. The order encodes dependencies: for example the WooPayments
request goes in before the target exists because of its lead time, and the
quarantine goes on before the first sync.

### Steps for a person

Some steps cannot be done by an agent: the Migration Assistant, MC tools,
registrar changes, talking to the partner, placing test orders. For these, give
the person exactly what they need - the link, the blog IDs, the values to
enter - copied from the runbook, then wait. When they report back, run the
verification yourself where one exists.

### Steps that change something

Before running any command that writes to a site, DNS, a repo or a deploy
connection, state the command and what it changes and get a clear yes. This
applies every time, including on the target. A yes for one step does not cover
the next. The riskiest are:

- anything on the live Pressable site (plugin deletion, the freeze);
- `search-replace`, plugin deactivation and uninstall on the target;
- connecting deploys;
- removing the quarantine.

Read-only checks need no confirmation.

### When verification fails

Stop. Report what the check showed. Do not work around it and do not continue
to later steps. During cutover a failed parity check means: unfreeze the source
(remove the freeze mu-plugin), tell the user, and investigate with the clock
stopped.

## Rules that hold throughout

- **Every sync replaces the target's database.** A database change made on the
  target before the final sync is lost. Keep all of them as commands in
  `$D/post-sync.sh` and run that file after every sync. Files added to the
  target survive re-syncs.
- **Never SafetyNet.** It deletes users, orders and subscriptions and scrubs
  keys, even in its keep-data mode. Never install it on a target and never
  create a target with `wpcom:clone-site`. The quarantine mu-plugin in
  `assets/` is the non-destructive replacement.
- **The live site is not touched before the freeze**, apart from plugin cleanup
  the partner agreed to.
- **The old site stays frozen after cutover**, so visitors with stale DNS
  cannot create data that would be lost.
- **WooPayments is never set up afresh on the new site.** A store with an
  existing account will show a setup prompt on the new blog ID; clicking
  through it creates a second Stripe account and orphans the real one. The
  WooPayments team re-links the existing account instead.
- **Ownership stays with Team 51** until the handover phase. Do not transfer
  anything during the migration.
- **Secrets stay out of the conversation.** Read constant values and keys on
  the site and set them on the target without echoing them.

## Untested steps

Steps marked **UNTESTED** in the runbook describe the intended procedure but
have not been run end to end. When you reach one, say so. If reality differs,
do what works, with the user's agreement, and write what happened to
`$D/notes.md` so `scripts/runbook.py` can be corrected.

## The Migration Assistant

The sync itself is run by a person in `mc.a8c.com/migration-assistant/` (the
runbook has the link with the target's blog ID). It runs Reprint's preflight,
the migration and a WordPress.com-side cleanup. It can be re-run; each run
re-pulls the database and applies only changed files.

If it fails: same-site redirects, TLS and storage warnings can be continued
through in the Assistant; an authentication error means the source's exporter
or secret is wrong; anything else, take the blog ID link to `#reprint`.

## Useful commands

```bash
# WP-CLI. Note the argument order differs by host.
team51 pressable:run-site-wp-cli-command '<wp command>' <domain> -n --no-ansi </dev/null
team51 wpcom:run-site-wp-cli-command <domain> '<wp command>' -n --no-ansi </dev/null

# Migration mu-plugins (install and remove write to the site)
"$S/mu_plugin.sh" status  <pressable|wpcom> <site> t51-migration-quarantine.php
"$S/mu_plugin.sh" install wpcom <target> "$PLUGIN_DIR/assets/t51-migration-quarantine.php"
T51_FREEZE_MODE=drain "$S/mu_plugin.sh" install pressable <domain> "$PLUGIN_DIR/assets/t51-migration-freeze.php"
"$S/mu_plugin.sh" remove  <pressable|wpcom> <site> <file>
```

For checks at each stage use the `migration-verify` skill; for the zone and
name servers use `migration-dns`.

## Finishing a session

Run `state.py status` and tell the user: what was done, the next open step and
who it is waiting on, and anything blocked. The state file is the hand-off.
