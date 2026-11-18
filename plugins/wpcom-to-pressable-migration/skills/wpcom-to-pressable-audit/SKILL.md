---
name: wpcom-to-pressable-audit
version: 0.1.0
description: Audit a WordPress.com (Atomic) site before moving it to Pressable, and generate its migration report and step-by-step runbook. Use this whenever someone wants to migrate, move or "audit for migration" a Team 51 site from WordPress.com (wpcom, Atomic, WoA) to Pressable, asks what would break or need manual work in that move, or asks about the Jetpack blog ID, subscribers, DNS, deploy or lockdown implications of moving a site off WordPress.com. Read-only - it never changes the site. For the opposite direction (Pressable to WordPress.com) use the pressable-to-wpcom-migration plugin instead.
argument-hint: "<site domain or WordPress.com blog ID>"
---

# WordPress.com → Pressable audit

Inspect one WordPress.com Atomic site and produce, in `migrations/<domain>/` under the current directory:

- `REPORT.md` - blockers, decisions, manual steps, and what the process handles.
- `RUNBOOK.md` - the ordered steps for this site, with commands filled in.
- `manifest.json`, `findings.json`, `state.json` - the facts the run and verify skills use.

Write for someone who knows the partner and the site but not WP-CLI: say what needs an answer and who can give it.

## What is already settled

These hold for every migration in this direction. The report prints them under "Already settled". Never raise them as
questions:

- The site stays Team 51-managed on Pressable. The partner is added as a Pressable collaborator.
- The copy is made with **Reprint**, run on the new Pressable site and pulling from the live site. The Migration Assistant
  on mc.a8c.com is not used: it only copies into WordPress.com. A Reprint pull can be repeated, so there is a rehearsal and
  a final pull.
- The Pressable site is created with `team51 pressable:create-site`, without a repository. Pressable's GitHub integration
  is connected just before the DNS change, after `pressable:prepare-site-repository` has written the allowlist. DeployHQ is
  not used.
- A domain registered at WordPress.com stays registered there, with its DNS there, unless the task says otherwise.
- Jetpack gets a new blog ID on Pressable. Subscribers are migrated; stats are merged only where the Stats module was on.

## Ground rules

- **Read-only.** Nothing here changes the site, DNS, a repo or a setting. A step that seems to need a write becomes a finding.
- **Never print secrets.** Use the bundled scripts for site inspection; they report constant names, not values.
- **Record what you could not check.** A missing input shows as "Not checked" in the report.
- These folders hold partner details. Add `migrations/` to `.gitignore` unless the user says otherwise.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"; mkdir -p "$D"
```

Needed: the `team51` CLI (update it first: `team51 --force-update list`; Pressable deploys changed in late 2026), `gh`,
`dig`, `whois`, `python3`, `php`. MCP tools: `mcp__team51__*` and `mcp__context-a8c__*` (call `load-provider` first). If
the team51 CLI reports **403 "API calls to this blog have been disabled"**, the blog's API access is switched off,
which happens to sites leaving Team 51 support. Stop and ask the user to turn it back on (Blog RC); nothing below works
without it.

## Steps

Run independent steps in parallel, but only one WP-CLI call against the Atomic site at a time: two at once failed
with "Could not connect to the SSH server" (2026-11-17).

### 1. Site inventory → `site.json`, `webroot.json`

```bash
"$S/wp_eval.sh" wpcom <blog ID> "$S/site_audit.php" > "$D/site.json"
"$S/wp_eval.sh" wpcom <blog ID> "$S/web_root.php" > "$D/webroot.json"
```

Use the blog ID: the team51 MCP tools and CLI can fail to resolve a domain on Atomic. `wpcom:list-sites` (filter with
`grep`) gives the ID, and also shows other WordPress.com sites using the same name, which go in step 2.

### 2. WordPress.com facts → `wpcom.json`

```bash
python3 "$S/wpcom_facts.py" <blog ID> --out "$D/wpcom.json"
```

Then add, editing the same file: `stickers` (`mcp__team51__wpcom_list_site_stickers`) and `existing_sites`, a list of
`{blog_id, url, note}` for other WordPress.com sites on the same domain or name (an older blog on `www.` is common, and
the staging site from step 5). Where your evidence answers whether one matters, add `severity` (`info` or `manual`),
`action` and `"steps": ["decom.wpcom-sites"]`; otherwise it is raised as a decision.
Fleet stats (`mcp__team51__wpcom_list_sites_stats_summary`, saved to a file, filtered with `grep`) give views for
those; a blog with the Stats module off returns an error there, which is itself the answer.

### 3. Activity → `activity.json`

This decides whether the live site needs a freeze in the window. Read the activity log with the context-a8c `wpcom`
provider, `site-activity-log`, filtered to the `post`, `feedback` and `user` groups for the last 90 days or more. The
result is large and saved to a file: summarise it with `jq`, never read it whole. Add who edited most recently
(`wp post list --post_type=any --orderby=modified` through `team51 wpcom:run-site-wp-cli-command`).

```json
{ "last_content_edit": "2026-08-18", "last_content_editor": "<name> (partner | Team 51)", "edited_last_14d": false,
  "form_entries_90d": 3, "comments_90d": 0, "last_partner_login": "2026-07-06", "source": "what you read" }
