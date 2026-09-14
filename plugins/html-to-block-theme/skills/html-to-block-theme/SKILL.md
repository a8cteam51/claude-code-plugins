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
4. **Build files serially — all of them, not just page-content writes.** Concurrent `wp_update_post`/`wp_insert_post` under SQLite trips Yoast indexable errors and corrupts results, and every builder also mutates shared theme files (`functions.php`, `theme.json`, block CSS) and refines against the same live site — a parallel builder would screenshot another's half-applied changes. So template-only files are serial too. One `section-builder` at a time — and "no file writes for a while" is **not** a completion signal (builders go quiet for long stretches during browser refinement); wait for the agent's completion notification before dispatching the next.

## Tooling

This skill uses two MCP tool sets plus the `studio` CLI.

- **Claude in Chrome** — the Claude in Chrome browser extension's MCP tools (`mcp__claude-in-chrome__*`); the extension must be installed, connected to the session, and granted access to `localhost`/`127.0.0.1` sites. Used to load the original HTML (served locally) and the WordPress output in real Chrome tabs, screenshot both at matched viewports, and inspect DOM/computed styles. If the tools are deferred in-session, load the whole needed set in a **single** ToolSearch call. See `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/visual-refinement.md`.
- **Studio MCP** — ships with the `studio` CLI; register once at user scope: `claude mcp add --scope user wordpress-studio -- studio mcp`. Relevant tools (confirm exact names in-session before relying on them — the validator has been renamed across Studio versions, e.g. earlier split `validate_html_blocks` / `validate_and_fix_blocks` tools):
  - `mcp__wordpress-studio__validate_blocks` — the combined validator: a static core/html policy check (policy: `mapping-guide.md`) followed by validation in the site's real block editor. Usage rules — argument forms, the two-call ceiling, what to do with rejects — live in the `section-builder` agent, which is what calls it.
  - `mcp__wordpress-studio__take_screenshot` — fallback screenshotter for the WordPress side if the Claude in Chrome extension is unavailable.
  - `mcp__wordpress-studio__scaffold_theme` — scaffold a minimal block theme if the site has none.

## Preconditions to verify

Run these in parallel before any work. If any fails, stop and report — do not work around a missing precondition.

