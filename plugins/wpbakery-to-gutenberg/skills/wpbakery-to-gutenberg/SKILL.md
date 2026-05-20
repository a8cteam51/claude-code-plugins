---
name: wpbakery-to-gutenberg
description: This skill should be used when the user asks to "convert this page", "migrate this page to blocks", "convert WPBakery on <URL>", "rewrite this page as Gutenberg", or otherwise requests an in-place WPBakery→Gutenberg conversion of a single post or page on a local WordPress Studio site. Triggers when a page URL is supplied alongside any WPBakery→Gutenberg conversion intent.
---

# Convert a page from WPBakery to Gutenberg

End-to-end conversion of a single post/page on a local WordPress Studio site. The mappings reference at `${CLAUDE_SKILL_DIR}/references/shortcode-mappings.md` is the source of truth for how each `vc_*` shortcode becomes Gutenberg block markup — load it before writing any conversion output.

## Inputs

- **Page URL** (required) — full permalink, e.g. `http://localhost:8881/about-us/`. The user provides this.
- **Site path** (optional but preferred) — absolute path to the Studio site's WordPress root, e.g. `/Users/<user>/Studio/my-site`. If the user provides it, use it as-is. If they don't, infer it by matching the URL's host:port against `studio site list --format=json` (look at each entry's `localhost.url` field). If exactly one site matches, use its `path`; if zero or multiple match, stop and ask.

## Critical environment quirks

Two non-obvious things will silently corrupt this skill's output if missed:

1. **Studio's `wp` runs in a sandbox that cannot see the host `/tmp/` directory.** Any file that PHP must `file_get_contents()` from inside a `studio wp eval-file` has to live **inside the site directory** (`<site-path>/...`). Files placed in `/tmp/` are fine for host-side tools (`curl`, `perl`, `Read`) but invisible to `studio wp`. This skill stages PHP-readable files at `<site-path>/.wpbakery-migration/` and cleans them up on the way out.
2. **`studio wp eval-file -` (stdin heredoc) can silently no-op** — it returns exit 0 with no output and no error, but the database is unchanged. Always pass a real file path, and always have the PHP echo a sentinel line that the caller greps for. Trust nothing without the sentinel.

## Why everything goes through `studio wp`, not bare `wp`

This skill invokes WP-CLI via `studio wp [...] --path=<site-path>`, **not** bare `wp --path=<site-path>`. Studio sites use SQLite as the database, and the Studio-managed `wp` wrapper handles that connection — bare `wp` from the host shell will fail or connect to nothing useful. The CLI surface used here is documented at https://developer.wordpress.com/docs/developer-tools/studio/cli/.

Relevant Studio CLI subcommands this skill uses:

| Command | What it does |
|---|---|
| `studio site status --path=<path>` | Prints details for a site, including its Local URL and run state. Used to validate the user-supplied site path and capture the local URL. |
| `studio site start --path=<path>` | Starts the site if stopped. Required before `studio wp` will work. |
| `studio wp <wp-cli args> --path=<path>` | Runs a WP-CLI command in the Studio site's context. Supports every standard WP-CLI command. |

Every `studio` command also accepts running without `--path=` when the shell's CWD is inside the site directory. The skill prefers explicit `--path=` so the invocation works regardless of where the user is.

## Block markup validation via the Studio MCP `validate_blocks` tool

This skill relies on the Studio MCP server (shipped with the `studio` CLI) for post-conversion validation. The relevant tool is **`validate_blocks`** — under the conventional Claude Code installation it surfaces as `mcp__wordpress-studio__validate_blocks`. Add it once at user scope with:

```bash
claude mcp add --scope user wordpress-studio -- studio mcp
```

What `validate_blocks` does, and why it's the right gate: it loads the converted content into the **site's actual block editor in a headless browser**, runs each block through its real `save()` function, and compares the output to the input. That makes it a *functional* validator, not a structural one — unlike a schema-only validator, it catches class-name hallucinations (e.g. `has-background-color-vivid-red` vs the correct `has-vivid-red-background-color`), attribute-name typos, and any other drift that produces a different `save()` output than the source. Invalid blocks come back with the **expected HTML** from `save()`, which is a concrete fix target.

