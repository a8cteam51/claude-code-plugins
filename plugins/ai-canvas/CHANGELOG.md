# Changelog

## [1.1.0] - 2026-08-28

### Changed

- `setup` skill reworked around a strict role split: Claude guides the user through every site-changing step (plugin installs, connection user, Application Password) without executing any of it, then automates the rest once it has the site URL and credentials — endpoint check, auth/header verification, REST capability check (including `unfiltered_html`), and `claude mcp add` registration.
- Added a capability verification step (`/wp/v2/users/me?context=edit`) so missing `unfiltered_html` (multisite, `DISALLOW_UNFILTERED_HTML`) is caught during setup instead of at first write.

## [1.0.0] - 2026-08-28

### Added

- Initial release.
- `setup` skill: connect Claude Code to a WordPress site running the AI-Canvas plugin — prerequisite checks (WP 6.9+, block theme, HTTPS), install of `mcp-adapter` (≥ 0.6.1) and `ai-canvas` from GitHub releases, dedicated Editor user + Application Password, Authorization-header passthrough verification, `claude mcp add` registration (direct HTTP or `mcp-wordpress-remote` proxy fallback), end-to-end smoke test.
- `vibe` skill: drive the six AI-Canvas MCP tools well when building pages — fragment/scoping rules for `index.html`/`style.css`/`script.js`, read-before-write and verify-on-the-live-URL workflow, Media Library usage, live-write semantics, failure-mode reference.
