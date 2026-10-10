---
name: migration-audit
version: 0.1.0
description: Audit a Pressable-hosted WordPress site before migrating it to WordPress.com, and generate its migration report and step-by-step runbook. Use this whenever someone wants to migrate, move or "audit for migration" a Team 51 site from Pressable to WordPress.com (wpcom, Atomic), asks what would break or need manual work in such a move, or asks for the blockers, gotchas, DNS, deploy or Jetpack/blog-ID implications of moving a site. Also use it to re-audit a site shortly before cutover, or to audit many sites for a portfolio view. Read-only - it never changes the site.
argument-hint: "<site domain or Pressable site ID>"
---

# Migration audit

Inspect one Pressable site and produce, in `migrations/<domain>/` under the
current directory:

- `REPORT.md` - blockers, decisions, manual steps, and what the process handles.
- `RUNBOOK.md` - the ordered steps for this site, with commands filled in.
- `manifest.json`, `findings.json`, `state.json` - the facts the later skills use.

The person running this is as likely to be a TAM as a developer. Write for
someone who knows the partner and the site but not WP-CLI: say what needs an
answer and who can give it, in plain words. The technical evidence is in the
files for whoever does the work.

## What is already settled

These rules hold for every migration. The report prints them under "Already
settled". Never raise them as questions, in the report, in `context.json`, or
in your summary:

- Team 51 owns the new site, repo and domain until the partner accepts it.
  Who owns what after handover is not a migration question.
- A Pressable development or staging site is not migrated. A WordPress.com
  staging site is made from the new production site after cutover.
- WordPress.com GitHub Deployments replace DeployHQ where the existing deploy
  is connected and current.
- Pressable-hosted DNS zones move to WordPress.com DNS.
- Atlantis is removed; other Team 51 access stays until handover.
- Jetpack features that a Business or Commerce plan includes need no decision.

A **decision** is something specific to this site that a person has to choose
and that changes what the migration does: a redesign in flight, a second site
on the same domain, a payment provider that may not work on the new host. If
you can answer it yourself from what you found, it is not a decision: answer
it and put the reasoning in the evidence.

## Ground rules

- **Read-only.** Nothing in this skill changes the site, DNS, a repo or any
  setting. If a step seems to need a write, record it as a finding instead.
- **Never print secrets.** Run only the bundled scripts for site inspection.
  They report constant names without values and never read keys or tokens. Do
  not `option get` whole options or `config get` secrets into the conversation.
- **Start from the production site, not from names.** A repo or DeployHQ
  project named after the site proves nothing about what deploys to it.
- **Record what you could not check.** A missing input is shown in the report
  as "Not checked". Never leave a gap looking like a clean result.
- These folders contain partner email addresses. Add `migrations/` to
  `.gitignore` unless the user says otherwise.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"
