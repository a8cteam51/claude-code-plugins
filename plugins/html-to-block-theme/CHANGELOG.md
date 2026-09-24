# Changelog

## [0.3.0] - 2026-09-24

### Added
- **Template mode** for repositories generated from `a8cteam51/a8csp-project-template`. The skill switches to it when the Studio site's `wp-content` is a clone of such a repository, and builds into that repository's theme and features mu-plugin under its conventions. Worked out while porting the missamychan.com build into `a8cteam51/missamychan-2026`.
  - `references/project-template-guide.md` covers:
    - detection and preconditions: feature branch, PHP floor, toolchain, dependencies;
    - the identifiers the template makes permanent, and the theme contract its tests encode;
    - where each part of the build goes, and the build pipeline;
    - removing the template's example features;
    - what fails the template's CI and how to fix it;
    - the checks, the parity guard, content and dependency handling, and delivery;
    - a recipe for porting an existing standalone build.
  - `scripts/detect-project-template.sh` identifies a template clone and prints its theme slug, PHP prefix, text domains, features plugin, floors and leftover example features as an `H2BT_TEMPLATE` sentinel.
  - `scripts/template-checks.sh` runs the repository's CI gates: build integrity, blocks allowlist, `composer lint:php`, `npm run lint`, and optionally the wp-env PHPUnit and Playwright suites.
    - **Why it uses a mirror:** the checks run from a mirror of the tracked files, because a Studio site's `wp-content` also holds Studio's SQLite integration and loader, which the lint scripts and wp-env would otherwise pick up.
    - **Tooling:** it picks a PHP CLI that meets the floor, using Studio's `~/.studio/php-bin` builds as a fallback.
    - **wp-env safety:** it refuses ports another wp-env instance publishes, and waits for theme activation before the end-to-end run.
  - `scripts/parity-check.sh` takes a pixel-exact full-page baseline and later compares against it: reduced motion, animations disabled, lazy images loaded, popups suppressed through `localStorage`. It uses the repository's own `@playwright/test` with local Chrome. Use it to prove a port or an auto-fix changed nothing.
- `scaffold-custom-block.sh --layout template` scaffolds a custom block into the features mu-plugin:
  - wp-scripts sources with ES modules and JSX, plus a strict-types `render.php` with prefixed variables;
  - manifest registration in `includes/blocks.php`;
  - the `build:features:blocks`/`start:features:blocks` scripts and the lint paths;
  - the `.github/blocks-allowlist` entries CI requires.
- `standards-audit.sh --layout auto|standalone|template`. Template mode, detected automatically, checks one `assets/css/src/blocks/*.scss` source per block type, built to `assets/css/build/blocks/` and enqueued from `functions.php` or `includes/*.php`. It flags unbuilt, orphaned and stray stylesheets, and lists per-purpose stylesheets for review.
- `scripts/write-page.sh` — wraps the whole sentinel-verified page write (stage markup inside the site dir, fill the `write-page-content.php.tmpl` placeholders, run `studio wp eval-file`, grep for `H2BT_OK`) in one command; its exit code is derived from the sentinel. Replaces the inline sed recipe in the `section-builder` agent.
- Run lessons: the skill now reads `<site-path>/.h2bt/lessons.md` at the start of a run and appends corrections/confirmed approaches at the end, so lessons persist across runs (Fable 5 memory-system pattern).
- Ported field-tested lessons from the first three full conversion runs (July 2026) into the reference guides:
  - `mapping-guide.md`: `blockGap` accepts only preset form (raw custom vars silently fall back to 24px); attribute `minHeight` is un-overridable inline style; a **Layout traps** section (root/template-part/stacked-columns default-gap drift, constrained-layout clamping of oversized absolute children); **core/navigation notes** (navigation-link `className` styling, portable path-based active state, logo/CTA in the native mobile overlay); native `<details name>` accordion groups; a **Forms (Jetpack)** section (offline module availability on Studio, composed field blocks, the `is-style-default` label-suppression quirk).
  - `theme-json-guide.md`: variable-font condensed cuts via a second `fontStretch` fontFamily; Fontsource `standard` (not `full`) multi-axis filenames; a **Responsive token overrides** section (`:root:root` in `style.css` beats global styles).
  - `block-styles-guide.md`: the audit requires literal per-file enqueues incl. the `.css` suffix (no glob loops); variations for blocks with `supports.className: false` scope as `p.is-style-x`, not `.wp-block-paragraph.is-style-x`.
  - `standards.md`: block themes don't auto-enqueue `style.css` — explicit `wp_enqueue_style()` + `add_editor_style()` required.
  - `custom-blocks-guide.md`: **Dynamic content from meta** (Block Bindings custom sources, the empty-`<p>` trap, `render_block_core/post-date` filter, ServerSideRender preview).
  - `visual-refinement.md`: lazy-image capture race (`document.images[].complete`); re-assert window size after navigation.
  - Skill quirk 4: quiet file activity is not a section-builder completion signal — wait for the agent notification.

### Changed
- The standards audit's CSS footprint now excludes comments properly (`/* */`, and `//` in SCSS), so the theme-header comment no longer counts toward the total.
- SKILL.md, `section-builder`, `blueprint-analyzer` and the block-styles, custom-blocks and standards guides point to the template guide when template mode is on. Section builders rebuild their sources before reloading the browser.
- Browser checks now use the **Claude in Chrome** extension's MCP tools (`mcp__claude-in-chrome__*`) instead of a bundled Playwright MCP:
  - Removed the `.mcp.json` Playwright server; Node.js/`npx` is no longer a prerequisite — Chrome with the Claude in Chrome extension (connected, with `localhost`/`127.0.0.1` site permission) is, plus `python3` for `serve-html.sh`.
  - Rewrote `visual-refinement.md` for the Chrome tools: two dedicated tabs in one shared window (a single `resize_window` matches both viewports), viewport-only screenshots (scroll each section into view; no full-page capture), `javascript_tool` for computed-style spot-checks, `read_console_messages` for `view.js` errors, and tab cleanup when a file is done.
  - Updated the skill's Tooling/preconditions, the `section-builder` refine phase, the README, and the plugin/marketplace descriptions accordingly. The refine phase now drives the user's real browser, so tabs visibly open and close during a run.
- Prompt-fit pass for Claude Fable 5:
  - Deduplicated rules across the skill, references, and agents — each rule (core/html policy, one-CSS-file-per-block, homepage rule, validation ceiling) now has one canonical statement with pointers elsewhere.
  - The blueprint review gate is explicit: present the blueprint, ask for approval, and end the turn (or proceed and flag it when the user asked for an unattended run).
  - The serial-build rule's rationale now covers template-only files too (shared theme files and the shared live site, not just SQLite writes), so it can't be "safely" parallelized.
  - `blueprint-analyzer` runs on Opus (`model: opus`) instead of pinning Sonnet — the blueprint is the build contract and warrants the stronger model.

### Fixed
- Leftover references to the old split validator names (`validate_html_blocks` / `validate_and_fix_blocks`) in the skill's precondition check, `mapping-guide.md`, and the README — a literal precondition check against those names would fail on current Studio versions.
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
