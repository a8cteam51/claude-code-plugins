---
description: Batch-convert multiple WPBakery pages to Gutenberg on a local WordPress Studio site. Discovers candidates, asks the user to scope the run, dispatches one subagent per page, and writes a single report.
argument-hint: <site-path>
allowed-tools: Bash, Read, Write, AskUserQuestion, Agent
---

# /wpbakery-to-gutenberg:wpbakery-batch

Orchestrate a batch WPBakery→Gutenberg conversion across multiple posts on a local Studio site. **Each per-page conversion runs inside a subagent** so that the main context window only ever holds the candidate list, the user's choices, and per-page summaries — never the actual post content, rendered HTML, or block markup. This is the only reason this command exists as a command instead of just looping inside the single-page skill.

Per-page work follows the `wpbakery-to-gutenberg` skill verbatim. **Do not reimplement that procedure here** — read `${CLAUDE_PLUGIN_ROOT}/skills/wpbakery-to-gutenberg/SKILL.md` once at the start so you know what to delegate, then dispatch.

## Inputs

- **`$ARGUMENTS`** — site path (absolute path to the Studio site's WordPress root). Required.

If `$ARGUMENTS` is empty or doesn't look like an absolute path, ask the user via AskUserQuestion (free-text via "Other").

## Step 1 — preconditions (orchestrator-side, run once)

Do these in parallel before any discovery. If any fails, stop with a plain-text reason — no recovery, no workarounds.

1. `command -v studio` and `studio --version` — `studio` CLI must be on PATH.
2. `studio site status --path=<site-path>` — must report a managed site. Capture the Local URL for the report header.
3. If status reports stopped, run `studio site start --path=<site-path>` and wait.
4. `studio wp core is-installed --path=<site-path>` — must exit 0.
5. Confirm `mcp__wordpress-studio__validate_blocks` is exposed in the current session. If not, surface it: the batch will run, but per-page subagents will skip the validate-and-fix pass and the report will flag every page as `validate=skipped`.
6. `mkdir -p <site-path>/.wpbakery-migration/` (subagents will stage `converted-<id>.txt` and `update-<id>.php` here, just like the single-page skill).

## Step 2 — discover candidates

List every post that contains a WPBakery shortcode marker. Use `wp post list --s`, not `wp db query` — on a Studio (SQLite) site `$wpdb` is not fully loaded under `wp db query` / `wp eval`, and raw-SQL paths can return an empty result set even when matching posts exist. `wp post list --s` runs through `WP_Query`, which the SQLite integration handles cleanly:

```bash
studio wp post list \
  --post_type=any \
  --post_status=publish,draft,private,pending \
  --s='[vc_' \
  --fields=ID,post_type,post_status,post_title \
  --orderby=type --order=ASC \
  --format=json \
  --path=<site-path>
```

`--post_type=any` already skips post types registered with `exclude_from_search => true` (e.g. `revision`, `nav_menu_item`), so no explicit `NOT IN` clause is needed. `attachment` has `exclude_from_search => false` and is included by `any`; in practice attachments don't carry `[vc_` in their content, but drop any returned row with `post_type=attachment` before dispatch as a safety net.

Capture the JSON result. If zero rows, stop: "No posts contain WPBakery shortcodes. Nothing to do." Do not proceed to the question step.

Then resolve each candidate's permalink in **one** WP-CLI call — looping `wp eval` per ID is wasteful. Stage the ID list inside `.wpbakery-migration/`:

```bash
printf '%s\n' <id1> <id2> ... > <site-path>/.wpbakery-migration/batch-ids.txt
studio wp eval 'foreach (file(__DIR__ . "/.wpbakery-migration/batch-ids.txt", FILE_IGNORE_NEW_LINES) as $id) { $id = (int) $id; echo $id . "\t" . get_permalink($id) . "\n"; }' --path=<site-path>
```

Merge the permalink output back into the candidate rows. If `get_permalink()` returns empty for any ID (drafts of CPTs with broken rewrites, mostly), tag that row `url=null` — that page is not batch-eligible (the single-page skill needs a fetchable URL for the rendered-CSS extraction step). Surface skipped rows in the final report.

Compute per-post-type counts (`page: 23, post: 4, custom_x: 2`) — you'll show this in the question step so the "filter by type" option has context.

## Step 3 — ask the user how to scope the run

Use AskUserQuestion with these four options. Lead the question with the totals: `Found <N> candidates (page: 23, post: 4, …). How should we scope this run?`

1. **Convert all candidates** — every eligible row from step 2.
2. **Pick specific IDs** — show the list, accept a comma-separated ID list via free-text follow-up.
3. **Filter by post type** — follow-up question listing the post types that appeared in step 2.
4. **Dry run** — write the candidate list to the report file and stop, no subagents dispatched.

Resolve each branch:

- **All** → working set = every URL-eligible row.
- **Pick** → after the user picks this option, ask a free-text follow-up via AskUserQuestion's "Other" path: "Which IDs? (comma-separated)". Parse, intersect with the candidate set (silently drop IDs the user typed that aren't in the candidate set, but call this out in the final report).
- **Filter by type** → AskUserQuestion with one option per type that appeared in step 2 (multiSelect=true). Working set = all rows of the chosen type(s).
- **Dry run** → skip directly to step 5 with an empty results list and a `mode: dry-run` flag.

## Step 4 — dispatch subagents, one at a time

For each row in the working set, in serial (one Agent call per iteration, wait for the result before the next):

