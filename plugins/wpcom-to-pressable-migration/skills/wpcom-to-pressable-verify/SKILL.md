---
name: wpcom-to-pressable-verify
version: 0.1.0
description: Run the verification checks for a WordPress.com (Atomic) to Pressable migration and report what differs - data parity, plugin/theme/config comparison, URL crawl, front end, row-level database diff, quarantine and freeze status, Jetpack connection state, and the post-cutover straggler check. Use this whenever someone asks whether the Pressable copy is complete or correct, "is it safe to cut over", "did the pull work", or wants to confirm nothing was written to the old WordPress.com site after cutover. Read-only.
argument-hint: "<site domain> [checkpoint: rehearsal | final | live]"
---

# WordPress.com → Pressable verify

Read-only checks that compare the WordPress.com source with the Pressable target. Report differences as they are; do
not explain them away.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"
```

From `$D/state.json`: `domain`, `target.pressable_id`, `target.domain` (the temporary address). The source blog ID is
in `$D/manifest.json` (`wpcom.blog_id`, or `site.jetpack.blog_id`). With no Pressable site recorded there is nothing
to compare.

## The checks

**Site comparison** - plugins and versions, theme, mu-plugins, platform leftovers, PHP, constants, REST namespaces, cron,
the Atlantis key, and whether the target still holds the source's Jetpack connection.

```bash
"$S/wp_eval.sh" pressable <pressable ID> "$S/site_audit.php" > "$D/site-target.json"
python3 "$S/compare_sites.py" "$D/site.json" "$D/site-target.json"
```

Re-take `site.json` from the source first if the audit is old. Expect REST namespaces only WordPress.com serves
(`wpcom/v2`, `wpcomsh/v1`, `help-center` and the like) to be missing on Pressable: list them, they are not a fault.

**Data parity** - counts, highest IDs and latest change times per content type, and a row count for every table.

```bash
"$S/wp_eval.sh" wpcom <blog ID> "$S/parity.php" > "$D/parity-source.json"
T51_ARGS='{"other_host":"<source domain>"}' "$S/wp_eval.sh" pressable <pressable ID> "$S/parity.php" > "$D/parity-target.json"
python3 "$S/compare_parity.py" "$D/parity-source.json" "$D/parity-target.json"
```

Before the domain moves, references to the source domain on the target should be zero (the pull rewrote them); after
it, pass the temporary address as `other_host` instead.

**Database diff** - every table, row by row. Host names are treated as equal.

```bash
python3 "$S/db_diff.py" --source <blog ID> --target <pressable ID> --hosts <domain>,<temporary address> --out "$D/db-diff" --sql
```

`DIFF.md` separates **gaps** (rows on the source missing or different on the target) from platform and target-only
differences. WordPress.com writes options of its own (`wpcom_*`, `at_*`, Jetpack); those are not gaps.

**URL crawl**

```bash
python3 "$S/url_check.py" https://<domain> https://<temporary address> --limit 150
```

**Front end** - needs Node 20+, Google Chrome and `npm ci --prefix "$S/frontend"` once.

```bash
node "$S/frontend/sample.mjs" https://<domain> --out "$D/frontend-paths.txt"
node "$S/frontend/snapshot.mjs" https://<domain> --paths "$D/frontend-paths.txt" --out "$D/frontend/source"
node "$S/frontend/snapshot.mjs" https://<temporary address> --paths "$D/frontend-paths.txt" --out "$D/frontend/target"
node "$S/frontend/compare.mjs" "$D/frontend/source" "$D/frontend/target" --out "$D/frontend/REPORT.md"
```

Expected notes, not issues: WordPress.com's own assets (`bilmur`, `s0.wp.com`, the `wpcomsh` and Gutenberg-served
block assets), images served through `i0.wp.com` on one side and locally on the other until Jetpack connects on
Pressable, and the quarantine's noindex.

**Quarantine, freeze and the Reprint work directory**

```bash
"$S/mu_plugin.sh" status pressable <pressable ID> t51-migration-quarantine.php
"$S/mu_plugin.sh" status wpcom <blog ID> t51-migration-freeze.php
T51_ARGS='{"action":"status","work":"/tmp/t51-reprint-<site name>"}' "$S/wp_eval.sh" pressable <pressable ID> "$S/reprint_remote.php"
```

**Stragglers** - rows written to the old site after the window started (`decisions.window_started.value` in
`state.json`).

```bash
T51_ARGS='{"since":"<YYYY-MM-DD HH:MM:SS UTC>"}' "$S/wp_eval.sh" wpcom <blog ID> "$S/parity.php" \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['after_since'])"
```

Run it before the DNS change (`cut.old-site`). Once the domain moves, the team51 CLI cannot reach the old site until
WordPress.com moves it to its `*.wpcomstaging.com` address: it goes through the old site's primary domain, which then
lands on Pressable. In between, read the old site's Activity Log instead.

**Which host answers** - the `host-header` response header: `WordPress.com` for the Atomic site, `wpcloud` for Pressable.
`x-ac` names the edge pool and reads `_atomic_…` on both, so it cannot tell them apart. Before `cut.jetpack` the
quarantine's noindex also marks the Pressable copy.

## Checkpoints

| Checkpoint | Run | Pass means |
|---|---|---|
| `rehearsal` | site comparison, parity, URL crawl, front end, database diff, quarantine present | No missing tables, active plugins or theme. No missing assets or new errors on the front end. Differences in recent rows are expected on a live source. |
| `final` | the same, after the final pull | The database diff reports NO GAPS, or every gap is explained and recorded. This is the go-live gate: give an explicit go or no-go. |
| `live` | DNS from several resolvers, `host-header`, certificate, site comparison against the live domain, front end against the pre-window baseline, quarantine absent, Jetpack on a blog ID other than the old site's, stragglers | The domain resolves to Pressable everywhere and `host-header` is `wpcloud`, the certificate is valid, mail records unchanged against `zone-before.txt`, no Jetpack REST namespaces missing, straggler counts zero. |

For `live` DNS:

```bash
for r in 1.1.1.1 8.8.8.8 9.9.9.9; do echo "$r: $(dig +short <domain> @$r | tr '\n' ' ') | MX: $(dig +short MX <domain> @$r | tr '\n' ' ')"; done
curl -sI "https://<domain>/?nocache=$RANDOM" | grep -iE '^HTTP|^host-header'
```

## Reporting

State the checkpoint, then pass or fail, then each difference with its numbers. Finish with what you could not check.