Inputs: `nameOrPath` (the site path or registered Studio name — the site **must be running**) and either `filePath` (absolute path to a file containing block markup) or `content` (raw block markup string). For this skill, pass `filePath` pointing at the staged converted file inside `<site-path>/.wpbakery-migration/`.

Important constraints and gaps to keep in mind:

- **No pre-emission schema lookup exists in the Studio MCP.** There is no equivalent of `get_block_schema`, `list_block_attributes`, or `get_block_markup`. Attribute names for emitted blocks come from the mappings reference doc and from the model's own knowledge — `validate_blocks` then catches the drift after the fact. The mappings doc is the source of truth; do not invent attribute names beyond what it documents or the standard globals (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `align`).
- **One call per converted file, not per block.** `validate_blocks` accepts the whole content blob and returns per-block results. Walking block-by-block in code is unnecessary; parse the response.
- **Each call spins up a real browser editor.** Calls are not cheap. Run a single validate pass on the full converted content, fix all problems in one editing pass, then re-validate once. Avoid call-per-block loops.

## Preconditions to verify

Run these checks in parallel before doing any work. If any fails, stop and report — don't try to recover silently.

1. **`studio` CLI is installed.** Check with `command -v studio` and `studio --version`. If missing, instruct the user to install Studio from https://developer.wordpress.com/studio/ and stop.
2. **Site path is valid.** Run `studio site status --path=<site-path>`. Non-zero exit (or output indicating Studio doesn't manage this path) = stop and ask the user to supply the correct path. Capture the site's reported Local URL from the status output for use in the preview step.
3. **URL host matches the site.** Compare the host of the user-provided page URL against the Local URL from step 2. If they don't match, stop — the user is asking to convert a page on a different site than the path points at. Do not proceed; let the user reconcile.
4. **Site is running.** If `studio site status` indicates the site is stopped, run `studio site start --path=<site-path>` and wait for it to come up. If start fails, stop.
5. **WP-CLI works against the site.** Run `studio wp core is-installed --path=<site-path>`. Non-zero exit = stop.
6. **Working directory is clean.** Create `<site-path>/.wpbakery-migration/` if it doesn't exist, and remove any leftover files from a prior aborted run (`*.txt`, `*.php` inside it) so stale content can't be reused.
7. **Studio MCP `validate_blocks` is available.** Confirm the tool `mcp__wordpress-studio__validate_blocks` is exposed in the current Claude Code session (it ships with the `studio` CLI's built-in MCP server — see the "Block markup validation" section above for the one-time `claude mcp add` command).

## Procedure

### 1. Resolve URL → post ID

```bash
studio wp eval 'echo url_to_postid("<url>");' --path=<site-path>
```

If the output is `0`, the URL didn't resolve. Stop and ask the user to double-check the URL (likely a non-published draft, a custom post type with non-default rewrites, or a redirect).

### 2. Fetch the current content

```bash
studio wp post get <id> --field=post_content --path=<site-path> > /tmp/wpbakery-original-<id>.txt
```

Also fetch a few attributes for context — `post_title`, `post_status`, `post_type` — to confirm the right post in the preview step:

```bash
studio wp post get <id> --fields=ID,post_title,post_status,post_type --format=json --path=<site-path>
```

The `/tmp/wpbakery-original-<id>.txt` file is the user's audit trail of the pre-conversion content. Rolling back, if needed, is done by the user in the WordPress admin (Revisions panel) — this skill does not script that path.

### 3. Fetch the rendered page and extract WPBakery's compiled CSS

The post content holds shortcodes, but the *visual* styling lives in two places that the raw shortcodes don't fully expose:

- a single `<style type="text/css" data-type="vc_shortcodes-custom-css">` block that WPBakery injects into the rendered page head, containing all `.vc_custom_xxxxx { … }` rules consolidated from the per-shortcode `css=` attributes; and
- the rendered `vc_row` / `vc_column` markup, which carries data attributes (`data-vc-full-width`, `data-vc-stretch-content`) and modifier classes (`vc_row-no-padding`) that the shortcode form encodes only via the `full_width=` attribute.

Fetch the rendered HTML and save both pieces:

```bash
curl -sSL "<url>" -o /tmp/wpbakery-rendered-<id>.html
```

Then extract the WPBakery custom-CSS block (plain CSS, no URL-encoding — easier to map than the `css=` attribute form). Use the **`if`-then-`print` form** — `perl -ne 'print if /.../'` prints *every* line when the regex doesn't match (because `-n` wraps the body in a `while` loop that defaults to printing nothing, but `print` with no args prints `$_`). The form below is the safe one:

```bash
# grep the <style data-type="vc_shortcodes-custom-css"> block out of the rendered HTML
perl -0777 -ne 'if (/<style[^>]*data-type="vc_shortcodes-custom-css"[^>]*>(.*?)<\/style>/s) { print $1 }' \
  /tmp/wpbakery-rendered-<id>.html > /tmp/wpbakery-custom-css-<id>.css

# verify the extraction actually matched — if the file is suspiciously close to the HTML size, the regex missed
wc -c /tmp/wpbakery-rendered-<id>.html /tmp/wpbakery-custom-css-<id>.css
```

If the CSS file size is anywhere near the HTML file size, the regex didn't match and the whole page was copied through — re-check the `data-type` attribute (some themes vary it) and re-run before relying on the extracted CSS.

Use this file during conversion as the **authoritative source for per-shortcode styling**: when a shortcode carries `css=".vc_custom_1234567{...}"`, find the matching `.vc_custom_1234567` rule in the extracted CSS and apply its declarations (padding, margin, background, color, border) to the converted block's `style`/`backgroundColor`/`textColor` attributes per the section 13 decoder rules. The extracted CSS file may also surface styles that would otherwise be missed when the `css=` attribute is malformed or truncated.

If the curl fetch fails (non-200, redirect off-site, authentication wall, page is private/draft), don't stop the run — log it, skip the CSS-extraction step, and fall back to decoding the `css=` attributes inline. Note in the final report that styling fidelity will be lower.

### 4. Verify the post actually contains WPBakery shortcodes

Grep the fetched content for `\[vc_`. If there are zero matches, stop and tell the user the page has no WPBakery shortcodes to convert (it may already be Gutenberg, or use a different page builder). Do not run the rest of the procedure on a clean page.

### 5. Convert

Load `${CLAUDE_SKILL_DIR}/references/shortcode-mappings.md` into context. Walk the original content and rewrite it to Gutenberg block markup, applying the mappings for every `vc_*` shortcode encountered. Specific rules:

- **Walk depth-first** so nested shortcodes (e.g. `vc_row` → `vc_column` → `vc_column_text`) resolve from the inside out.
- **Apply the attribute decoders** in the mappings doc section 13 for `link=`, `font_container=`, and `css=` attributes. Don't guess at the encoded format — follow the documented split rules.
- **Cross-reference `/tmp/wpbakery-custom-css-<id>.css`** for every `.vc_custom_xxxxx` class referenced by a `css=` attribute. The compiled CSS file is the source of truth for what each `vc_custom_*` class applies; the inline `css=` form is just URL-encoded duplication.
- **`vc_row` has four variants** (normal, stretch row, stretch row+content, stretch row+content no padding). The shortcode's `full_width=` attribute and the rendered HTML's `data-vc-stretch-content` / `vc_row-no-padding` markers disambiguate them. See section 2 of the mappings doc for the full branch table.
- **Drop visual-effect attributes** (animation, parallax, css_animation_*) silently per the doc's fidelity policy.
- **Long-tail unknown shortcodes** (`vc_*` not in the reference table) → emit as `core/html` containing the original shortcode source, preceded by a `<!-- TODO(wpbakery-migration): unhandled "vc_xyz" -->` comment. Do not invent mappings.
- **Treat the mappings reference doc as the only source of truth for attribute names.** There is no pre-emission schema lookup in the Studio MCP — step 5a catches drift after the fact via `validate_blocks` (which runs the real `save()` and returns the expected HTML for mismatches). To keep the validate-and-fix pass cheap, follow the mappings doc precisely for attribute names and core-block class conventions (e.g. `has-{slug}-background-color`, **not** `has-background-color-{slug}`). Stick to documented globals (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `align`) plus the per-block attrs the mappings doc spells out. Do not invent attribute names.
- **Non-`vc_` shortcodes** (`[contact-form-7 …]`, `[gravityforms …]`, etc.) → pass through unchanged inside their parent block.
- **Preserve `post_title` and all other post meta** — only the `post_content` changes.

Write the result to `/tmp/wpbakery-converted-<id>.txt` (host-side, for the user to inspect later) **and also** copy it into the site-visible working dir:

```bash
cp /tmp/wpbakery-converted-<id>.txt <site-path>/.wpbakery-migration/converted-<id>.txt
```

### 5a. Validate the converted content before the DB write

Skip this step only if precondition #7 reported `validate_blocks` unavailable. Otherwise, call the Studio MCP tool **once** on the staged file:

```
mcp__wordpress-studio__validate_blocks
  nameOrPath: <site-path>
  filePath:   <site-path>/.wpbakery-migration/converted-<id>.txt
```

The tool loads the content into the running site's block editor, runs each block through its real `save()` function, and returns per-block results. For every block that comes back as invalid, the response includes the **expected HTML** produced by `save()` — that is the concrete fix target.

Walk the per-block results and apply this triage:

- **Valid** → keep as-is.
- **Invalid, expected HTML differs from input by a recoverable amount** (attribute name typo, class-name ordering like `has-background-color-vivid-red` → `has-vivid-red-background-color`, missing/extra wrapper class) → **replace the offending block in the converted file with the expected HTML** from the response. This is the canonical fix path — the editor itself has already told you what the block should look like.
- **Invalid and the diff is large or structural** (block name doesn't exist, deeply nested mismatch the editor flattens away, content the editor refuses to render) → **downgrade that block to `core/html`** wrapping the original `vc_*` shortcode source, preceded by `<!-- TODO(wpbakery-migration): block failed validation — please review -->`. Do not silently emit invalid markup.

After applying all fixes, rewrite both `/tmp/wpbakery-converted-<id>.txt` and the staged `<site-path>/.wpbakery-migration/converted-<id>.txt`, then **call `validate_blocks` one more time** to confirm the fixes didn't introduce new failures. If the second pass still shows invalid blocks, downgrade each remaining offender to `core/html` (do not loop endlessly — two rounds maximum).

Keep a running count of `(validated_ok, auto_fixed_from_expected_html, downgraded_to_html)` to surface in step 7. The DB write in step 6 must consume the post-fix content, not the pre-validation draft.

Cost note: each `validate_blocks` call spins up a real browser editor, so it is not free. The two-call ceiling above (initial + one re-validate) is deliberate; do not call per-block.

### 6. Write back (creates a revision)

**Do not use** `studio wp post update --post_content="$(< file)"` — `$(< file)` is bounded by `ARG_MAX` (~256KB on macOS) and tends to mangle multi-line block markup at the shell layer.
**Do not use** `studio wp eval-file -` with a stdin heredoc — that form can return exit 0 with no output while leaving the database unchanged, and no error is surfaced.

Use a staged PHP script inside the site directory, with a sentinel echo for verification. The canonical template lives at `${CLAUDE_SKILL_DIR}/scripts/update-post-content.php.tmpl` — copy it into the site dir and substitute `__POST_ID__` with the actual post ID:

```bash
sed "s/__POST_ID__/<id>/g" "${CLAUDE_SKILL_DIR}/scripts/update-post-content.php.tmpl" \
  > <site-path>/.wpbakery-migration/update-<id>.php
```

The template reads `converted-<id>.txt` from the same directory via `__DIR__`, calls `wp_update_post`, and echoes `WPBM_OK id=<id> bytes=N` on success or `WPBM_FAIL: <reason>` on failure. Do not reinvent this inline.

Run it and grep for the sentinel — anything other than a matched `WPBM_OK` line is a failure, regardless of exit code:

```bash
studio wp eval-file .wpbakery-migration/update-<id>.php --path=<site-path> 2>&1 | tee /tmp/wpbakery-update-<id>.log
grep -q '^WPBM_OK id=<id>' /tmp/wpbakery-update-<id>.log || { echo "WRITE FAILED — see log"; exit 1; }
```

Path note: `studio wp eval-file` resolves the script path relative to the site directory (NOT the host CWD, and NOT `/tmp/`). Pass a path relative to `<site-path>`. The `__DIR__` inside the script then correctly resolves to `<site-path>/.wpbakery-migration/`.

Unrelated SQLite/Yoast warnings ("WordPress database error … wp_yoast_indexable") are common during `wp_update_post` on Studio sites and do not indicate the update failed — that's why this step greps for the sentinel rather than checking stderr emptiness.

### 6a. Verify the write actually landed

Sentinel-grep is necessary but not sufficient — the script could echo OK and the DB write could still be intercepted. Re-read the post and check the first bytes have changed:

```bash
studio wp post get <id> --field=post_content --path=<site-path> | head -c 200
```

The output must start with `<!-- wp:` (block markup), NOT `[vc_` (the original shortcodes). If `[vc_` is still present, the write did not take effect — stop and surface the failure; do not report success.

### 6b. Smoke-test the rendered page

Fetch the page again and check it still renders without fatal errors:

```bash
curl -sSL -o /dev/null -w "%{http_code}\n" "<url>"
curl -sSL "<url>" | grep -ciE 'fatal error|parse error|wsod|wordpress (database )?error' || true
```

A non-200 status, or a non-zero error-string count, means the converted markup broke the page — surface it in the report so the user knows to inspect before publishing.

### 6c. Clean up the staged files

The PHP script and converted-txt copy inside the site dir are only needed during the write. Remove them so they don't end up in backups, deploys, or git:

```bash
rm -f <site-path>/.wpbakery-migration/update-<id>.php <site-path>/.wpbakery-migration/converted-<id>.txt
```

Leave `/tmp/wpbakery-original-<id>.txt`, `/tmp/wpbakery-converted-<id>.txt`, and `/tmp/wpbakery-custom-css-<id>.css` in place — those are the user's audit trail.

### 7. Report

Summarize, after the write and verification both pass:

- The post that was converted (title + edit URL: `<site-url>/wp-admin/post.php?post=<id>&action=edit`)
- Counts per shortcode handled (e.g. "12 `vc_row`, 28 `vc_column_text`, 4 `vc_btn` …")
- `validate_blocks` summary from step 5a: `(validated_ok, auto_fixed_from_expected_html, downgraded_to_html)`. If the Studio MCP tool was unavailable, say so explicitly — do not omit this line.
- TODOs left in the converted content (unhandled `vc_*`, MCP-downgraded blocks, lossy mappings like carousels/charts) so the user knows what to inspect
- The smoke-test result from step 6b (HTTP status + error-string count)
- Path to the pre-conversion content backup at `/tmp/wpbakery-original-<id>.txt`, and a one-line note that revert is done in the WordPress admin via the Revisions panel on the edit screen.

## Things that should stop the run

Each precondition check and each post-write verification (steps 6, 6a, 6b) is a hard gate. If any fails, surface the reason plainly and stop — do not work around a missing precondition or a failed verification. **Never report success when the step-6 sentinel grep, the step-6a re-read, or the step-6b smoke test fails**, even if every other step looked fine. The user is driving this and needs to know exactly what was checked and what wasn't.