```text
Agent({
  description: "Convert WPBakery page <id>",
  subagent_type: "general-purpose",
  prompt: <see template below>
})
```

**Subagent prompt template** — fill in `<id>`, `<url>`, `<site-path>`, `<post-type>`, `<post-title>`:

> Convert one WPBakery page to Gutenberg on a local WordPress Studio site, following the skill at `${CLAUDE_PLUGIN_ROOT}/skills/wpbakery-to-gutenberg/SKILL.md` exactly.
>
> **Inputs**:
>
> - Post ID: `<id>`
> - Page URL: `<url>`
> - Site path: `<site-path>`
> - Post type: `<post-type>`
> - Post title (for context only): `<post-title>`
>
> Read the SKILL.md file first, then execute steps 1–6c on this single post. Skip step 7 — instead, return your result as a single JSON object on the final line of your response. Use this exact schema (no trailing prose after it):
>
> ```json
> {
>   "id": <id>,
>   "url": "<url>",
>   "post_type": "<post-type>",
>   "status": "success" | "failed" | "skipped",
>   "shortcode_counts": {"vc_row": 12, "vc_column_text": 28, ...},
>   "validate_summary": {"ok": N, "auto_fixed": N, "downgraded": N, "skipped": false},
>   "todos": ["unhandled vc_xyz on line N", ...],
>   "smoke_test": {"http_code": 200, "error_string_count": 0},
>   "failure_reason": null | "<short reason — set when status != success>",
>   "original_backup_path": "/tmp/wpbakery-original-<id>.txt",
>   "converted_path": "/tmp/wpbakery-converted-<id>.txt"
> }
> ```
>
> Continue-on-error policy: if any precondition or step fails for this post, set `status: "failed"`, fill `failure_reason` with a one-line description, return the JSON, and stop. Do not retry, do not partially write — the orchestrator will move on to the next post.
>
> Do not call any other slash commands, do not invoke other agents, and do not chat — the only output the orchestrator parses is the final JSON line.

After each Agent call returns, parse the trailing JSON line out of its response and append it to the in-memory results list. If the response doesn't contain valid JSON, synthesize a `{"id": ..., "status": "failed", "failure_reason": "subagent returned no parseable JSON"}` entry and move on. **Never let one failed subagent abort the batch** — that's the whole point of the continue-on-error policy.

After every 5 conversions, emit a one-line progress update to the user (`[batch] 5/47 done, 1 failed`).

## Step 5 — write the batch report

Write the report to `/tmp/wpbakery-batch-<UTC-timestamp>-report.md` (timestamp format `YYYYMMDD-HHMMSSZ`). Structure:

```markdown
# WPBakery → Gutenberg batch conversion

- **Site**: <site-path> (<local-url>)
- **Run started**: <iso-timestamp>
- **Run finished**: <iso-timestamp>
- **Scope**: <All | Picked: 1,2,3 | Filtered: post_type=page | Dry run>
- **Mode**: <converted | dry-run>

## Summary

| Outcome | Count |
| --- | --- |
| Converted successfully | N |
| Failed | N |
| Skipped (no resolvable URL) | N |
| Dropped (user-supplied ID not in candidate set) | N |

## Per-post results

| ID | Type | URL | Status | Validate (ok / fix / downgrade) | Smoke (HTTP / errs) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | page | http://... | success | 18 / 2 / 0 | 200 / 0 | |
| 57 | page | http://... | failed | — | — | step-6a re-read still showed `[vc_`; write did not land |
| ... | | | | | | |

## Outstanding TODOs

Per-post TODOs surfaced by the subagents (unhandled `vc_*`, blocks downgraded to `core/html`, lossy mappings). Group by post.

- **ID 42** (`/about-us/`)
  - unhandled `vc_pie` on line 84
  - `vc_gmaps` downgraded to `core/html`
- ...

## Backups

Pre-conversion `post_content` is preserved at `/tmp/wpbakery-original-<id>.txt` for every attempted post. To revert a single page, open the WP admin edit screen for that post and use the Revisions panel.
```

Print the report path to the user as the final user-facing line. Do not echo the per-post detail into the chat — the report file is the deliverable.

## Step 6 — clean up

Remove `.wpbakery-migration/batch-ids.txt`. Leave the per-post `wpbakery-original-*.txt` and `wpbakery-converted-*.txt` in `/tmp/` — those are the audit trail the report points at.

## Things that should stop the batch (vs. continue-on-error)

Hard stops (abort the run, do not dispatch subagents):

- Any step-1 precondition fails (missing CLI, bad site path, site can't start, WP-CLI doesn't work, mkdir fails).
- Discovery query in step 2 errors out.
- Zero candidates after discovery.

Continue-on-error (record in report, move to next):

- Per-post failures inside a subagent (any reason).
- `get_permalink()` returns empty for an ID.
- User typed IDs that aren't in the candidate set.
- `mcp__wordpress-studio__validate_blocks` unavailable — every per-post `validate_summary.skipped` will be `true` but conversions still proceed.

## Constraints

- **Serial only.** Do not dispatch multiple Agent calls in one message. SQLite + `wp_update_post` under concurrent writes will trip Yoast indexable errors and corrupt the result set.
- **Do not retry** failed subagents inside this command. Report the failure; the user can re-run the single-page skill manually for any post they want to investigate.
- **Do not invent options** in the scope question — stick to the four listed in step 3.
- **Do not summarize converted content** in chat. The report file is the channel for detail; the chat is for progress and the final path.