1. **`studio` CLI installed.** `command -v studio` and `studio --version`. If missing, point the user to https://developer.wordpress.com/studio/ and stop.
2. **Site resolves and is valid.** `studio site status --path=<site-path>` exits zero; capture the site's Local URL for the refine phase.
3. **Site is running.** If stopped, `studio site start --path=<site-path>` and wait. If start fails, stop.
4. **WP-CLI works.** `studio wp core is-installed --path=<site-path>` exits zero.
5. **Theme scaffold present, and bind `<theme-dir>`.** Confirm the active theme is a block theme with at least `style.css`, `theme.json`, and `templates/index.html`. If absent, offer to scaffold via `mcp__wordpress-studio__scaffold_theme` and proceed only once it exists. Capture its absolute path once and reuse it as `<theme-dir>` for the rest of the run: `studio wp theme path <active-theme-slug> --dir --path=<site-path>` (or the scaffold tool's reported path).
6. **MCP tools and subagents exposed.** Confirm the Claude in Chrome browser tools (`mcp__claude-in-chrome__*` — if deferred, load them with one ToolSearch call) and the Studio validator (`validate_blocks`, or whatever name the installed Studio version exposes — see Tooling) are available in the session, and that the `html-to-block-theme:blueprint-analyzer` and `html-to-block-theme:section-builder` subagent types resolve (they ship with this plugin). If a subagent type is unavailable, fall back to dispatching a `general-purpose` subagent with the same instructions.
7. **Design directory exists** and contains at least one `.html` file. Glob the linked assets so later phases know what to route.
8. **Clean working dir, read prior lessons.** Create `<site-path>/.h2bt/` and remove leftover staged files from any prior aborted run — but keep `lessons.md` and read it if present: it holds lessons recorded by previous runs against this site and environment, and they apply to this run.

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
   - Each file's target: core templates (`templates/index.html`, `single.html`, `archive.html`, `404.html`, …) vs pages that share a wrapper template and differ only in content → a WordPress page assigned to that template. **The homepage is always a page, never `templates/front-page.html`** — template choice and Reading-settings wiring per the homepage rule in `mapping-guide.md`.
   - The list of custom blocks to build, each justified against core.

4. Write the blueprint to `<site-path>/.h2bt/blueprint.md` (a per-file target table, the token set, the part/pattern/custom-block lists, and the per-section mapping). **Present a summary to the user, ask them to approve or amend it, and end the turn** — the blueprint is the build contract, and Phase 2 starts only on their approval. Do not end the turn on a promise to build. Exception: when the user has already said to run without check-ins, proceed directly and flag in the final report that the blueprint was applied unreviewed.

### Phase 2 — Foundation (theme.json is the source of truth)

Build the shared foundation once, before any per-file content. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, `block-styles-guide.md`, and `custom-blocks-guide.md`.

1. Write `theme.json` from the unified token set: palette, typography/`fontFamilies`, spacing scale, layout `contentSize`/`wideSize`, radii/shadows, and element styles.
2. Create template parts for the shared chrome (`parts/header.html`, `parts/footer.html`, etc.).
3. Register block styles per `block-styles-guide.md` — `register_block_style()` in `functions.php` (one variation per mapped custom CSS class), with one CSS file per block type under `assets/css/blocks/`, enqueued via `wp_enqueue_block_style()`.
4. Scaffold each needed custom block build-less and register it from the theme:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold-custom-block.sh" --theme-dir "<theme-dir>" --slug "<block-slug>" --title "<Block Title>"
   ```

5. Route assets: fonts → `theme.json` `fontFamilies` with files copied into `assets/fonts/`; content images → media library (`studio wp media import ...`); decorative/background images → theme `assets/`.

### Phase 3 — Build and refine, section by section (serial)

Process the files **one at a time** (serial — see quirk 4). For each file, dispatch a **`section-builder`** subagent via the Agent tool with `subagent_type: "html-to-block-theme:section-builder"`, passing the blueprint, that file's target, the site path, the theme dir, the served original URL, and the site's Local URL. The subagent (per its definition):

- Emits Gutenberg block markup using **only `<!-- wp -->` comments** (no other inline comments) for each section, applying the escalation ladder from `mapping-guide.md`.
- For core templates: writes `templates/*.html` / `parts/*.html`.
- For shared-wrapper pages: creates/updates a WordPress page whose `post_content` is the block markup, assigned to the shared template, via the sentinel-verified `${CLAUDE_PLUGIN_ROOT}/scripts/write-page.sh`.
- Validates the markup with the Studio validator (`validate_blocks` — policy check + editor validation, two-call ceiling).
- Refines against the original in Chrome per `visual-refinement.md`: screenshot original vs WP output at matched viewports, compare per section, apply the ladder for mismatches, converge in ~3 rounds max, and record residual drift rather than looping. Ends with a `1900px` wide-desktop sanity check pass on the WordPress output.

Collect each subagent's JSON result (target built, validation summary, drift list, custom CSS used, TODOs) before starting the next file.

### Phase 4 — Verify and report

1. Full-page visual diff per file at desktop + the responsive breakpoints the designs define, plus the `1900px` wide-desktop sanity check on each page.
2. Block-validity summary across all files.
3. Standards audit:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/standards-audit.sh" --theme-dir "<theme-dir>"
   ```

   It must report zero non-`<!-- wp -->` inline comments (`stray_comments=0`), zero block-CSS organization violations (`css_org=0` — every block CSS file is one-per-block-type under `assets/css/blocks/` and enqueued via `wp_enqueue_block_style()`), and an itemised, minimal custom-CSS footprint. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/standards.md` for what counts as a violation.
4. **Record lessons.** Append to `<site-path>/.h2bt/lessons.md` anything a future run of this skill should know — corrections, confirmed approaches, environment quirks discovered this run. One lesson per entry, a one-line summary first, then why it mattered. Don't record what `blueprint.md` or the theme itself already captures; update an existing entry rather than duplicating it, and delete entries this run proved wrong.
5. Report (see below). Stop the static server (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --stop --pidfile <pidfile>`) so it doesn't leak, and clean up transient staged files in `<site-path>/.h2bt/`, leaving `blueprint.md` and `lessons.md` as the audit trail.

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
