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
| `migration-audit` | Inspects a Pressable site and writes `REPORT.md`, `RUNBOOK.md` and `REPORT.html` (both as one page for a browser) | No |
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
- For the front-end check: Node 20+, Google Chrome, and
  `npm ci --prefix scripts/frontend` once (installs `playwright-core`,
  `pixelmatch` and `pngjs`; no browser download)
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
scripts/report_html.py   report and runbook as one page        ─► REPORT.html
scripts/frontend/        page snapshots on both sides, compared ─► frontend/REPORT.md
scripts/db_diff.py       row-level database diff, source vs target ─► db-diff/DIFF.md
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
- The copy runs once, inside the cutover window with the source frozen; it
  cannot be repeated against the same target. Target-side database changes are
  scripted in `post-sync.sh` and run once after it. A row-level database diff
  (`scripts/db_diff.py`) is the go-live gate.
- The migrated site stays a Team 51-managed site: Atlantis, SSO, monitoring
  and Team 51 accounts all stay. Handing a site to a partner is a separate
  process and is not covered here.
- Team 51 monitoring keys on the blog ID and the Pressable site ID. The
  runbook adds and removes the settings rows that keep a migration from
  raising alerts, and keeps the old site connected until the new one reports
  the production domain.
- SafetyNet is never used on a migration target. `assets/` has a quarantine
  mu-plugin that only filters at runtime.
- VideoPress videos do not follow a site to a new blog ID and there is no bulk
  transfer. The audit flags them and a person moves or re-uploads them
  during the migration, with the VideoPress team for a large library. The
  old site is not deleted until every video plays on the new one.
- Stats are merged and subscribers migrated to the new blog ID on every site.
- A staging site is made with `team51 wpcom:clone-site` as the last step,
  after every DNS change. That command installs SafetyNet on the staging copy.

## Known gaps

- No command exports a Pressable DNS zone; the DNS audit only sees names it
  guesses.
- After the test migration, the new site's local `jetpack_options['id']`
  still held the source's blog ID, even after the cleanup was re-run. The
  connection itself was the new site's. Whether that is intended has not been
  confirmed with the Reprint team.
- On the test migration the Assistant reported complete while Blog RC still
  showed the migration in progress, and the first cleanup removed the
  connection owner. The runbook checks Blog RC after the copy.
- The two mu-plugins in `assets/` are drafts and have not run on a real site.
- The list of plugins "likely incompatible with WordPress.com" in `checks.py`
  is a starting list, not the official one.
- Multisite is reported as a blocker; nothing here handles it.
