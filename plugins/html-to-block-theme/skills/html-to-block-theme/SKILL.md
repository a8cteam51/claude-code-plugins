---
name: html-to-block-theme
description: This skill should be used when the user asks to "build a block theme from this HTML", "turn these designs into a WordPress theme", "convert this Claude Design output to a block theme", "make a WordPress theme from these HTML files", "make this design into a real WordPress site", or otherwise requests turning static HTML/CSS/JS design files into a WordPress block theme on a local WordPress Studio site. Triggers when static HTML/CSS design files (or a directory of them) are supplied alongside any HTML→block-theme conversion intent.
---

# Build a WordPress block theme from a set of static HTML designs

End-to-end conversion of a directory of static Claude Design files (HTML + linked CSS + JS + assets) into a standards-driven WordPress **block theme** on a local Studio site. The output reproduces the designs as closely as possible using WordPress primitives — `theme.json`, templates, template parts, block patterns, block styles, and page content — not hand-written CSS.

Work in phases and **do not skip the blueprint**. Plan the whole mapping first, get it on disk, then build section by section and refine each section against the original in a real browser. The reference guides under `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/` are the source of truth for every mapping, standards, and tooling decision — load the relevant one before acting in each phase.

## Inputs

- **Design directory** (required) — absolute path to a folder of static `.html` files plus their linked `.css`, `.js`, image, and font assets. The user provides this.
- **Studio site** (optional but preferred) — path or registered name of the target Studio site. If the user provides a path, use it as-is. If they don't, infer it from `studio site list --format=json` (match a sensible name, or ask if ambiguous). The site has a minimal block-theme scaffold the agent fully controls.

## Critical environment quirks

These will silently corrupt output if missed (inherited from the Studio environment — same constraints the `wpbakery-to-gutenberg` skill documents):

1. **Use `studio wp ... --path=<site>`, never bare `wp`.** Studio sites use SQLite; the Studio-managed `wp` wrapper handles that connection. Bare `wp` from the host shell connects to nothing useful.
2. **Studio's `wp` runs in a sandbox that cannot see the host `/tmp/`.** Any file PHP must read inside `studio wp eval-file` must live **inside the site directory**. This skill stages such files at `<site-path>/.h2bt/` and cleans them up.
3. **`studio wp eval-file -` (stdin heredoc) can silently no-op** — exit 0, no output, database unchanged. Always pass a real file path and have the PHP echo a sentinel line the caller greps for. Trust nothing without the sentinel.
4. **Page-content writes are SQLite-serial.** Never dispatch concurrent `section-builder` subagents that write to the database — concurrent `wp_update_post`/`wp_insert_post` under SQLite trips Yoast indexable errors and corrupts results. Build one file at a time.

## Tooling

This skill uses two MCP servers plus the `studio` CLI.

- **Playwright MCP** — bundled with this plugin via `.mcp.json` (runs `npx -y @playwright/mcp@latest`). Used to load the original HTML (served locally) and the WordPress output, screenshot both at matched viewports, and inspect DOM/computed styles. See `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/visual-refinement.md`.
- **Studio MCP** — ships with the `studio` CLI; register once at user scope: `claude mcp add --scope user wordpress-studio -- studio mcp`. Relevant tools (confirm exact names in-session before relying on them — older docs reference a since-renamed `validate_blocks`):
  - `mcp__wordpress-studio__validate_html_blocks` — load block markup into the real editor and report invalid blocks with the expected `save()` HTML.
  - `mcp__wordpress-studio__validate_and_fix_blocks` — the auto-fix counterpart. Two-call ceiling: validate, fix in one pass, re-validate once; never loop per block.
  - `mcp__wordpress-studio__take_screenshot` — fallback screenshotter if Playwright is unavailable.
  - `mcp__wordpress-studio__scaffold_theme` — scaffold a minimal block theme if the site has none.

## Preconditions to verify

