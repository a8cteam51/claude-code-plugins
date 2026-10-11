---
name: html-to-block-theme
description: This skill should be used when the user asks to "build a block theme from this HTML", "turn these designs into a WordPress theme", "convert this Claude Design output to a block theme", "make a WordPress theme from these HTML files", "make this design into a real WordPress site", "convert this site to a block theme", "rebuild this live site as a block theme", or otherwise requests turning static HTML/CSS/JS design files, or the pages of an existing live site, into a WordPress block theme on a local WordPress Studio site — including building into, or porting a finished build into, a project repository generated from a8cteam51/a8csp-project-template. Triggers when static HTML/CSS design files (or a directory of them), or the address of a site to rebuild, are supplied alongside any HTML→block-theme conversion intent.
---

# Build a WordPress block theme from a set of static HTML designs

End-to-end conversion of a directory of static Claude Design files (HTML + linked CSS + JS + assets) into a standards-driven WordPress **block theme** on a local Studio site. The output reproduces the designs as closely as possible using WordPress primitives — `theme.json`, templates, template parts, block styles, and page content an editor can change — not hand-written CSS. Custom behaviour comes from core features first, then from the A8C Special Projects blocks monorepo; the skill never creates a block inside a theme.

Work in phases and **do not skip the blueprint**. Plan the whole mapping first, get it on disk, then build section by section and refine each section against the original in a real browser. The reference guides under `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/` are the source of truth for every mapping, standards, and tooling decision — load the relevant one before acting in each phase.

## Inputs

- **Design directory** (required) — absolute path to a folder of static `.html` files plus their linked `.css`, `.js`, image, and font assets. The user provides this.
- **Or a live site to rebuild.** When the source is a running site, load `references/live-site-guide.md` first: it says what to ask, how to mirror the pages into a design directory, and how to treat the original's defects. The mirror is then the design directory for the rest of the run.
- **Project repository** (optional) — a repository generated from `a8cteam51/a8csp-project-template`. When the Studio site's `wp-content` is a clone of one, the run is in **template mode** (detected in Preconditions): it builds into that repository's theme and features mu-plugin under the template's conventions, per `references/project-template-guide.md`.
- **Studio site** (optional but preferred) — path or registered name of the target Studio site. If the user provides a path, use it as-is. If they don't, infer it from `studio site list --format=json` (match a sensible name, or ask if ambiguous). The site has a minimal block-theme scaffold the agent fully controls.

## Critical environment quirks

These will silently corrupt output if missed (inherited from the Studio environment — same constraints the `wpbakery-to-gutenberg` skill documents):

1. **Use `studio wp ... --path=<site>`, never bare `wp`.** Studio sites use SQLite; the Studio-managed `wp` wrapper handles that connection. Bare `wp` from the host shell connects to nothing useful.
2. **Studio's `wp` runs in a sandbox that cannot see the host `/tmp/`.** Any file PHP must read inside `studio wp eval-file` must live **inside the site directory**. This skill stages such files at `<site-path>/.h2bt/` and cleans them up.
3. **`studio wp eval-file -` (stdin heredoc) can silently no-op** — exit 0, no output, database unchanged. Always pass a real file path and have the PHP echo a sentinel line the caller greps for. Trust nothing without the sentinel.
4. **Build files serially — all of them, not just page-content writes.** Concurrent `wp_update_post`/`wp_insert_post` under SQLite trips Yoast indexable errors and corrupts results, and every builder also mutates shared theme files (`functions.php`, `theme.json`, block CSS) and refines against the same live site — a parallel builder would screenshot another's half-applied changes. So template-only files are serial too. One `section-builder` at a time — and "no file writes for a while" is **not** a completion signal (builders go quiet for long stretches during browser refinement); wait for the agent's completion notification before dispatching the next.
5. **`studio wp` output is not a clean value.** Under a newer PHP the `studio` CLI can print PHP deprecation notices on standard output, so `$(studio wp … --field=…)` captures a notice. Read values with an `eval-file` script that prints one sentinel line. And the Studio MCP's WP-CLI tool is not a drop-in for `studio wp`: it can run a different PHP version from the site's, below which a plugin with a PHP floor loads nothing, with no error.