```

Leave out bulk imports (dozens of form entries in one minute) from the counts, and say so in `source`.

### 4. DNS → `dns-<apex>.json`

```bash
python3 "$S/dns_audit.py" <apex> --site-ips <current A records> --names www,<known subdomains> > "$D/dns-<apex>.json"
```

`whois` and the context-a8c `domains` provider (`get-domain-subscriptions`) tell you which WordPress.com account holds
a registration; put that in `context.json`.

### 5. Repo and deploys → `deploy.json`

Find the repo (`gh api --paginate 'orgs/a8cteam51/properties/values?per_page=100'`, filtered for the domain, or the
current directory's remote). Its custom properties also name the WordPress.com staging site
(`site-url-staging`, `wpcom-blog-id-staging`): add that to `existing_sites` in `wpcom.json` for decommission. Check the
layout (themes/plugins/mu-plugins at the root) and whether the deploy branch's `.deployignore` already has a
`# BEGIN Pressable deploy allowlist` block.

WordPress.com GitHub Deployments: `team51 wpcom:site:deployment:webhook:list <blog ID>` names the connected
deployment and repo ("Using site deployment 7391 (a8cteam51/…)").

Drift: compare every file the repo tracks under themes/, plugins/ and mu-plugins/ with the live site, read-only:

```bash
ARGS=$(git ls-files themes mu-plugins plugins | python3 -c "import json,sys; print(json.dumps({'paths':[l.strip() for l in sys.stdin if l.strip()]}))")
T51_ARGS="$ARGS" "$S/wp_eval.sh" wpcom <blog ID> "$S/file_hashes.php" > "$D/live-hashes.json"
```

then compare each `hashes[path]` with the md5 of the file at the deploy branch. Files `.deployignore` keeps out are
missing on the server by design. Real differences go in `drift`: the Pressable integration's first deploy would
overwrite them.

```json
{ "repo": "a8cteam51/<repo>", "branch": "trunk", "wpcom_deployments": "connected | not connected | unknown: why",
  "layout_ok": true, "allowlist_present": false, "drift": null, "evidence": "what you compared" }
```

### 6. Related Pressable sites → `pressable-related.json`

The partner's other Pressable sites, as `[{id, url, note}]`. `mcp__team51__pressable_list_sites` returns a large result
saved to a file: filter it with `jq` by the partner's name stem.

### 7. Context → `context.json`

Linear (the migration issue and anything for the domain), Slack (search the domain and partner, a year back) and the
project P2 on `team51projects.wordpress.com` (context-a8c `wpcom` → `posts-text` by guessed slugs). Keep what matters to
the move, at most 15 notes: who asked and why, the partner collaborator's email, DNS and registrar arrangements, dates,
anything fragile.

```json
{ "notes": [ { "source": "Slack", "url": "https://…", "note": "One sentence.", "severity": "info | manual | decision | blocker",
               "action": "", "owner": "TAM | Developer | …" } ] }
```

A note with severity `decision` can carry `"decision_key": "<key>"`; once that key is recorded with `state.py decide`,
the note drops to info. Where the history answers something the report asks, record it, for example
`python3 "$S/state.py" --dir "$D" decide partner_collaborator <email>`. `state.py` needs a `state.json`, so build once
first (step 8), then record and build again.

### 8. Build

```bash
python3 "$S/build_audit.py" --dir "$D"
```

Read `REPORT.md` against what you saw. If a finding is wrong, fix the input file and rebuild; do not edit the report.
Something no check covers goes in `context.json`, and tell the user it is a candidate for a new check in
`scripts/checks.py`.

### 9. Tell the user

Short, plain, in this order: can the site move and what it waits on; each blocker and decision as a question, with who
answers it; two to four things that make this site different; what was not checked; where the report is. Then say the
`wpcom-to-pressable-run` skill starts the work.
