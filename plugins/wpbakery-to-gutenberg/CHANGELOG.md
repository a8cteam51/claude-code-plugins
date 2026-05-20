# Changelog

## [0.2.0] - 2026-05-20

### Added
- `/wpbakery-to-gutenberg:wpbakery-batch` slash command for multi-page conversion runs on a Studio site. Discovers candidate posts via a single `wp db query` against `wp_posts` LIKE `'%[vc_%'`, resolves permalinks in one batched `wp eval`, and asks the user to scope the run via `AskUserQuestion` (Convert all / Pick specific IDs / Filter by post type / Dry run).
- Per-page work in the batch command is delegated to **one subagent per post (serial)** so the orchestrator's context window only holds the candidate list and per-post JSON summaries — never the post content, rendered HTML, or block markup.
- Continue-on-error policy for batch runs: per-post failures are recorded and the batch keeps going. A single Markdown report is written to `/tmp/wpbakery-batch-<timestamp>-report.md` with a summary table, per-post results, outstanding TODOs, and backup-file paths.

### Changed
- The single-page skill no longer captures pre/post-write revision IDs and no longer prints a rollback command in its final report. Rationale: in practice users revert via the WP admin Revisions panel; scripting that path was carrying weight it didn't earn. The pre-conversion `post_content` is still saved to `/tmp/wpbakery-original-<id>.txt` as an audit trail.

## [0.1.0] - 2026-05-18

### Added
- Initial release
- `wpbakery-to-gutenberg` skill for in-place conversion of a single WPBakery (Visual Composer) page on a local WordPress Studio site to Gutenberg block markup
- `references/shortcode-mappings.md` as the source of truth for `vc_*` shortcode → block mappings, including the attribute decoders for `link=`, `font_container=`, and `css=`
- `scripts/update-post-content.php.tmpl` for the post-content write-back, staged inside the site directory and verified via a sentinel-line grep (works around `studio wp eval-file -` silently no-op'ing on stdin heredocs)
- Pre-write extraction of WPBakery's compiled `<style data-type="vc_shortcodes-custom-css">` block so per-shortcode `.vc_custom_*` styling can be applied to the converted block attributes
- Post-conversion validation pass via the Studio MCP `validate_blocks` tool (runs each block through the editor's real `save()` and returns the expected HTML for mismatches), with a two-call ceiling and automatic downgrade to `core/html` for unrecoverable blocks
- Pre-write revision capture so the final report's rollback line points at an unambiguous revision ID
