# Changelog

## [2.1.0] - 2026-09-17

### Added

- `vibe` skill gains a "Build accessible pages" section, distilled from the Special Projects designer handbook's accessibility guidelines and QA checklist and filtered to what a single HTML block controls. Target is WCAG 2.1 AA on the first write (AAA only on request, and stated): computed contrast for every pairing (4.5:1 text, 3:1 large text and UI boundaries), no information or state by color alone, a scrim under text on swappable hero photos, 16px body text at 1.5 line height in 50–80 character measures, no justified text or text-as-image, one `<h1>` per page (posts start at `<h2>`), DOM order as reading order, descriptive link text and new-tab labelling, alt text in the block and on `wp.sh upload --alt`, `prefers-reduced-motion` on every animation with no parallax or flashing, 44px targets 8px apart, a `:focus-visible` ring restated per section, keyboard behaviour and no-JS-true ARIA state on widgets, and labelled forms with associated, announced errors. Landmarks are template-aware: the framed template already provides `<main>` and the theme's skip link, while the blank template's content is a bare Post Content block, so the block supplies `<header>`, `<main>`, `<footer>`, and a skip link itself.
- Browser verification now includes an accessibility pass: tab through the page checking order and focus visibility, read the accessibility tree for heading order, names, and duplicate `main`, check target size at phone width, and run an automated audit when the session offers one. Without browser tools the skill reports keyboard and focus as untested and checks the rest from source.

- `wp.sh contrast FG BG [FG BG ...]`: WCAG contrast ratio for hex color pairs in bash and awk, no site needed. Reports the ratio (truncated, so 4.499 never reads as 4.5) and pass/FAIL against 4.5 (text), 3 (large text and UI), and 7 (AAA text). The skill runs the whole palette through it instead of estimating.
- When a color the user asked for fails contrast, the skill flags it in plain words and offers options (nearest passing shade, brand color for large text and decoration only, or as asked) rather than silently changing it; the user decides, once.

### Changed

- The `<button>`-based widget rule moved from "Keep pages fast" into the new section.

## [2.0.0] - 2026-09-10

### Changed