```

Needed on this machine: the `team51` CLI, `gh` (authenticated), `dig`, `whois`,
`python3`, `php`. The team51 CLI reads credentials from 1Password; if a command
hangs or reports a 1Password prompt error, run
`op vault list --account a8cteam51.1password.com` and ask the user to approve.

MCP tools (load schemas with ToolSearch if deferred): `mcp__team51__*` for
Pressable, DeployHQ and WordPress.com data, and `mcp__context-a8c__*` (call
`load-provider` first) for Linear, Slack, P2 and the blog report card. If a
provider reports `unavailable`, skip it and note that in step 7.

`mcp__team51__pressable_run_wp_cli_command` only allows a few read commands, so
site inspection goes through `$S/wp_eval.sh`, which uses the local CLI.

## Steps

Set `D=migrations/<domain>` and `mkdir -p "$D"`. Save each tool result as the
named file. Run independent steps in parallel where you can.

### 1. Resolve the site → `pressable.json`

`mcp__team51__pressable_get_site` with the domain (try the `www.` form if the
bare domain fails; some sites are registered that way). Save the JSON. Note the
Pressable `id`, `name`, `ipAddressOne`, `ipAddressTwo`.

Find the repo and blog IDs from GitHub custom properties:

```bash
gh api --paginate 'orgs/a8cteam51/properties/values?per_page=100' \
  | jq -s -c --arg d "<domain>" 'add | .[]
    | select(any(.properties[]; (.value // "" | tostring) | contains($d)))
    | {repo: .repository_name, props: ([.properties[] | select(.value != null) | {(.property_name): .value}] | add)}'
```

No match is a finding in itself: the site may have no repo, or one that was
never linked.

### 2. Site inventory → `site.json`

```bash
"$S/wp_eval.sh" pressable <domain or id> "$S/site_audit.php" > "$D/site.json"
```

About 20 seconds. If it prints "No result markers", read the CLI output it
shows: usually 1Password, or a plugin fataling under WP-CLI.

### 3. Related sites → `related.json`

`mcp__team51__pressable_list_sites` returns a very large result that is saved to
a file. Filter that file, do not read it:

```bash
jq -c --arg stem "<name stem, e.g. acme>" --argjson id <pressable id> '[.. | objects
  | select(has("id") and has("url"))
  | select(.id != $id)
  | select(.clonedFromId == $id or ((.name // "") | test($stem; "i")) or ((.url // "") | test($stem; "i")))
  | {id, name, url, staging, clonedFromId}] | unique_by(.id)' <saved file> > "$D/related.json"
```

Choose a stem that catches renamed variants (`acme` finds
`acmestore-redesign-production`). Sites on a subdomain of the same
apex (for example `shop.example.com`) matter for DNS: keep their hostnames for
step 4.

### 4. DNS and registrar → `dns-<apex>.json`

`mcp__team51__pressable_list_site_domains` lists the domains attached to the
site. For each distinct apex domain:

```bash
python3 "$S/dns_audit.py" <apex> --site-ips <ip1>,<ip2> --names <hostnames from step 3 and the domain list> > "$D/dns-<apex>.json"
```

The script classifies who hosts DNS and who the registrar is, and flags whether
the partner's registrar or DNS login is needed. It can only see names it asks
about, so its record list is a floor. Do not present it as the full zone.

If the context-a8c `domains` provider is available, `get-domain-subscriptions`
for the apex tells you which WordPress.com account holds a registration; add
that as a note in step 7.

### 5. Deploy state → `deploy.json`

The question: is there a deploy that targets the production site, and is it
current? Connecting WordPress.com deploys to a site whose deploy is stale or
absent would overwrite manual changes on the server.

1. Get the site's SFTP/SSH usernames: `mcp__team51__pressable_list_sftp_users`.
2. Collect candidate DeployHQ projects: any project whose permalink appears in
   a webhook on a candidate repo (`gh api repos/a8cteam51/<repo>/hooks`), plus
   any whose name or repo URL matches the stem in the saved output of
   `mcp__team51__deployhq_list_projects` (filter the file with `jq` or `grep`;
   do not let `head` cut the matches off).
3. For each candidate, `mcp__team51__deployhq_list_project_servers`. A server
   targets this site only if its `username` is one of the site's SFTP users
   (or, failing that, its name is the site's domain). Never print `host_key`.
4. If a server targets production and is enabled:

   ```bash
   python3 "$S/deploy_check.py" revision --repo a8cteam51/<repo> --branch <server branch> --deployed-rev <last_revision>
   python3 "$S/deploy_check.py" drift --repo a8cteam51/<repo> --rev <last_revision> --host pressable --site <domain>
   ```

   If the current directory is a clone of that repo, pass `--repo-dir .`
   instead of `--repo` to the drift check.

Write `deploy.json`:

```json
{
  "production": {
    "state": "connected-current | behind-tooling-only | behind | drifted | not-connected | unknown",
    "repo": "a8cteam51/<repo>", "branch": "trunk", "project": "<deployhq permalink>",
    "deployed_rev": "<sha>", "evidence": "one or two sentences: what was compared and what it showed"
  },
  "other_projects": ["<project, server or repo> - what it is and where it deploys"],
  "needs_decision": ["<a different project for this site that could change the plan> - why"],
  "revision_check": { }, "drift_check": { }
}
```

Choosing `state`: `drifted` if the drift check found real differences (read
its lists; built assets and ignored files are not drift); otherwise the
revision check's state (`current` → `connected-current`); `not-connected` when
no enabled server targets production; `unknown` when you could not tell.

`other_projects` is for the record: the same project's development server, an
old staging project. It shows as information. `needs_decision` is only for a
genuinely separate effort, such as a redesign with its own repo and site,
where someone has to choose the order of work. The same project deploying
`develop` to the development site is never a decision.

DeployHQ shows current servers only. If nothing targets production, say "no
evidence it was ever deployed", not "never deployed".

### 6. WordPress.com-side facts → `wpcom.json`

For the source blog ID (from `site.json` → `jetpack.blog_id`), start the file
with the subscriber count:

```bash
python3 "$S/wpcom_facts.py" <blog id> --out "$D/wpcom.json"
```

It reads `subscribers_count` from the public WordPress.com API and merges into
the file, keeping any keys already there. The figure can include social
followers on some sites, and a private site returns nothing (left as `null`).

Then add what the tools give you, editing the same file:

- context-a8c `wpcom` → `get-blog-report-card` (sections `blog_info`,
  `stickers`, `jetpack_site_info`): owner, plan stickers.
- Views: `mcp__team51__wpcom_get_site_stats` if available.
- Sites that already exist on WordPress.com for this partner:
  `mcp__team51__wpcom_list_sites`, filtered by the name stem. An earlier
  migration attempt or a staging site changes the plan.

```json
{ "subscribers": 1, "views_30d": 0, "source_plan": "…", "owner": "…", "stickers": [],
  "existing_sites": ["<domain> (blog <id>) - what it looks like"] }
```

Use `null`, not `0`, for anything you could not read.

### 7. Context → `context.json`

Look for history that changes how this site should be migrated. In past
audits this step found things no site inspection could: an earlier failed
move to WordPress.com, who holds the registrar login, a payment provider that
cannot be used for the partner's products, a redesign about to replace the
site.

**Project P2 posts.** Team 51 keeps a post per site and per project on
`team51projects.wordpress.com`, with the support history in the comments.
Fetch by slug with the context-a8c `wpcom` provider:

```
execute-tool { "provider": "wpcom", "subtool": "posts-text",
  "subtool_args": { "site": "team51projects.wordpress.com", "include_comments": true, "max_comments_per_post": 80,
                    "slugs": ["<slug>", "<slug>"] } }
```

There is no search, so guess slugs and let `unresolved_slugs` tell you which
missed. Site posts are usually the domain with dots as dashes
(`example-com`, `acme-store-com`); project posts use the project
name, often with a suffix (`acme-archive`,
`acme-store-migration`, `acme-store-redesign`). Try the
domain form, the Pressable site name without `-production`, the repo name,
and those with `-migration`, `-redesign` and `-launch`. A site post links to
its project post ("Project P2"); follow that link's slug too. If nothing
resolves, ask the user for the URL once, then carry on without it.

The result is large and is saved to a file. Do not read it whole:

```bash
python3 "$S/p2_extract.py" <saved result file>
```

This prints only the sentences that touch DNS, email, payments, earlier
migrations, redesigns and access, with dates and authors. Read that.

**Linear and Slack.** Search both for the domain and the partner or project
name, a year back. Follow links from the P2 posts where a note needs
confirming.

Keep only what matters to the migration, at most 15 notes:

- DNS, email or registrar arrangements, and who holds the logins;
- third-party integrations, and anything described as fragile;
- earlier host moves or migration attempts;
- a redesign, relaunch or other project in flight;
- dates the partner cares about, and who to contact for access;
- a finding in the report that the history explains or overturns (a gateway
  that looks misconfigured but is deliberate; a registrar login we already
  hold). Say which finding, by its ID.

Where the history settles something the report asks about, record the
decision as well, for example
`state.py --dir "$D" decide registrar_access.<apex> confirmed` when the
registrar credentials are known to be in 1Password, then rebuild.

Do not summarise the project or paste threads. One sentence per note, with the
link.

```json
{ "notes": [ { "source": "Slack", "url": "https://…", "note": "Email is on Proton; DKIM was set up by the partner's IT contractor.",
               "severity": "info | manual | decision | blocker", "action": "what to do about it, if anything",
               "owner": "who can answer or do it: TAM, Developer, Management, or a named team" } ] }
```

Most notes are `info`. Use `decision` or `blocker` only by the test in "What
is already settled" above, and write the note as the question to be answered.

Also record here, as `manual` notes, any step above that you could not
complete and why.

### 8. Build

```bash
python3 "$S/build_audit.py" --dir "$D"
```

Read `REPORT.md`. Check it against what you saw: if a finding contradicts
something you observed, fix the input file and rebuild; do not edit the report
by hand. If the site showed something no check covers, add it as a note in
`context.json` and tell the user it is a candidate for a new check in
`scripts/checks.py`.

### 9. Tell the user

Plain language, short, in this order:

1. One sentence: can this site be migrated, and what is it waiting on.
2. **Needs an answer:** each blocker and decision as a question, with who can
   answer it. If there are none, say so. Do not pad this list: nothing from
   "What is already settled", nothing you resolved yourself.
3. **Different about this site:** two to four things that make this migration
   unlike a standard one, in terms the partner's TAM would recognise ("email
   for the domain runs through this DNS zone", not "MX records present").
4. **Not checked,** and what that leaves uncertain.
5. Where the report and runbook are, and that `migration-run` starts the work.

Leave out commands, file names of scripts, check IDs and counts of steps
unless the user asks. Do not repeat the report.

## Several sites

Run the steps per site, each into its own folder, then:

```bash
python3 "$S/fleet_summary.py" migrations/ > migrations/fleet.csv
```

## Adding checks

Checks live in `scripts/checks.py`, one function each, and the steps they
switch on live in `scripts/runbook.py`. When a migration surprises you, add a
check so the next audit catches it.
