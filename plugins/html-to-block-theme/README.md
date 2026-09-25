# html-to-block-theme

Convert a set of static **Claude Design** HTML/CSS/JS files into a standards-driven **WordPress block theme** on a local WordPress Studio site.

The agent maps the design to WordPress primitives — templates, template parts, block patterns, `theme.json`, block styles, and page content — rather than reproducing it with hand-written CSS. It plans a blueprint first, then builds section by section and refines its output against the originals in a real browser until it matches as closely as possible.

## What it does

- **Plans before building.** Analyses every HTML file (and its linked CSS/JS) and writes a blueprint that maps each section to core blocks, maps custom CSS classes to block styles, and records where any behaviour beyond core comes from.
- **`theme.json` is the source of truth.** Design tokens (colours, typography, spacing, layout widths) are unified across the whole design set into `theme.json`.
- **Minimal custom CSS.** Styling is expressed first through block supports, then through block style variations registered in `functions.php` with `register_block_style()`. Any block CSS is split into one file per block type under `assets/css/blocks/` and loaded on demand with `wp_enqueue_block_style()` — never a monolithic stylesheet. Hand-written CSS is a last resort and every rule is reported.
- **Custom blocks kept to a minimum, from the blocks monorepo.** Behaviour beyond core supports tries core features first: patterns, Block Bindings, the Interactivity API on existing blocks, variations and filters.
  - **Reuse:** failing those, the skill reuses a block from the [A8C Special Projects blocks monorepo](https://github.com/a8cteam51/special-projects-blocks-monorepo). It installs the block's release ZIP and styles it from the theme.
  - **New block:** only when nothing fits does it build a new, project-agnostic `a8csp/` block in a local monorepo clone, then check it in the newest Twenty-* theme and draft its New block proposal. Pushing, the pull request and the proposal wait for your approval.
  - **Never in a theme:** it never creates a block in a theme.
- **Refines against the originals.** Uses the Claude in Chrome browser extension to screenshot the original design and the WordPress output in real Chrome tabs at matched viewports, then iterates.
- **Works inside an A8C Special Projects project repository.** When the Studio site's `wp-content` is a clone of a repository generated from [`a8cteam51/a8csp-project-template`](https://github.com/a8cteam51/a8csp-project-template), the skill switches to *template mode* and builds into that repository's theme and features mu-plugin under its conventions (see [Template mode](#template-mode)).

## Prerequisites

- **WordPress Studio** with the `studio` CLI on your `PATH` — <https://developer.wordpress.com/studio/>
- A Studio site with a minimal block-theme scaffold the agent can take over (the skill can scaffold one via the Studio MCP if absent).
- **Google Chrome with the Claude in Chrome extension**, connected to your Claude Code session and granted site permission for `localhost` / `127.0.0.1` (both the served design files and the Studio site are local). The refine phase drives your real browser — expect tabs to open and close.
- **Python 3** (`python3`) — used by `serve-html.sh` to serve the design files locally, and by `monorepo-blocks.sh`.
- **git**, for the blocks monorepo catalog and clone. The GitHub CLI (`gh`), when signed in, is used for release lookups; otherwise the public GitHub API is.
- **Node/npm and Composer**, only when a run builds a new block in the monorepo.
- **Studio MCP server**, registered once at user scope (it ships with the `studio` CLI):

  ```bash
  claude mcp add --scope user wordpress-studio -- studio mcp
  ```

  This exposes the block validator (`validate_blocks`), `take_screenshot`, and `scaffold_theme`.

Browser checks use the Claude in Chrome extension's MCP tools (`mcp__claude-in-chrome__*`) directly — the plugin no longer bundles a browser MCP server.

## Usage

Point the skill at the directory of design files and (optionally) the target Studio site:

> Build a block theme from the designs in `./design` on my Studio site `my-theme-dev`.

The skill then:

1. Verifies preconditions (Studio CLI, site running, MCP tools, theme scaffold, clean working dir).
2. Writes a blueprint to `<site-path>/.h2bt/blueprint.md` and surfaces it for review.
3. Builds the `theme.json` foundation, template parts and block styles, and installs or builds the blocks the blueprint calls for.
4. Builds each file section by section, validates the block markup, and refines it against the original in Chrome.
5. Reports per-file fidelity, residual drift, custom CSS used (and why), and every block beyond core with its source (and why).

## Inputs

- **Design directory** (required) — a folder of static `.html` files plus their linked `.css` / `.js` / image / font assets.
- **Studio site** (optional) — path or name. If omitted, it is inferred from `studio site list --format=json`.
- **Project repository** (optional) — an `a8csp-project-template` repository to build into. If the site's `wp-content` isn't a clone of it yet, the skill sets that up with the [`studio-repo-clone`](../studio-repo-clone) plugin first.

## Template mode

`scripts/detect-project-template.sh` recognises a project-template clone by its `mu-plugins/mu-loader.php` and its `a8csp/configs` dependency. It then reads the identifiers the template makes permanent: the theme slug and text domain, the PHP prefix from `.phpcs.xml`, the features mu-plugin, and the PHP, WordPress and Node floors.

The build then follows `references/project-template-guide.md`.

**Where things go:**
- The template's `functions.php` loader stays. Theme code goes in `includes/*.php`, root styles in `assets/sass/`, block CSS in `assets/css/src/blocks/*.scss` (built to `assets/css/build/blocks/`), and theme JS in ES modules under `assets/js/src/`.
- Blocks come from the blocks monorepo, as in standalone runs. Only an exclusion an engineering lead has approved goes in the features mu-plugin: `scaffold-custom-block.sh --exclusion-approved` writes wp-scripts sources, registers them from a blocks manifest, and adds them to `.github/blocks-allowlist`.
- The template's example features (Book CPT, WooCommerce cart stylesheet) are removed with their own recipes.

**How it's checked:**
- `scripts/standards-audit.sh` detects the template layout.
- `scripts/template-checks.sh --repo <wp-content> [--tests] [--e2e]` runs the repository's CI gates: build integrity, blocks allowlist, PHPCS and PHPStan, ESLint and stylelint, PHPUnit in wp-env, and Playwright. It runs them from a mirror of the tracked files, because the Studio site's `wp-content` also holds Studio's own runtime files.
- `scripts/parity-check.sh` takes pixel-exact full-page baselines and compares against them. Use it before porting a finished standalone build into a template repository or running auto-fixers; the guide ends with that porting recipe.

**Extra prerequisites:**
- Node at the repository's `engines.node`.
- A PHP CLI at the repository's PHP floor for Composer. Studio's own builds under `~/.studio/php-bin/` work.
- Docker, only for the wp-env test suites.

The skill works on a feature branch and never commits to `trunk` or `develop`, which deploy. It pushes and opens a draft PR only when you allow it.

## Notes

- All WP-CLI runs go through `studio wp ... --path=<site>` (Studio sites use SQLite); never bare `wp`.
- Page-content writes are SQLite-serial and use a sentinel-verified staged PHP script — do not parallelise them.
