---
name: migration-verify
version: 0.1.0
description: Run the verification checks for a Pressable to WordPress.com migration and report what differs - data parity between source and target, plugin/theme/config comparison, URL crawl, Jetpack connection identity, quarantine and freeze status, and the post-cutover straggler check. Use this whenever someone asks whether a migrated copy is complete or correct, wants to compare the old and new site, asks "is it safe to cut over", "did the sync work", "check parity", or wants to confirm nothing was written to the old site after cutover. Read-only.
argument-hint: "<site domain> [checkpoint: first-sync | pre-cutover | cutover | post-cutover]"
---

# Migration verify

Read-only checks that compare the Pressable source with the WordPress.com
target. Each produces a clear pass or a list of differences. Report
differences as they are; do not explain them away.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"
```

Source and target come from `$D/state.json` (`domain`, `target.domain`,
`target.blog_id`) and `$D/manifest.json` (`site.jetpack.blog_id` is the source
blog ID). If there is no target recorded, there is nothing to compare yet.

## The checks

**Data parity** - counts, highest IDs and latest change times for posts,
comments, users, orders and form entries, plus a row count for every table.

```bash
"$S/wp_eval.sh" pressable <source> "$S/parity.php" > "$D/parity-source.json"
T51_ARGS='{"other_host":"<source domain>"}' "$S/wp_eval.sh" wpcom <target> "$S/parity.php" > "$D/parity-target.json"
python3 "$S/compare_parity.py" "$D/parity-source.json" "$D/parity-target.json"
```

`other_host` makes the target count rows that still mention the other
hostname. Before the domain is attached, pass the source domain (references
are expected and fine). After the domain switch, pass the temporary domain
(references should be zero).

**Site comparison** - plugins and versions, theme, mu-plugins, host leftovers,
PHP, constants, REST namespaces, cron hooks.

```bash
"$S/wp_eval.sh" wpcom <target> "$S/site_audit.php" > "$D/site-target.json"
python3 "$S/compare_sites.py" "$D/site.json" "$D/site-target.json"
```

**Jetpack connection** - the copy leaves the source's blog ID in the target's
local `jetpack_options['id']`, and the WordPress.com cleanup does not change
it. Both scripts above note it; on its own it is not a failure. What decides
it is the connection in the Jetpack debug tool
(`https://jptools.wordpress.com/debug/?url=<target URL>`): connected, owner
connected, no warnings or identity-crisis flag, on the target's blog ID. After
a checksum run, the site must not carry the `out-of-sync-posts` sticker.
Never disconnect or reconnect Jetpack on either site to fix anything; report
it and stop. Also check Blog RC shows the migration complete: the Assistant
saying so is not enough.

**URL crawl** - same paths on both hosts, status codes and redirects.

```bash
python3 "$S/url_check.py" https://<source> https://<target> --limit 150
```

**Front end** - what a logged-out visitor gets, on a fixed sample of pages,
desktop and mobile. Needs Node 20+ and Google Chrome; run
`npm ci --prefix "$S/frontend"` once.

```bash
node "$S/frontend/sample.mjs" https://<source> --out "$D/frontend-paths.txt"   # once; edit to add key pages
node "$S/frontend/snapshot.mjs" https://<source> --paths "$D/frontend-paths.txt" --out "$D/frontend/source"
node "$S/frontend/snapshot.mjs" https://<target> --paths "$D/frontend-paths.txt" --out "$D/frontend/target"
node "$S/frontend/compare.mjs" "$D/frontend/source" "$D/frontend/target" --out "$D/frontend/REPORT.md"
```

The comparison groups the same difference across pages into one line and
splits it into issues and notes. Issues: a stylesheet or script the source
loads and the target does not, fonts that fail, new console errors or failed
requests, requests to the old host, mixed content, changed computed styles,
broken images, large layout or pixel differences, and content differences.
Notes: platform assets (Pressable's `gaug.es` tracker, WordPress.com's
`bilmur.min.js`, core block assets served by the Gutenberg plugin on
WordPress.com), the quarantine's noindex, small size and pixel changes.
Content differences after the first sync are usually posts created on the
live source since; check them against parity before calling them a fault.
The snapshots bypass the system proxy, because through the Automattic proxy
WordPress.com renders its admin and debug bars for logged-out visitors.

**Quarantine and freeze status**

```bash
"$S/mu_plugin.sh" status wpcom <target> t51-migration-quarantine.php
"$S/mu_plugin.sh" status pressable <source> t51-migration-freeze.php
```

**Database diff** - every table on both sides, row by row, read-only. Host
names are treated as equal, so the copy's URL rewrite does not count.

```bash
python3 "$S/db_diff.py" --source <source domain or Pressable ID> --target <target> \
  --hosts <source host>,<target host> --out "$D/db-diff" --sql
```

`DIFF.md` splits the result into **gaps** (rows on the source that are missing
or different on the target: data that would be lost) and target-only or
platform differences (options, caches, queues, tables WordPress.com adds;
not gaps). `delta.sql` holds each gap row as a REPLACE statement for a
developer to review; nothing applies it. A password-only difference on a user
is expected: site creation rotates the admin password. Fingerprinting is done
in SQL in buckets of 1,000 rows, so even a large database takes a few calls;
a table with more than 50 differing buckets is reported, not listed.

**Stragglers** - rows written to the old site after the freeze time.

```bash
T51_ARGS='{"since":"<freeze time UTC, YYYY-MM-DD HH:MM:SS>"}' "$S/wp_eval.sh" pressable <pressable id> "$S/parity.php" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['after_since'])"
```

After cutover the domain resolves to the new site, so address the old one by
its Pressable ID.

## Checkpoints

| Checkpoint | Run | Pass means |
|---|---|---|
| `pre-window` | `dig` for the lowered TTL, quarantine present on the target, front-end sample picked | TTL at 300 seconds for longer than the old TTL. |
| `copy` | freeze status (source, `frozen`), parity, site comparison, Jetpack connection and Blog RC status, URL crawl, front end against the baseline, then the database diff | No missing tables or plugins. No missing assets or new errors on the front end. Jetpack connection healthy. `db_diff.py` reports NO GAPS, or every gap is resolved or recorded. This is the go-live gate. |
| `post-cutover` | DNS resolution, certificate, site comparison against the live domain, front end against the pre-freeze baseline, quarantine absent, stragglers | Domain resolves to WordPress.com from more than one resolver, valid certificate, quarantine removed, straggler counts all zero. |

For `post-cutover` DNS and TLS:

```bash
for r in 1.1.1.1 8.8.8.8 9.9.9.9; do echo "$r: $(dig +short <domain> @$r | tr '\n' ' ')"; done
curl -sI https://<domain> | head -n 12
```

## Reading results

- **Parity on a live source is approximate until the freeze.** A few more rows
  on the source in orders, comments or options is normal for a first sync.
  After the freeze it must be exact.
- **Missing tables, missing active plugins or a different theme are never
  normal.** Report them as failures.
- **Excluded tables**: queues, logs and session tables are left out of the
  row-count comparison because they differ between any two running copies.
- A `note` in the URL crawl is a difference that is probably not the
  migration's doing (a bot challenge on one side, a path that fails on both).
  A `DIFF` needs explaining.

## Reporting

State the checkpoint, then pass or fail, then each difference with its numbers.
Finish with what you could not check. If this was the `cutover` checkpoint,
give an explicit go or no-go and the reason.
