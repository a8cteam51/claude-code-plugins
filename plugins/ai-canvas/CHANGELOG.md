# Changelog

## [1.2.0] - 2026-08-28

### Added

- Plugin README covering both skills, the non-technical-user posture, and site requirements; ai-canvas section added to the marketplace README.

### Changed

- `vibe` skill now directs the agent to check its own work with Claude in Chrome when the browser tools are available: open the canvas URL in a dedicated tab, screenshot and inspect the render between the theme header/footer (catching CSS scoping violations), exercise `script.js` interactions and read the console for errors, do a phone-width check on layout-heavy pages, and iterate read → write → reload → re-screenshot. `curl` remains the fallback, reported as markup-only verification.
- Both skills reworked for non-technical users. `vibe`: report in page terms (link + screenshot, never filenames or jargon), translate every error into plain language before showing it, at most one round of brief questions (checking the Media Library for brand assets first), and infer real copy from whatever was given instead of lorem ipsum — flagging invented specifics for correction. `setup`: assume a beginner from the start (one step at a time, literal wp-admin labels, no jargon), risk-warning gate removed, the Application Password is the only credential (with plain-terms storage/revoke reassurance; the placeholder-`!` alternative is gone), Authorization-header fixes are routed through hosting support, and the registration command is always run by the agent.
- `vibe` skill documents instant undo via the new `rollback-file` tool (requires companion WordPress plugin ≥ 0.2.0): every `write-file` retains one previous version per file, `rollback-file` swaps it live, and swapping again re-does.
- `vibe` skill gains a "Keep pages fast" section distilled from auditing a real vibe-coded landing page: reference right-sized image variants (`upload-media`/`list-media` now return dimensions and generated sizes, plugin ≥ 0.2.0), explicit `width`/`height` on every image, below-fold-only lazy-loading with an eager `fetchpriority="high"` hero, IntersectionObserver-driven video playback and sticky/reveal effects instead of layout-reading scroll handlers, literal HTML over client-side templating, and `<button>`-based ARIA widgets proven working in the browser. The phone-width verification check now looks specifically for overflow and pixel-positioned decoration that breaks on small screens.

## [1.1.0] - 2026-08-28

### Changed

- `setup` skill reworked around a strict role split: Claude guides the user through every site-changing step (plugin installs, connection user, Application Password) without executing any of it, then automates the rest once it has the site URL and credentials — endpoint check, auth/header verification, REST capability check (including `unfiltered_html`), and `claude mcp add` registration.
- Added a capability verification step (`/wp/v2/users/me?context=edit`) so missing `unfiltered_html` (multisite, `DISALLOW_UNFILTERED_HTML`) is caught during setup instead of at first write.

## [1.0.0] - 2026-08-28

### Added

- Initial release.
- `setup` skill: connect Claude Code to a WordPress site running the AI-Canvas plugin — prerequisite checks (WP 6.9+, block theme, HTTPS), install of `mcp-adapter` (≥ 0.6.1) and `ai-canvas` from GitHub releases, dedicated Editor user + Application Password, Authorization-header passthrough verification, `claude mcp add` registration (direct HTTP or `mcp-wordpress-remote` proxy fallback), end-to-end smoke test.
- `vibe` skill: drive the six AI-Canvas MCP tools well when building pages — fragment/scoping rules for `index.html`/`style.css`/`script.js`, read-before-write and verify-on-the-live-URL workflow, Media Library usage, live-write semantics, failure-mode reference.
