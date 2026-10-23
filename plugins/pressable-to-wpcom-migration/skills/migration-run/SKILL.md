---
name: migration-run
version: 0.1.0
description: Walk a Pressable to WordPress.com site migration through its runbook - preparing the target, platform items, the cutover window (freeze, the one Reprint copy via the Migration Assistant, checks, the database diff gate, DNS switch), post-cutover tasks (stats, subscribers, payments), Team 51 monitoring, the staging site and decommission. Use this whenever someone wants to start, continue, resume or check progress on a site migration that has already been audited ("what's next for the example.org migration", "run the cutover", "continue the migration"), or asks how to do a specific migration step. Needs a migrations/<domain>/ folder from the migration-audit skill; if there is none, run that skill first.
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

Then check the Team 51 migrations space, which is the shared record.

**Spacefast sign-in.** Before the first space command, run
`python3 "$S/space.py" login`. Exit 0: already signed in. Exit 10: it printed a
link and a code; give both to the user, ask them to open the link, check the
code matches and approve, then run `python3 "$S/space.py" login --wait`, which
returns 0 once they have (4 if not within 10 minutes; start again). Exit 2:
the account is not in the Team 51 team, or the CLI failed; tell the user. A
sign-in lasts 30 days, so this is usually exit 0.

```bash
python3 "$S/space.py" check <domain>
```

If the space's last update is newer than this folder's progress, or was made
by someone else, tell the user who did what and when, and ask before going
on. Two people must not run the same migration at once. To take over a
migration started elsewhere, the folder needs the space's progress:
`python3 "$S/space.py" pull <domain> --dir "$D"` (into a folder with no
`state.json`), then re-run the audit into that folder.

## Starting a run

Nothing has to be supplied up front. The source blog ID is already in the
audit. The target site does not exist yet: creating it is a runbook step, and
its address and blog ID are recorded then (`state.py target`), after which the
runbook is rebuilt with those values in every command and link.

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
   `python3 "$S/state.py" --dir "$D" done <step-id> "short note" --publish`.
   Use `skip` with a reason when a step does not apply, `block` when it cannot
   proceed. `--publish` rebuilds the report and updates the site's page and
   status in the migrations space, so the team sees where the migration is.
   Always pass it. If the publish fails, the step is still recorded locally:
   say so, and publish later with `python3 "$S/space.py" publish --dir "$D"`.
   Keep notes free of secrets and partner credentials: they are published.
5. After any `decide` or `target` command, rebuild so the runbook picks up the
   new values. `--publish` on those commands does the rebuild and the publish;
   without it, run `python3 "$S/build_audit.py" --dir "$D"`.

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

- **There is one copy.** It runs inside the cutover window, with the source
  frozen, and cannot be repeated against the same target. It replaces the
  target's database, so database changes made on the target before it are
  lost: keep them as commands in `$D/post-sync.sh`, run once after the copy.
  Files added to the target beforehand are kept.
- **The database diff is the go-live gate.** `verify.db-diff` lists every row
  on the source that is missing or different on the target. Resolve or record
  each before the DNS change. If gaps cannot be explained, unfreeze the source
  and stop: the live site has not changed.
- **Never SafetyNet.** It deletes users, orders and subscriptions and scrubs
  keys, even in its keep-data mode. Never install it on a target and never
  create a target with `wpcom:clone-site`. The quarantine mu-plugin in
  `assets/` is the non-destructive replacement. The one place it appears is
  the staging copy made in the last phase, where `wpcom:clone-site` installs
  it on the copy, not on production. Never sync that copy back to production.
- **The live site is not touched before the freeze**, apart from plugin cleanup
  the partner agreed to.
- **The old site stays frozen after cutover**, so visitors with stale DNS
  cannot create data that would be lost.
- **WooPayments is never set up afresh on the new site.** A store with an
  existing account will show a setup prompt on the new blog ID; clicking
  through it creates a second Stripe account and orphans the real one. The
  WooPayments team re-links the existing account instead.
- **The site stays Team 51-managed.** Do not transfer anything, and do not
  remove Atlantis, SSO, Team 51 accounts or monitoring. Handing a site to a
  partner is a separate process.
- **The old site stays connected to Jetpack** until the new one reports the
  production domain. Dropping the old connection first raises an `@here`
  alert.
- **Never disconnect or reconnect Jetpack on either site.** The new site's
  local `jetpack_options['id']` keeps the source's blog ID after the copy; that
  is expected and not fixed by reconnecting, which could register the new site
  under the source's ID. Check connection health in the Jetpack debug tool and
  raise anything wrong in `#reprint`. **Restore User Connection** in the debug
  tool is not a reconnect and is used: for the connection owner after the copy,
  and to connect a domain owner's account (`verify.domain-owner`).
- **The domain leaves Pressable in the window.** Pressable and WordPress.com
  are both WP Cloud hosts, so the domain is removed from the Pressable site and
  its `atomic-domain` TXT records replaced before it can be primary on
  WordPress.com. A domain registered at WordPress.com switches name servers the
  moment it is moved to the new site, so its zone is exported beforehand.
- **The copy brings the freeze file with it.** It no longer acts on
  WordPress.com, but `post-sync.sh` removes it from the new site first.
- **The Assistant saying "complete" is not proof.** After the copy, check
  Blog RC (step `sync.cleanup`) and re-queue the cleanup if it is still in
  progress.
- **Secrets stay out of the conversation.** Read constant values and keys on
  the site and set them on the target without echoing them.

## Untested steps

Steps marked **UNTESTED** in the runbook describe the intended procedure but
have not been run end to end. When you reach one, say so. If reality differs,
do what works, with the user's agreement, and write what happened to
`$D/notes.md` so `scripts/runbook.py` can be corrected.

## The Migration Assistant

The copy itself is run by a person in `mc.a8c.com/migration-assistant/` (the
runbook has the link with the target's blog ID). It runs Reprint's preflight,
the migration and a WordPress.com-side cleanup. It runs once per target: a
second run against the same target is not possible, so it happens inside the
cutover window with the source frozen.

If it fails: same-site redirects, TLS and storage warnings can be continued
through in the Assistant; an authentication error means the Reprint exporter
plugin is missing on the source or its public key does not match the one the
Assistant shows; anything else, take the blog ID link to `#reprint`.

After the copy, and again after the domain change, a person repairs the new
site's Jetpack connection in the
Jetpack debug tool
(`https://jptools.wordpress.com/debug/?url=<site URL>#async_section_connection_health`):
**Restore User Connection** in the connection health section, then
**Schedule Sync** in the Full Sync section. The copy replaces the database, so
WordPress.com's view of the site is stale until then.

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
who it is waiting on, and anything blocked. The migrations space is the
hand-off: confirm its page is current (`space.py check <domain>`), and if a
publish failed during the session, run `space.py publish --dir "$D"` now.
