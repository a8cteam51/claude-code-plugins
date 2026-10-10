# pressable-to-wpcom-migration

Skills for moving Team 51 sites from Pressable to WordPress.com: audit a site,
get a report and a runbook for that site, then work through the migration with
checks at each stage.

**Status: 0.1.0, a draft for evaluation.** The audit has been run read-only
against real sites. Nothing after the audit has been used on a real migration
yet; runbook steps that are unproven are marked UNTESTED.

## Skills

| Skill | What it does | Changes anything? |
|---|---|---|
| `migration-audit` | Inspects a Pressable site and writes `REPORT.md` and `RUNBOOK.md` | No |
| `migration-run` | Walks the runbook, does the agent's steps, hands over the rest, records progress | Yes, with confirmation per step |
| `migration-verify` | Compares source and target: data parity, plugins, URLs, stragglers | No |
| `migration-dns` | Registrar and zone audit, cutover of site records, zone comparison | No (it tells a person what to change) |

## Try it

```bash
# from the marketplace, once merged
/plugin install pressable-to-wpcom-migration@a8cteam51-claude-code-plugins

# or straight from a checkout of this repo
claude --plugin-dir plugins/pressable-to-wpcom-migration
```

Then, from any working directory (a clone of the site's repo is useful, since
the deploy drift check can use it):

> Audit example.org for migration to WordPress.com.

Output goes to `migrations/<domain>/` in the current directory. Those folders
hold partner email addresses; keep them out of git.

## Requirements

- `team51` CLI, authenticated through 1Password
- `gh`, authenticated, with access to `a8cteam51`
- `dig`, `whois`, `python3` (3.8+), `php`
- The `team51` and `context-a8c` MCP servers for Pressable, DeployHQ, Linear,
  Slack and P2 lookups. The audit still runs without them, and says what it
  could not check.

## How it fits together

```
scripts/site_audit.php   one read-only `wp eval` on the source   ─┐
scripts/dns_audit.py     registrar, name servers, records        ├─► migrations/<domain>/*.json
scripts/deploy_check.py  is the existing deploy current?         ─┘            │
MCP lookups              Pressable, DeployHQ, Linear, Slack      ──────────────┤
scripts/p2_extract.py    project P2 history, filtered            ──────────────┤
                                                                               ▼
scripts/checks.py        the check catalogue          ─► findings.json, REPORT.md
scripts/runbook.py       the steps, switched on by findings ─► RUNBOOK.md, state.json
```

- **Checks** are plain functions in `scripts/checks.py`. Each returns findings
  with a severity: `blocker`, `decision`, `manual`, `auto` or `info`. When a
  migration turns up something new, add a check.
- **Steps** are in `scripts/runbook.py`. A step appears in a site's runbook
  when it always applies or a finding switches it on.
- **State** is `state.json`: step progress, decisions, and the target site.
  `scripts/state.py` edits it; `build_audit.py` preserves it across rebuilds.

## What the process assumes

- The copy is done by Reprint through the Migration Assistant
  (`mc.a8c.com/migration-assistant/`), run by a person.
- Every sync replaces the target database, so target-side database changes are
  scripted in `post-sync.sh` and re-run after each sync.
- Team 51 owns the new site, repo and domain until the partner accepts it.
  Handover is a separate phase. It points to `/offboard-site-audit` in
  `a8cteam51/ops-agent-skills`, which is not bundled here: run it from a clone
  of that repo.
- SafetyNet is never used on a migration target. `assets/` has a quarantine
  mu-plugin that only filters at runtime.
- VideoPress videos do not follow a site to a new blog ID and there is no bulk
  transfer. A few videos are moved one at a time or re-uploaded; a large
  library holds the site until a plan is agreed with the VideoPress team. The
  old site is not deleted until every video plays on the new one.

## Known gaps

- No command exports a Pressable DNS zone; the DNS audit only sees names it
  guesses.
- What the Migration Assistant's cleanup step does to the Jetpack connection
  has not been confirmed. The verify checks test for it.
- Whether the Assistant accepts Jetpack's built-in exporter for a Pressable
  source is unconfirmed.
- The two mu-plugins in `assets/` are drafts and have not run on a real site.
- The list of plugins "likely incompatible with WordPress.com" in `checks.py`
  is a starting list, not the official one.
- Multisite is reported as a blocker; nothing here handles it.