- **Rewritten around the WordPress REST API and the core Custom HTML block.** The AI-Canvas WordPress plugin and the MCP Adapter are no longer used; a site needs only [Jamie's Visual HTML Editor](https://wordpress.org/plugins/jamies-visual-html-editor/), which gives the Custom HTML block full-width alignment and lets the site owner click text and images to edit them in wp-admin. Each page or post body is one `<!-- wp:html {"align":"full"} -->` block carrying `<style data-wp-block-html="css">`, `<script data-wp-block-html="js">`, and a single scoped root element.
- `setup` skill: guides a beginner through installing the visual HTML editor plugin, creating an Editor user and an Application Password, then saves the connection with `wp.sh add-site` and verifies credentials and capabilities (`publish_pages`, `publish_posts`, `upload_files`, `unfiltered_html`) with `wp.sh me`. No MCP registration, no session restart.
- `vibe` skill: creates and updates pages and posts through `scripts/wp.sh`; read-before-write; undo through WordPress revisions (`revisions` lists, `restore` sends one back; `create` re-saves once so the first version is recorded, since core skips revisions on insert); `wp.sh check` verifies the public page is served with its style and script intact and reports whether the full-width wrapper is present (which doubles as detection of the visual editor plugin); Claude-in-Chrome verification loop, performance rules, and plain-language reporting carried over. Posts ask once whether to publish or draft. Markup is kept human-editable (plain text elements and `<img>` tags, `data-vc-bg` on hero backgrounds).

### Added

- Page templates over REST. `wp.sh template-ensure` reads the theme's `page` template, copies its header and footer template parts, and creates **AI Canvas (with header and footer)** and **AI Canvas (blank)** as custom `wp_template` posts. The framed template's Post Content block is `align: full`, otherwise the constrained `main` group squeezes it to the theme's content width and the page's own `alignfull` cannot escape; `templates`, `template-get`, and `template-delete` support it. The setup skill runs it once per site; the vibe skill passes `--template ai-canvas-framed|ai-canvas-blank` on every new page, chosen from the brief or one plain question. Because templates need `edit_theme_options`, the connection user is now an **Administrator** (was Editor) and block themes are required (classic themes unsupported).
- `scripts/wp.sh`: REST client needing only `bash` and `curl` (no Python, Node, or jq). Credentials live in one curl config file per site under `~/.claude/ai-canvas/sites/` (mode 600), read with `curl -K`, so the Application Password never appears on a command line after setup. Content is sent as a multipart form field, so nothing is JSON-encoded client-side; `get` decodes the JSON string in awk, including `\uXXXX` and surrogate pairs. Uses `?rest_route=` so plain permalinks work. Commands: `sites`, `add-site`, `remove-site`, `me`, `find`, `get`, `create`, `update`, `revisions`, `restore`, `trash`, `media`, `upload`, `check`.

- `wp.sh check` reports `script_ampersand_rewritten`: `wptexturize` leaves `<script>` text alone but treats any bare `<` in the block (`i < 10`) as the start of a tag running to the next `>`, and rewrites every `&` in that span to `&#038;`, so `&&` becomes a syntax error on the served page while the stored content looks fine. The vibe skill documents the rule (no bare `<` in script, style, or text), the DOM-ready wrapper the block's script needs because it is printed above the markup it queries, and the need to restate font, color, and text-transform on headings, links, and buttons that block themes style directly.
- The vibe skill requires a no-JS-complete block: the visual HTML editor plugin injects the block's markup into wp-admin's "Edit content" view, where injected `<script>` tags never execute, so any state only JS can leave (`opacity: 0` before a scroll reveal, hidden tab panels) is written under `.canvas-x.is-js`, a class the script adds to the root as its first act. Sections were rendering blank in the editor while the front end looked fine. The skill also documents the editor signal: no WordPress global exists inside the editor iframe (`wp`, `pagenow` live in the parent document), so `.editor-styles-wrapper` ancestor / `root.closest('.editor-styles-wrapper')` is the check for anything that must differ in the editor, and the browser verification loop now includes the edit view for pages with JS-driven states.

### Removed

- The `PreToolUse` guard hook and `scripts/guard-mcp-endpoint.py`; there is no MCP endpoint to guard.
- All dependence on the AI-Canvas WordPress plugin, the MCP Adapter, `claude mcp add`, and `@automattic/mcp-wordpress-remote`.

## [1.3.0] - 2026-08-28

### Added

- `PreToolUse` guard hook (`hooks/hooks.json` + `scripts/guard-mcp-endpoint.py`) that denies direct HTTP access to any `/wp-json/ai-canvas/mcp` endpoint — authenticated/protocol-level Bash commands (curl with auth, headers, bodies, method overrides, `jsonrpc`/`tools/call` payloads, HTTP-library one-liners) and Write/Edit of helper scripts embedding the endpoint plus call/auth material. The setup skill's unauthenticated status probe, `claude mcp …` commands, and Markdown docs are explicitly allowed; the deny message routes the agent to the real fix (user runs `/mcp` or restarts the session). Fails open on unexpected input; requires only `python3`.

### Changed

- `vibe` skill gains a "MCP tools only — no exceptions" section born from a real session where the agent, finding a mid-session-registered server's tools absent, started rebuilding the connection out of curl and stored credentials. New rules: canvas content moves only through `mcp__<server>__ai-canvas-*` tools; missing tools mean the user must run `/mcp` or restart (there is no workaround to attempt); a preflight matches the tool prefix to the intended site when multiple ai-canvas servers are registered (`claude mcp list` shows each URL — diagnosis only, never a content route); mid-task auth/connection failures are reported, not downgraded to HTTP. The `curl` verification fallback is now explicitly scoped to the public page URL, and the failure-mode table covers missing tools and stale connections.
- `setup` skill: B4 now pre-checks `claude mcp list` for existing ai-canvas registrations and resolves naming with the user (replace, or site-suffixed name) so server names map unambiguously to sites; after registration the Application Password / `Authorization` header never appears in conversation again; B5 states plainly that tools will not appear mid-session (expected, not a failure — user runs `/mcp` or restarts) and forbids bridging the gap over HTTP; A4 forbids hunting for missing inputs through other tooling instead of asking the user. Troubleshooting table covers both new symptoms.

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
