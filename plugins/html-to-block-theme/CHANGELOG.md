# Changelog

## [Unreleased]

### Added
- `scripts/write-page.sh` — wraps the whole sentinel-verified page write (stage markup inside the site dir, fill the `write-page-content.php.tmpl` placeholders, run `studio wp eval-file`, grep for `H2BT_OK`) in one command; its exit code is derived from the sentinel. Replaces the inline sed recipe in the `section-builder` agent.
- Run lessons: the skill now reads `<site-path>/.h2bt/lessons.md` at the start of a run and appends corrections/confirmed approaches at the end, so lessons persist across runs (Fable 5 memory-system pattern).

### Changed
- Prompt-fit pass for Claude Fable 5:
  - Deduplicated rules across the skill, references, and agents — each rule (core/html policy, one-CSS-file-per-block, homepage rule, validation ceiling) now has one canonical statement with pointers elsewhere.
  - The blueprint review gate is explicit: present the blueprint, ask for approval, and end the turn (or proceed and flag it when the user asked for an unattended run).
  - The serial-build rule's rationale now covers template-only files too (shared theme files and the shared live site, not just SQLite writes), so it can't be "safely" parallelized.
  - `blueprint-analyzer` runs on Opus (`model: opus`) instead of pinning Sonnet — the blueprint is the build contract and warrants the stronger model.

### Fixed
- Two leftover references to the old split validator names (`validate_html_blocks` / `validate_and_fix_blocks`) in the skill's precondition check and `mapping-guide.md` — a literal precondition check against those names would fail on current Studio versions.
- The homepage is never built as `templates/front-page.html`. It is now a WordPress page (block markup in `post_content`) set as the static front page through the Reading settings (`show_on_front=page`, `page_on_front`), assigned to the shared page template or a custom page template registered in `theme.json` `customTemplates`. Updated `mapping-guide.md` (new homepage rule), `standards.md`, the skill, and both subagents.
- `standards-audit.sh` fails (`front_page=1`) when the theme ships `templates/front-page.html`.
- Documented the **core/html policy** the Studio validator enforces (`mapping-guide.md`, `standards.md`, skill, `section-builder`): `core/html` is allowed only for bare inline SVG, third-party embed markup with no block equivalent, or a single script block; icon links are `core/social-links` with a block style variation for bespoke glyphs.
- `block-styles-guide.md` gains a **CSS-hook decision rule**: structural rung-4 CSS targets block selectors directly (wrapper classes, contextual combinators); any custom class used as a CSS hook must be a registered block style (`register_block_style()` + `is-style-*`) — including responsive utilities like pull-ups and breakpoint hides. Unregistered bespoke classNames as CSS hooks are a violation (also enforced as a standards rule).
- `theme-json-guide.md` documents **slug kebab-expansion**: WordPress kebab-cases preset slugs when generating CSS custom properties and classes (`type-h1` → `--wp--preset--font-size--type-h-1`), so slugs should be written in fully-expanded kebab form up front.
- Updated the Studio validator tool references to the current combined `mcp__wordpress-studio__validate_blocks` (replacing the split `validate_html_blocks` / `validate_and_fix_blocks` names).

## [0.2.0] - 2026-06-10

### Changed
- Block style variations are now registered in `functions.php` with `register_block_style()` instead of `/styles/*.json` files.
- Block CSS is split into **one file per block type** under `assets/css/blocks/<block-name>.css` (e.g. `core-button.css`) and loaded on demand with [`wp_enqueue_block_style()`](https://developer.wordpress.org/reference/functions/wp_enqueue_block_style/) — replacing the previous single-stylesheet approach. CSS now loads only when its block renders.
- `standards-audit.sh` enforces the new layout: it fails (`css_org` > 0) when a block CSS file is not enqueued via `wp_enqueue_block_style()` or when block CSS lives outside `assets/css/blocks/`.
- Updated `block-styles-guide.md`, `mapping-guide.md`, `standards.md`, the `html-to-block-theme` skill, and the `section-builder` agent to document the PHP-registration + per-block-CSS workflow.

## [0.1.0] - 2026-06-09

### Added
- Initial release.
- `html-to-block-theme` skill: end-to-end orchestrator that converts a set of static HTML/CSS/JS design files into a WordPress block theme on a local Studio site. Plans a blueprint first, then builds section by section and refines against the originals with Playwright.
- Reference guides: HTML→block mapping and the fidelity escalation ladder, `theme.json` token extraction, block style variations as `/styles/*.json`, build-less custom blocks, WordPress standards, and the Playwright visual-refinement loop.
- Subagents: `blueprint-analyzer` (read-only, parallel per file) and `section-builder` (serial, builds one file's templates/page content and refines it).
- Scripts: `serve-html.sh` (static server for the design set), `scaffold-custom-block.sh` (build-less block skeleton), `write-page-content.php.tmpl` (sentinel-verified page write), and `standards-audit.sh` (inline-comment and custom-CSS audit).
- Bundled Playwright MCP via `.mcp.json` for browser-driven visual comparison.
