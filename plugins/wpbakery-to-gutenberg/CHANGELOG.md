# Changelog

## [0.1.0] - 2026-05-18

### Added
- Initial release
- `wpbakery-to-gutenberg` skill for in-place conversion of a single WPBakery (Visual Composer) page on a local WordPress Studio site to Gutenberg block markup
- `references/shortcode-mappings.md` as the source of truth for `vc_*` shortcode → block mappings, including the attribute decoders for `link=`, `font_container=`, and `css=`
- `scripts/update-post-content.php.tmpl` for the post-content write-back, staged inside the site directory and verified via a sentinel-line grep (works around `studio wp eval-file -` silently no-op'ing on stdin heredocs)
- Pre-write extraction of WPBakery's compiled `<style data-type="vc_shortcodes-custom-css">` block so per-shortcode `.vc_custom_*` styling can be applied to the converted block attributes
- Post-conversion validation pass via the Studio MCP `validate_blocks` tool (runs each block through the editor's real `save()` and returns the expected HTML for mismatches), with a two-call ceiling and automatic downgrade to `core/html` for unrecoverable blocks
- Pre-write revision capture so the final report's rollback line points at an unambiguous revision ID