Run these in parallel before any work. If any fails, stop and report — do not work around a missing precondition.

1. **`studio` CLI installed.** `command -v studio` and `studio --version`. If missing, point the user to https://developer.wordpress.com/studio/ and stop.
2. **Site resolves and is valid.** `studio site status --path=<site-path>` exits zero; capture the site's Local URL for the refine phase.
3. **Site is running.** If stopped, `studio site start --path=<site-path>` and wait. If start fails, stop.
4. **WP-CLI works.** `studio wp core is-installed --path=<site-path>` exits zero.
5. **Theme scaffold present, and bind `<theme-dir>`.** Confirm the active theme is a block theme with at least `style.css`, `theme.json`, and `templates/index.html`. If absent, offer to scaffold via `mcp__wordpress-studio__scaffold_theme` and proceed only once it exists. Capture its absolute path once and reuse it as `<theme-dir>` for the rest of the run: `studio wp theme path <active-theme-slug> --dir --path=<site-path>` (or the scaffold tool's reported path).
6. **MCP tools and subagents exposed.** Confirm the Playwright tools and the Studio `validate_html_blocks` / `validate_and_fix_blocks` tools are available in the session, and that the `html-to-block-theme:blueprint-analyzer` and `html-to-block-theme:section-builder` subagent types resolve (they ship with this plugin). If a subagent type is unavailable, fall back to dispatching a `general-purpose` subagent with the same instructions.
7. **Design directory exists** and contains at least one `.html` file. Glob the linked assets so later phases know what to route.
8. **Clean working dir.** Create `<site-path>/.h2bt/` and remove leftovers from any prior aborted run.

## Procedure

### Phase 1 — Analyze and blueprint (plan the map first)

1. Start a local static server for the design set so relative assets resolve:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --dir "<design-dir>"
   ```

   It starts a background server and prints one sentinel line: `H2BT_SERVE url=<base-url> pid=<pid> pidfile=<path>`. Parse it — capture `<base-url>` (each design file is then reachable at `<base-url><file>.html`) and `<pidfile>` (needed to stop the server in Phase 4).

2. Dispatch one **`blueprint-analyzer`** subagent **per HTML file, in parallel** (these are read-only — parallel is safe and fast). Use the Agent tool with `subagent_type: "html-to-block-theme:blueprint-analyzer"`, passing the file path, the served URL, and the design directory. Each returns the structured JSON described in that agent's definition: section list, per-section block mapping with the chosen escalation-ladder rung, custom-CSS-class → block-style candidates, custom-block candidates (with "why core can't"), the file's classification (core template vs shared-wrapper page content), and the design tokens it detected.

3. **Reconcile** all analyzer outputs into one blueprint. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/mapping-guide.md` and `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md` for the rules. Decide:
   - A single unified token set for `theme.json` (merge near-duplicate colours/sizes; one source of truth).
   - The shared chrome (header/footer/nav present across files) → template parts.
   - Repeated cross-file sections → block patterns.
   - Each file's target: core templates (`templates/index.html`, `single.html`, `archive.html`, `404.html`, `front-page.html`, …) vs inner pages that share a wrapper template and differ only in content → a WordPress page assigned to that template.
   - The list of custom blocks to build, each justified against core.

4. Write the blueprint to `<site-path>/.h2bt/blueprint.md` (a per-file target table, the token set, the part/pattern/custom-block lists, and the per-section mapping). **Surface it to the user and let them review before building** — this is the build contract.

### Phase 2 — Foundation (theme.json is the source of truth)

Build the shared foundation once, before any per-file content. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, `block-styles-guide.md`, and `custom-blocks-guide.md`.

1. Write `theme.json` from the unified token set: palette, typography/`fontFamilies`, spacing scale, layout `contentSize`/`wideSize`, radii/shadows, and element styles.
2. Create template parts for the shared chrome (`parts/header.html`, `parts/footer.html`, etc.).
3. Register block styles in **`functions.php` via `register_block_style()`** — one per mapped custom CSS class. Put each block type's CSS in **its own file** at `assets/css/blocks/<block-name>.css` (the block name's `/` becomes `-`, e.g. `core-button.css`) and load it on demand with **`wp_enqueue_block_style()`**. One CSS file per block type — never a monolithic stylesheet, and not `/styles/*.json` block-style files. See `block-styles-guide.md`.
4. Scaffold each needed custom block build-less and register it from the theme:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold-custom-block.sh" --theme-dir "<theme-dir>" --slug "<block-slug>" --title "<Block Title>"
   ```

5. Route assets: fonts → `theme.json` `fontFamilies` with files copied into `assets/fonts/`; content images → media library (`studio wp media import ...`); decorative/background images → theme `assets/`.

### Phase 3 — Build and refine, section by section (serial)

Process the files **one at a time** (serial — see quirk 4). For each file, dispatch a **`section-builder`** subagent via the Agent tool with `subagent_type: "html-to-block-theme:section-builder"`, passing the blueprint, that file's target, the site path, the theme dir, the served original URL, and the site's Local URL. The subagent (per its definition):

- Emits Gutenberg block markup using **only `<!-- wp -->` comments** (no other inline comments) for each section, applying the escalation ladder from `mapping-guide.md`.
- For core templates: writes `templates/*.html` / `parts/*.html`.
- For shared-wrapper pages: creates/updates a WordPress page whose `post_content` is the block markup, assigned to the shared template, via the sentinel-verified staged write (`${CLAUDE_PLUGIN_ROOT}/scripts/write-page-content.php.tmpl`).
- Validates the markup with `validate_html_blocks` → `validate_and_fix_blocks` (two-call ceiling).
- Refines against the original in Playwright per `visual-refinement.md`: screenshot original vs WP output at matched viewports, compare per section, apply the ladder for mismatches, converge in ~3 rounds max, and record residual drift rather than looping.

Collect each subagent's JSON result (target built, validation summary, drift list, custom CSS used, TODOs) before starting the next file.

### Phase 4 — Verify and report

1. Full-page visual diff per file at desktop + the responsive breakpoints the designs define.
2. Block-validity summary across all files.
3. Standards audit:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/standards-audit.sh" --theme-dir "<theme-dir>"
   ```

   It must report zero non-`<!-- wp -->` inline comments (`stray_comments=0`), zero block-CSS organization violations (`css_org=0` — every block CSS file is one-per-block-type under `assets/css/blocks/` and enqueued via `wp_enqueue_block_style()`), and an itemised, minimal custom-CSS footprint. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/standards.md` for what counts as a violation.
4. Report (see below). Stop the static server (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --stop --pidfile <pidfile>`) so it doesn't leak, and clean up transient staged files in `<site-path>/.h2bt/`, leaving `blueprint.md` as the audit trail.

## Report

After Phase 4, summarise:

- The theme built (name + path) and the per-file target table from the blueprint (what became a template, a part, a pattern, or a page).
- Per-file fidelity at each viewport, and the **residual drift list** — every detail that did not match 1:1 and why.
- **Every custom CSS rule written and why** (which ladder rung it sits on), plus the total custom-CSS footprint from the audit.
- **Custom blocks created and why** each was needed beyond core.
- Block-validation summary (`validated_ok`, `auto_fixed`, `downgraded`).
- TODOs the user should inspect (lossy mappings, dropped animations, JS not yet ported).

## Things that should stop the run

Each precondition and each post-write verification is a hard gate. Never report success when a page-content write's sentinel grep fails, when block validation still shows invalid blocks after the two-call ceiling (downgrade to `core/html` instead), or when the standards audit reports stray inline comments or block-CSS organization violations. Surface the reason plainly and stop — the user is driving this and needs to know exactly what was checked.
