# wpcom-to-pressable-migration

Skills for moving Team 51 sites from WordPress.com (Atomic) to Pressable: audit a site, get a report and a runbook
for it, then work through the migration with checks at each stage.

The opposite direction is the `pressable-to-wpcom-migration` plugin. This one shares its inspection and comparison
scripts (copied, with the direction-specific ones adapted) and its learnings about WP Cloud domains, Atlantis keys and
deploy allowlists.

**Status: 0.1.0.** Written for and run end to end on thinkbiggerinnovation.com (T51ENG-2541, cut over 2026-11-18). Runbook
steps not yet run on a real migration (the freeze, the Atlantis key copy) are still marked UNTESTED.

## Skills

| Skill | What it does | Changes anything? |
|---|---|---|
| `wpcom-to-pressable-audit` | Inspects a WordPress.com site and writes `REPORT.md` and `RUNBOOK.md` | No |
| `wpcom-to-pressable-run` | Walks the runbook, does the agent's steps, hands over the rest, records progress | Yes, with confirmation per step |
| `wpcom-to-pressable-verify` | Compares source and target: site, parity, database diff, URLs, front end, stragglers | No |

## Try it

```bash
# from the marketplace, once merged
/plugin install wpcom-to-pressable-migration@a8cteam51-claude-code-plugins

# or straight from a checkout of this repo
claude --plugin-dir plugins/wpcom-to-pressable-migration
```

Then, from a clone of the site's repo:

> Audit example.org for migration from WordPress.com to Pressable.

Output goes to `migrations/<domain>/` in the current directory. Those folders hold partner details; keep them out of git.

## Requirements

- `team51` CLI, authenticated through 1Password, and current (`team51 --force-update list`): the Pressable deploy
  commands it relies on changed in late 2026
- `gh`, authenticated, with access to `a8cteam51`
- `dig`, `whois`, `python3` (3.8+), `php`
- For the front-end check: Node 20+, Google Chrome, and `npm ci --prefix scripts/frontend` once
- The `team51` and `context-a8c` MCP servers for Pressable, WordPress.com, Linear, Slack and P2 lookups
- The source blog's API access switched on. Sites leaving Team 51 support can have it off, and every team51 call then
  fails with 403 "API calls to this blog have been disabled"

## How it fits together

```
scripts/site_audit.php    one read-only `wp eval` on the source      ─┐
scripts/web_root.php      what is served from outside wp-content     ├─► migrations/<domain>/*.json
scripts/dns_audit.py      registrar, name servers, records           │
scripts/wpcom_facts.py    blog ID and subscribers                    ─┘
MCP lookups               stickers, activity log, Pressable, Linear, Slack ─┤
                                                                            ▼
scripts/checks.py         the check catalogue            ─► findings.json, REPORT.md
scripts/runbook.py        the steps, switched on by findings ─► RUNBOOK.md, state.json
scripts/reprint_remote.php the Reprint client on the Pressable site: probe, setup, pull, place, cleanup
scripts/compare_sites.py, parity.php, db_diff.py, url_check.py, frontend/  the checks between source and target
```

## What the process assumes

- **The copy is Reprint, run on Pressable.** Jetpack on Atomic ships Reprint's exporter, and the Reprint plugin from
  WordPress.org works too. The client (`reprint.phar`) runs on the new Pressable site through WP-CLI, pulls wp-content
  into a work directory in `/tmp` and the database straight into the site's MySQL. A pull can be repeated, so there is
  a rehearsal and then a final pull in the window. The Migration Assistant on mc.a8c.com only copies into WordPress.com.
- **Probed on a Pressable site (2026-11-17):** `exec` and `proc_open` allowed, every extension Reprint needs loaded,
  `max_execution_time` 0, `/tmp` writable outside the web root, the same `/srv/htdocs` layout as Atomic. Whether a
  background process survives the WP-CLI call is tested by `bgtest` on the new site.
- **The quarantine keeps Jetpack offline.** The pull copies the live site's Jetpack tokens. The quarantine mu-plugin
  turns on Jetpack offline mode (new in this version) until the cutover deletes them and Jetpack connects as a new site.
- **Pressable deploys through its GitHub integration**, connected just before DNS. `pressable:create-site` runs without
  a repository; `pressable:prepare-site-repository` writes the allowlist block from the Pressable site's files after the
  final pull; `pressable:connect-site-repository` connects. WordPress.com deployments are disconnected first.
- **A domain registered at WordPress.com stays there**, DNS included, and stays attached to the Atomic site. Pressable
  writes `atomic-domain` TXT values for the apex and `www` into its own zone; they are copied into the WordPress.com zone,
  then the apex `A` records are added (the "Handled by WordPress.com" row cannot be edited; adding a custom apex `A`
  replaces it). WP Cloud hands the domain to Pressable a few minutes later. Nothing is detached.
- **The freeze is optional.** The audit reads the activity log; a site that is rarely written to gets a request to the
  partner and a straggler check instead.

## Known gaps

- One migration so far (thinkbiggerinnovation.com, 2026-11-18). A site with heavier traffic, a freeze, Atlantis messages
  or a domain registered elsewhere will exercise steps this one skipped.
- Between the domain moving and WordPress.com moving the old site to its `*.wpcomstaging.com` address, the team51 CLI
  cannot reach the old site, so `cut.old-site` does its straggler count and Monitor deregistration before DNS.
- Jetpack picks the blog by URL and may reuse one already on the domain (here, its 2023 Jetpack site with an active
  plan). The audit cannot tell beforehand; `cut.jetpack` checks the blog it lands on.
- Reprint is built to mirror a site into its own folder and run it there, so it has no step that installs into a hosted
  site's wp-content. Its tree keeps the source's absolute paths (`srv/htdocs/wp-content`, plus `wordpress/plugins` for
  the symlinked platform plugins), and `place` copies wp-content across. Its `--remap` option might write straight into
  wp-content; that is untested.
- Reprint's host-plugin list for WordPress.com covers only `wpcomsh` and its loader. Jetpack, Akismet, Gutenberg,
  page-optimize and woocommerce-fraud-protection come across as symlink targets; `place` skips them, and
  `rehearse.plugins` installs only those active on the source.
- Reprint 0.11.8's URL rewrite turns a bare `href="#"` into `href="/"`. On thinkbiggerinnovation.com this hit only old
  revisions.
- Whether Pressable rewrites URLs when the primary domain changes is not confirmed; the runbook checks and falls back to
  `wp search-replace`.
- There is no HTML report and no shared migrations space; the other direction's `report_html.py` and `space.py` could be
  brought over once this has run.
