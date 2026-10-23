---
name: migration-status
version: 0.1.0
description: Answer questions about Team 51 Pressable to WordPress.com migrations from the shared migrations space on Spacefast - the status of one site's migration, who is running it, what it is waiting on, or which migrations are in progress, blocked or finished. Use this whenever someone asks "what's the status of the example.org migration", "who is migrating example.org", "is anyone migrating example.org", "which migrations are in the cutover window", or "list the Pressable migrations", including people who have no local migrations folder. Read-only.
argument-hint: "[site domain]"
---

# Migration status

The Team 51 migrations space (`https://t51-pressable-migrations.space.fast/`,
team-only) holds one page per migration plus an index. The `migration-audit`
skill creates a site's entry and `migration-run` updates it after every step,
so the space is the shared record of who is migrating what.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"
```

Needs the Spacefast CLI signed in to the Team 51 team (`npx -y spacefast@0.5.0
login`). If a command exits 2 with a login error, ask the user to run that and
try again.

## One site

```bash
python3 "$S/space.py" check <domain>
```

Exit 3 means there is no entry: nobody has audited the site with the plugin.
Say so, and that `migration-audit` would start one.

Otherwise answer from what it prints: the status, the phase and next step,
anything blocked and why, the target site, who started it and who updated it
last and when, and the page link. For more detail (decisions, recent steps
with notes, the step log), add `--json` for the full status file.

## All migrations

```bash
python3 "$S/space.py" list
```

One line per site, most recently updated first: status, steps done out of the
total, next step. Filter it to answer the question asked (in the window,
blocked, complete).

## Statuses

| Status | Meaning |
|---|---|
| Audited | Audit published, no step done yet |
| On hold | Audit found blockers, no step done yet |
| Preparing | Work before the cutover window |
| In cutover window | Freeze, copy, checks or go-live under way |
| Live, after cutover | Site is on WordPress.com; post-cutover, DNS, staging or decommission work remains |
| Blocked | A step is marked blocked; the reason is in its note |
| Complete | Every step done or skipped |

The page is only as current as the last publish. If someone recorded steps
without publishing, the space lags their local folder; the "last update" time
shows how fresh it is.

Do not change anything from this skill. To pick up or continue a migration,
use `migration-run`.