## Tooling

This skill uses two MCP tool sets, the `studio` CLI, and the blocks monorepo helper.

- **Claude in Chrome** — the Claude in Chrome browser extension's MCP tools (`mcp__claude-in-chrome__*`); the extension must be installed, connected to the session, and granted access to `localhost`/`127.0.0.1` sites. Used to load the original HTML (served locally) and the WordPress output in real Chrome, side by side in the comparison harness at an exact width, to screenshot both, and to measure DOM and computed styles. If the tools are deferred in-session, load the whole needed set in a **single** ToolSearch call. See `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/visual-refinement.md`.
- **Studio MCP** — ships with the `studio` CLI; register once at user scope: `claude mcp add --scope user wordpress-studio -- studio mcp`. Relevant tools (confirm exact names in-session before relying on them — the validator has been renamed across Studio versions, e.g. earlier split `validate_html_blocks` / `validate_and_fix_blocks` tools):
  - `mcp__wordpress-studio__validate_blocks` — the combined validator: a static core/html policy check (policy: `mapping-guide.md`) followed by validation in the site's real block editor. Usage rules — argument forms, the two-call ceiling, what to do with rejects — live in the `section-builder` agent, which is what calls it.
  - `mcp__wordpress-studio__take_screenshot` — fallback screenshotter for the WordPress side if the Claude in Chrome extension is unavailable.
  - `mcp__wordpress-studio__scaffold_theme` — scaffold a minimal block theme if the site has none.
