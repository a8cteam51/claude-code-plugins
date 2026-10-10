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

**Jetpack identity** - the target must report its own blog ID. Both scripts
above flag a target that carries the source's ID. That is a stop: two sites
claiming one identity.

**URL crawl** - same paths on both hosts, status codes and redirects.

```bash
python3 "$S/url_check.py" https://<source> https://<target> --limit 150
```

For how pages look, use the `site-launch-comparison` skill with the same two
hosts.

**Quarantine and freeze status**

```bash
"$S/mu_plugin.sh" status wpcom <target> t51-migration-quarantine.php
"$S/mu_plugin.sh" status pressable <source> t51-migration-freeze.php
```

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
| `first-sync` | parity, site comparison, Jetpack identity, URL crawl, quarantine status | No missing tables or plugins. Data differences are explained by activity on the live source since the sync. Quarantine present. Target has its own blog ID. |
| `pre-cutover` | all of the above after the rehearsal sync, plus `dig` for the lowered TTL | Same as above, and the rehearsal's `post-sync.sh` ran clean. |
| `cutover` | freeze status (source, `frozen`), then parity after the final sync | `RESULT: PARITY` with no notes about recent rows. This is the go/no-go gate. |
| `post-cutover` | DNS resolution, certificate, site comparison against the live domain, quarantine absent, stragglers | Domain resolves to WordPress.com from more than one resolver, valid certificate, quarantine removed, straggler counts all zero. |

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
