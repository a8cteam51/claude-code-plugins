# Changelog

## [1.0.0] - 2026-08-28

### Added

- Initial release.
- `setup` skill: connect Claude Code to a WordPress site running the AI-Canvas plugin — prerequisite checks (WP 6.9+, block theme, HTTPS), install of `mcp-adapter` (≥ 0.6.1) and `ai-canvas` from GitHub releases, dedicated Editor user + Application Password, Authorization-header passthrough verification, `claude mcp add` registration (direct HTTP or `mcp-wordpress-remote` proxy fallback), end-to-end smoke test.
- `vibe` skill: drive the six AI-Canvas MCP tools well when building pages — fragment/scoping rules for `index.html`/`style.css`/`script.js`, read-before-write and verify-on-the-live-URL workflow, Media Library usage, live-write semantics, failure-mode reference.