- **Blocks monorepo** — [`a8cteam51/special-projects-blocks-monorepo`](https://github.com/a8cteam51/special-projects-blocks-monorepo), public. `${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh` lists its catalog with each plugin's latest release (`catalog`), installs release ZIPs on the Studio site (`install`), and clones it with its autoloader for building a new block (`clone`). It needs `git` and `python3`, and uses `gh` for release lookups when signed in. Building a new block also needs Node/npm, and Composer for PHPCS. See `custom-blocks-guide.md`.
- **The plugin's own scripts** (`${CLAUDE_PLUGIN_ROOT}/scripts/`):
  - `serve-html.sh` serves the design files with the comparison harness and a results sink (`visual-refinement.md`);
  - `render-probe.sh` renders a block-markup file on the site and prints its HTML and CSS, with no database write (`mapping-guide.md`);
  - `write-page.sh` writes a page, verified by a sentinel;
  - `standards-audit.sh` and, in template mode, `template-checks.sh` and `parity-check.sh` are the gates.

## Preconditions to verify

Run these in parallel before any work. If any fails, stop and report — do not work around a missing precondition.

1. **`studio` CLI installed.** `command -v studio` and `studio --version`. If missing, point the user to https://developer.wordpress.com/studio/ and stop.
2. **Site resolves and is valid.** `studio site status --path=<site-path>` exits zero; capture the site's Local URL for the refine phase.
3. **Site is running.** If stopped, `studio site start --path=<site-path>` and wait. If start fails, stop.
4. **WP-CLI works, and note the core version.** `studio wp core is-installed --path=<site-path>` exits zero. Read the WordPress version (`studio wp core version --path=<site-path>`): attribute forms depend on it, and the per-viewport attributes in `mapping-guide.md` need 7.1 or later. Then turn development mode on for the build: `studio wp config set WP_DEVELOPMENT_MODE theme --path=<site-path>`. WordPress caches a theme's file list and its `theme.json`; without this, deleted or new files show stale results.
5. **Detect the layout.** Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-template.sh" --site-path <site-path>` and read its `H2BT_TEMPLATE` sentinel.
   - `mode=standalone` → continue with step 6 as written. If the user named a project-template repository but the site's `wp-content` is not a clone of it, set that up first with the `studio-repo-clone` plugin (`clone-into-existing-site` keeps the site's database and uploads; `clone-new-site` for a new site), then re-run detection.
   - `mode=template` → load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/project-template-guide.md` and satisfy its Preconditions (feature branch, PHP floor, toolchain, dependencies). Bind `<repo>`, `<theme-dir>` (the sentinel's `theme_dir`), `<features-dir>`, `<prefix>`, and the text domains for the rest of the run. The template ships its theme, so skip scaffolding in step 6; confirm it is active (`studio wp theme activate <theme_slug> --path=<site-path>`) unless you are porting a build that must stay active until its parity baseline is taken.
6. **Theme scaffold present, and bind `<theme-dir>`.** Confirm the active theme is a block theme with at least `style.css`, `theme.json`, and `templates/index.html`. If absent, offer to scaffold via `mcp__wordpress-studio__scaffold_theme` and proceed only once it exists. Capture its absolute path once and reuse it as `<theme-dir>` for the rest of the run: `studio wp theme path <active-theme-slug> --dir --path=<site-path>` (or the scaffold tool's reported path).
7. **MCP tools and subagents exposed.** Confirm the Claude in Chrome browser tools (`mcp__claude-in-chrome__*` — if deferred, load them with one ToolSearch call) and the Studio validator (`validate_blocks`, or whatever name the installed Studio version exposes — see Tooling) are available in the session, and that the `html-to-block-theme:blueprint-analyzer` and `html-to-block-theme:section-builder` subagent types resolve (they ship with this plugin). If a subagent type is unavailable, fall back to dispatching a `general-purpose` subagent with the same instructions.
8. **Design directory exists** and contains at least one `.html` file. Glob the linked assets so later phases know what to route.
9. **Clean working dir, read prior lessons.** Create `<site-path>/.h2bt/` and remove leftover staged files from any prior aborted run — but keep the records a run leaves (`blueprint.md`, `lessons.md`, `plugin-findings.md`, `quirks.md`, `analysis/`, `pages/`, `media.json`) and read `lessons.md` if present: it holds lessons recorded by previous runs against this site and environment, and they apply to this run. A `<site-path>/_h2bt/` folder left by an aborted run is a stale harness copy: remove it.
10. **The session is on the pinned model.** This plugin's guides are checked against one model, `claude-opus-5-5`, and both subagents are pinned to it. The orchestration runs on the session's model, which a skill cannot hold across turns. If this session is on another model, say which, ask the user to switch (`/model claude-opus-5-5`), and stop.

## Procedure

### Phase 1 — Analyze and blueprint (plan the map first)

1. Start a local static server for the design set so relative assets resolve:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --dir "<design-dir>" --site-path "<site-path>"
   ```

   It starts a background server and prints two sentinel lines: `H2BT_SERVE url=<base-url> pid=<pid> pidfile=<path>` and `H2BT_HARNESS url=<harness-url> site_copy=<path> sink=<dir>`. Parse them — capture `<base-url>` (each design file is then reachable at `<base-url><file>.html`), `<pidfile>` (needed to stop the server in Phase 4), and the harness URL and sink directory for the comparisons (`visual-refinement.md`). `--site-path` places a copy of the comparison harness in the site root; stopping the server removes it.

2. Dispatch one **`blueprint-analyzer`** subagent **per HTML file, in parallel** (each changes nothing but its own report — parallel is safe and fast). Use the Agent tool with `subagent_type: "html-to-block-theme:blueprint-analyzer"`, passing the file path, the served URL, the design directory, and a report path (`<site-path>/.h2bt/analysis/<name>.json`). Each writes its full report there and returns a digest of a couple of kilobytes: classification, target, sections with their rung, block-style and behaviour candidates, breakpoints, and open questions. A full report runs to tens of kilobytes, so keep them on disk: read a report only for the facts a decision needs, and give each builder the path to its own. A hand-back that is not the digest, or whose report file does not exist, is not a finished analysis: continue that analyzer as Phase 3 continues a builder.

