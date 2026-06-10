# html-to-block-theme

Convert a set of static **Claude Design** HTML/CSS/JS files into a standards-driven **WordPress block theme** on a local WordPress Studio site.

The agent maps the design to WordPress primitives — templates, template parts, block patterns, `theme.json`, block styles, and page content — rather than reproducing it with hand-written CSS. It plans a blueprint first, then builds section by section and refines its output against the originals in a real browser until it matches as closely as possible.

## What it does

- **Plans before building.** Analyses every HTML file (and its linked CSS/JS) and writes a blueprint that maps each section to core blocks, maps custom CSS classes to block styles, and lists any custom blocks needed for behaviour beyond core.
- **`theme.json` is the source of truth.** Design tokens (colours, typography, spacing, layout widths) are unified across the whole design set into `theme.json`.
- **Minimal custom CSS.** Styling is expressed first through block supports, then through block style variations registered in `functions.php` with `register_block_style()`. Any block CSS is split into one file per block type under `assets/css/blocks/` and loaded on demand with `wp_enqueue_block_style()` — never a monolithic stylesheet. Hand-written CSS is a last resort and every rule is reported.
- **Build-less custom blocks.** When core blocks cannot express a behaviour, a custom block is scaffolded with `block.json` + PHP `render.php` + vanilla `view.js` / the Interactivity API — no node/webpack build step.
- **Refines against the originals.** Uses the bundled Playwright MCP to screenshot the original design and the WordPress output at matched viewports, then iterates.

## Prerequisites

- **WordPress Studio** with the `studio` CLI on your `PATH` — <https://developer.wordpress.com/studio/>
- A Studio site with a minimal block-theme scaffold the agent can take over (the skill can scaffold one via the Studio MCP if absent).
- **Node.js / `npx`** available (the bundled Playwright MCP runs via `npx -y @playwright/mcp@latest`).
- **Studio MCP server**, registered once at user scope (it ships with the `studio` CLI):

  ```bash
  claude mcp add --scope user wordpress-studio -- studio mcp
  ```

  This exposes the block-validation tools (`validate_html_blocks`, `validate_and_fix_blocks`), `take_screenshot`, and `scaffold_theme`.

The Playwright MCP is **bundled** with this plugin via `.mcp.json` — no separate install step.

## Usage

Point the skill at the directory of design files and (optionally) the target Studio site:

> Build a block theme from the designs in `./design` on my Studio site `my-theme-dev`.

The skill then:

1. Verifies preconditions (Studio CLI, site running, MCP tools, theme scaffold, clean working dir).
2. Writes a blueprint to `<site-path>/.h2bt/blueprint.md` and surfaces it for review.
3. Builds the `theme.json` foundation, template parts, block styles, and any custom blocks.
4. Builds each file section by section, validates the block markup, and refines it against the original in Playwright.
5. Reports per-file fidelity, residual drift, custom CSS used (and why), and custom blocks created (and why).

## Inputs

- **Design directory** (required) — a folder of static `.html` files plus their linked `.css` / `.js` / image / font assets.
- **Studio site** (optional) — path or name. If omitted, it is inferred from `studio site list --format=json`.

## Notes

- All WP-CLI runs go through `studio wp ... --path=<site>` (Studio sites use SQLite); never bare `wp`.
- Page-content writes are SQLite-serial and use a sentinel-verified staged PHP script — do not parallelise them.