3. **Reconcile** the analyses into one blueprint. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/mapping-guide.md`, `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, and `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/custom-blocks-guide.md` for the rules. **Every value an analyzer reports is derived from stylesheets, not measured: measure on the rendered original before a value goes into the blueprint or the theme.** Decide:
   - A single unified token set for `theme.json` (merge near-duplicate colours/sizes; one source of truth), with no reserved slug, and whether typography is fluid (`theme-json-guide.md`).
   - The design's two main breakpoints, which become `settings.viewport` on WordPress 7.1 and later as whole pixels, and the list of other widths at which something changes: each of those costs a block style.
   - The design's text column and wide column, which become `contentSize` and `wideSize`. Post content is laid out with them in every template; a section wider than the text column is an aligned block in the page.
   - The shared chrome (header/footer/nav present across files) → template parts.
   - **Where content and images live** (`mapping-guide.md` § Where content lives, § Asset routing). The defaults: nothing a visitor reads is held in a PHP pattern, and design images are media-library items, with Safe SVG as a site dependency when any is an SVG. State both in the summary so the user can change them, with what they bring: no page content in the theme, and a content migration for any other environment.
   - Each file's target: core templates (`templates/index.html`, `single.html`, `archive.html`, `404.html`, …) vs pages that share a wrapper template and differ only in content → a WordPress page assigned to that template. **The homepage is always a page, never `templates/front-page.html`** — template choice and Reading-settings wiring per the homepage rule in `mapping-guide.md`.
   - Where each behaviour comes from, per `custom-blocks-guide.md`: a core route; a monorepo plugin to reuse (run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" catalog` once and check every candidate against it); a new `a8csp/<slug>` block to build in the monorepo; or, in template mode and only when the user states an engineering lead approved it, an exclusion kept in the features plugin. Record why each earlier step fails.
   - What cannot be carried over as it is and needs the user's answer: a control whose accessible name differs from its visible text, and, for a live site, everything `live-site-guide.md` lists.

4. Write the blueprint to `<site-path>/.h2bt/blueprint.md` (a per-file target table with a status column, every file `pending`, the token set and breakpoints, the part list, the content and image decisions, the behaviour table with each behaviour's source, the per-section mapping, and an empty **build notes** section that Phase 3 fills). **Present a summary to the user, ask them to approve or amend it, and end the turn** — the blueprint is the build contract, and Phase 2 starts only on their approval. Do not end the turn on a promise to build. Exception: when the user has already said to run without check-ins, proceed directly and flag in the final report that the blueprint was applied unreviewed.

### After approval — one run, to the report

Phases 2 to 4 are one run. The user approves the blueprint and may not be watching after that, and a message with no tool call in it ends the turn: the work stops there until they come back. So do not end a turn:

- on a summary of what was just built or checked that announces the next step. Take the next step in the same message;
- on an offer to carry on unless the user would prefer otherwise;
- on a list of decisions for the user when none of them blocks the remaining files. Record each in the blueprint's build notes for the report, and carry on with everything it does not block;
- because a phase or a file is finished, or the turn has been long.

Status notes are welcome, in the same message as the next tool call. Waiting for a running builder or analyzer is not an early stop: its completion notification restarts the run. The stops that are wanted are the ones under *Things that should stop the run*, and a question without whose answer nothing can move. Work that waits for the user's approval (a push, a pull request, a block proposal) does not stop the run either: finish everything else and list it in the report. None of this removes a confirmation this skill asks for.

**The target table is the run's checklist.** Set a file's status when its builder is dispatched (`building`) and when its hand-back has been checked (`checked`, or `failed` with the reason). A turn that ends with a file still `pending`, no builder running and no blocker stated has ended early, and the next turn starts from that table.

### Phase 2 — Foundation (theme.json is the source of truth)

Build the shared foundation once, before any per-file content. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, `block-styles-guide.md`, and `custom-blocks-guide.md`.

1. Write `theme.json` from the unified token set: palette, typography/`fontFamilies`, spacing scale, layout `contentSize`/`wideSize`, the two viewport breakpoints, radii/shadows, and element styles. **Every value in pixels is a whole number of pixels,** breakpoints included (`mapping-guide.md` § Pixel values are whole pixels). **Measure which font file draws each weight** before declaring the font faces (`theme-json-guide.md` § Font faces): it cannot be read from the original's stylesheet.
2. Create template parts for the shared chrome (`parts/header.html`, `parts/footer.html`, etc.) as plain block markup. In every template, give `core/post-content` a constrained layout, also where the design is a stack of full-width bands: those are `alignfull` blocks in the page's content (`mapping-guide.md` § Post content sits at content width).
3. Register block styles per `block-styles-guide.md` — `register_block_style()` in `functions.php` (one variation per mapped custom CSS class), with one CSS file per block type under `assets/css/blocks/`, enqueued via `wp_enqueue_block_style()`.
4. Put each behaviour's block in place, per the blueprint and `custom-blocks-guide.md`:
   - **Reused monorepo blocks:** install their release ZIPs with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" install --site-path <site-path> <plugin-dir>...`.
   - **New blocks:** build them in a monorepo clone (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" clone --site-path <site-path>`, then `npm run new-block`, on an `add/<slug>` branch), keep them project-agnostic and wireframe-styled, check them in the newest Twenty-* theme on a throwaway Studio site, add the screenshot, and draft the New block proposal. Pushing the branch, opening the monorepo pull request and filing the proposal wait for the user's approval.
   - **Styling:** style every reused or new block from the theme with its own block stylesheet (`block-styles-guide.md`), and adapt behaviour with project-side filters, never by editing the block.
   - **Approved exclusions** (template mode only): see Template mode below.

5. Route assets per `mapping-guide.md` § Asset routing: fonts → `theme.json` `fontFamilies` with files copied into `assets/fonts/`; design images → the media library, recorded in one manifest (`<site-path>/.h2bt/media.json`) that every builder takes ids from; only the images a template, part or stylesheet itself needs → theme `assets/`.
6. **Write the dynamic pieces a view needs before its builder starts, and test them through a rendered template** (`custom-blocks-guide.md` § Test groundwork): bindings sources, render filters, sample content for a post type.

**Template mode.** `project-template-guide.md` overrides the locations above and adds steps. In short:
- Remove the template's example features by their co-located recipes.
- Replace `theme.json`, the parts and the templates in `<theme-dir>`, and remove the example patterns.
- Put root styles in `assets/sass/` partials.
- Put block CSS in `assets/css/src/blocks/<block>.scss`, registered from `includes/block-styles.php` against the build path.
- Put theme JS in ES modules under `assets/js/src/`.
- Blocks still come from the monorepo. Only an approved exclusion (the user states an engineering lead approved it) is scaffolded into the features mu-plugin, with `scaffold-custom-block.sh --exclusion-approved --features-dir <features-dir> --namespace <theme_slug>`.
- Delete `<features-dir>/.disabled` once the features plugin carries real features.

Run `npm run build` after the foundation and after every source edit, since the site serves built files.

### Phase 3 — Build and refine, section by section (serial)

Process the files **one at a time** (serial — see quirk 4). For each file, dispatch a **`section-builder`** subagent via the Agent tool with `subagent_type: "html-to-block-theme:section-builder"`, passing the blueprint (including its behaviour table and build notes), that file's target, the path to its analysis report, the site path, the theme dir, the served original URL, the harness URL, the media manifest, and the site's Local URL — and in template mode also `layout: template`, `<repo>`, `<features-dir>`, `<prefix>`, the text domains, and the path to `project-template-guide.md`. The subagent (per its definition):

- Emits Gutenberg block markup using **only `<!-- wp -->` comments** (no other inline comments) for each section, applying the escalation ladder from `mapping-guide.md`.
- For core templates: writes `templates/*.html` / `parts/*.html`.
- For shared-wrapper pages: keeps the page's source at `<site-path>/.h2bt/pages/<slug>.html` and creates/updates a WordPress page whose `post_content` is that markup, assigned to the shared template, via the sentinel-verified `${CLAUDE_PLUGIN_ROOT}/scripts/write-page.sh`.
- Validates the markup with the Studio validator (`validate_blocks` — policy check + editor validation, two calls per file: the first draft and the final file).
- Refines against the original in Chrome per `visual-refinement.md`: both pages side by side in the comparison harness at an exact width, compared per section by eye and by measurement, swept across the design's widths, converging in ~3 rounds max and recording residual drift rather than looping. Ends with a `1900px` wide-desktop sanity check and an overflow check at the narrowest width.

Collect each subagent's JSON result (target built, validation summary, drift list, custom CSS used, checks, anything changed outside its view, TODOs) before starting the next file.

**A hand-back that is not that JSON is a progress note, not a result.** So is one that names work it stopped before doing (sections not built, no final validation, widths not swept) with no reason it could not go on. Continue the same builder with `SendMessage`, naming what is open: it keeps its context, and a second builder for the file would start without it. If the session cannot continue an agent, dispatch a new builder with the first one's hand-back and the open items. After two continuations, set the file to `failed` with what is missing, run the hand-back checks below so that the shared files are sound, and go on to the next file.

**Not every view needs a builder.** A page that is one template plus one run of text is generated, validated, written and compared by the orchestrator, and two views of one design come from one generator (`mapping-guide.md` § Long-form and repeated content).

**Carry what each builder learns to the next one.** Builders start without memory, and the next builder copies what exists. After every hand-back:

1. **Check it, don't take it on trust.** Rebuild and confirm the built files do not change, lint the tracked paths, and compare the view at two widths in the harness (document height and overflow on both sides). This is the only window in which the browser and the shared stylesheets are free.
2. **Fix what it reported about shared files** — `changed_outside_view`, drift entries on shared parts, the TODOs — and measure the fix. Budget for this: in practice most hand-backs carry at least one real defect in shared chrome, a token or a shared section.
3. **Rewrite the blueprint's build notes** (what exists and is checked, the authoring procedure that worked, scope reminders, how to compare) **and set the file's status in the target table.**
4. Add the builder's `quirks_fixed` to the register (live sites) and its `plugin_findings` to the findings file (Phase 4, step 5).

While a builder runs, do only work that touches neither the theme, the database nor the browser: documentation, content conversion, the next builder's brief.

### Phase 4 — Verify and report

1. Full-page comparison per file in the harness: a sweep of desktop, the responsive breakpoints the designs define (one pixel either side of each), the narrowest width and `1900px`, for document height, sideways overflow and text; then a look at each page top to bottom at desktop and phone width. Read the `loading` attribute of the largest image on each view's first screen (`standards.md`).
2. Block-validity summary across all files, and one check in the editor itself: open a page per template in the block editor and confirm it loads with no invalid block, that the content's root is constrained, that its full-width sections span the canvas, and that a paragraph inserted at the root is as wide as the content column. Leave the page unsaved.
3. Standards audit:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/standards-audit.sh" --theme-dir "<theme-dir>" --content-dir "<site-path>/.h2bt/pages"
   ```

   It must report zero non-`<!-- wp -->` inline comments (`stray_comments=0`), zero block-CSS organization violations (`css_org=0` — every block CSS file is one-per-block-type under `assets/css/blocks/` and enqueued via `wp_enqueue_block_style()`; in template mode the audit detects the layout itself and checks one `assets/css/src/blocks/*.scss` source per block type, built and enqueued), zero blocks inside the theme (`theme_blocks=0`), no preset slug that collides with a core flag class (`reserved_slugs=0`), no colour that WordPress drops (`dropped_colors=0`), no fraction of a pixel (`subpixel_values=0`), no post content without a constrained layout (`post_content_layout=0`), and an itemised, minimal custom-CSS footprint. It also lists theme-file images that reserve no space (`image_review`): fix or explain each. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/standards.md` for what counts as a violation.
4. **Template mode gates.** Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/template-checks.sh" --repo <repo>` (add `--tests --e2e` when Docker is running). It must end `H2BT_TEMPLATE_CHECKS_OK`; fix each failing gate by the table in `project-template-guide.md` § What fails CI. Take a `parity-check.sh` baseline before running any formatter or auto-fixer, and compare afterwards. Replace the template's example tests with tests of this build's promises. Commit in logical conventional-commit units on the feature branch; push and open a **draft** PR against `trunk` only with the user's permission.
5. **Record lessons, in two files.**
   - `<site-path>/.h2bt/lessons.md`: anything a future run against **this site** should know — corrections, confirmed approaches, environment quirks discovered this run. One lesson per entry, a one-line summary first, then why it mattered. Don't record what `blueprint.md` or the theme itself already captures; update an existing entry rather than duplicating it, and delete entries this run proved wrong.
   - `<site-path>/.h2bt/plugin-findings.md`: what this run learned that applies to **any** site built with this skill, ready to be ported into the plugin's guides. Keep it through the run, not at the end: add each builder's `plugin_findings` as it reports. Nothing in it names the site, its owner or a design value. Each entry says what was observed, how it was checked (or that it was derived and not checked), and which plugin file it changes. Mark an entry that is the user's decision on this project, as opposed to an observation.
6. Report (see below). Stop the static server (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --stop --pidfile <pidfile>`) so it doesn't leak; this also removes the harness copy from the site root. Clean up transient staged files in `<site-path>/.h2bt/`, leaving the run's records: `blueprint.md`, `lessons.md`, `plugin-findings.md`, `analysis/`, `pages/`, `media.json`, and for a live site `quirks.md` and the mirror.

## Report

After Phase 4, summarise:

- The theme built (name + path) and the per-file target table from the blueprint (what became a template, a part, or a page).
- Per-file fidelity at each viewport, and the **residual drift list** — every detail that did not match 1:1 and why.
- **Where the content is.** Page content and design images live in the site's database and media library, not in the theme: another environment gets them by a content migration, and stored image blocks name this environment's attachment ids and URLs. Name the plugins the content depends on (Safe SVG when any image is an SVG).
- **What was not checked:** other browsers, touch devices, screen readers, the editor beyond the pages opened, and anything a local site cannot show (a connected plugin's output, production-scale content).
- **First-screen images:** the `loading` attribute of the largest image on each view's first screen, and whether the theme changes the lazy-loading threshold.
- **Every custom CSS rule written and why** (which ladder rung it sits on), plus the total custom-CSS footprint from the audit.
- **Every block beyond core and where it came from**: each behaviour's source and why the earlier steps failed.
  - Reused monorepo plugins, with their versions.
  - New monorepo blocks: the clone branch, the Twenty-* check result, the screenshot, and the proposal draft path. Their pull requests and proposals await the user's approval, and pages using them can't deploy until the block is released.
  - Approved exclusions.
- Block-validation summary (`validated_ok`, `auto_fixed`, `downgraded`).
- TODOs the user should inspect (lossy mappings, dropped animations, JS not yet ported).
- Live site sources: the capture date, the out-of-scope inventory, and the defects register with its "found, not changed" list (`live-site-guide.md`).
- Where the run's records are, and that `plugin-findings.md` holds the generic findings to port into this plugin.
- Template mode: the `H2BT_TEMPLATE_CHECKS_*` line, the parity result, the branch and commits (and the PR link if pushed), the plugins the content depends on (including every monorepo block plugin, and any still awaiting release), and that page content lives in the Studio database — deploying ships code only.

## Things that should stop the run

Each precondition and each post-write verification is a hard gate. Never report success when a page-content write's sentinel grep fails, when block validation still shows invalid blocks after the two-call ceiling (downgrade to `core/html` instead), when the standards audit reports stray inline comments, block-CSS organization violations, a block inside the theme, a reserved preset slug, a dropped colour, a fraction of a pixel or post content without a constrained layout, or — in template mode — when `template-checks.sh` ends `H2BT_TEMPLATE_CHECKS_FAIL` or the work would land on `trunk`/`develop`. Surface the reason plainly and stop — the user is driving this and needs to know exactly what was checked.

Never leave the comparison harness in the site: stop the server with `serve-html.sh --stop`, which removes `<site-path>/_h2bt/viewport.html`. The harness runs code it is sent, by design, and only loopback origins can reach it.

For blocks, also stop rather than work around these rules:
- Never create a block inside a theme.
- Never edit a reused monorepo block in place; adapt it from the project.
- Never push to the monorepo, open its pull request, or file a block proposal without the user's approval.
- Scaffold an exclusion only when the user states that an engineering lead approved it.
