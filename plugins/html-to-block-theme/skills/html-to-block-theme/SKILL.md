---
name: html-to-block-theme
description: This skill should be used when the user asks to "build a block theme from this HTML", "turn these designs into a WordPress theme", "convert this Claude Design output to a block theme", "make a WordPress theme from these HTML files", "make this design into a real WordPress site", "convert this site to a block theme", "rebuild this live site as a block theme", or otherwise requests turning static HTML/CSS/JS design files, or the pages of an existing live site, into a WordPress block theme on a local WordPress Studio site — including building into, or porting a finished build into, a project repository generated from a8cteam51/a8csp-project-template. Triggers when static HTML/CSS design files (or a directory of them), or the address of a site to rebuild, are supplied alongside any HTML→block-theme conversion intent.
---

# Build a WordPress block theme from a set of static HTML designs

End-to-end conversion of a directory of static Claude Design files (HTML + linked CSS + JS + assets) into a standards-driven WordPress **block theme** on a local Studio site. The output reproduces the designs as closely as possible using WordPress primitives — `theme.json`, templates, template parts, block styles, and page content an editor can change — not hand-written CSS. Custom behaviour comes from core features first, then from the A8C Special Projects blocks monorepo; the skill never creates a block inside a theme.

Work in phases and **do not skip the blueprint**. Plan the whole mapping first, get it on disk, then build view by view and refine each against the original in a real browser. The reference guides under `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/` are the source of truth for every mapping, standards, and tooling decision — load the relevant one before acting in each phase.

The plugin's own directory is `${CLAUDE_PLUGIN_ROOT}`. The reference guides are files you read, so nothing fills that path in for them: where one writes `<plugin-root>`, it means this directory. The shell does not have it as a variable.

## Inputs

- **Design directory** (required) — absolute path to a folder of static `.html` files plus their linked `.css`, `.js`, image, and font assets. The user provides this.
- **Or a live site to rebuild.** When the source is a running site, load `references/live-site-guide.md` first: it says what to ask, how to mirror the pages into a design directory, and how to treat the original's defects. The mirror is then the design directory for the rest of the run.
- **Project repository** (optional) — a repository generated from `a8cteam51/a8csp-project-template`. When the Studio site's `wp-content` is a clone of one, the run is in **template mode** (detected in Preconditions): it builds into that repository's theme and features mu-plugin under the template's conventions, per `references/project-template-guide.md`.
- **Studio site** — path or registered name of the target Studio site. If the user named neither, list the sites (`studio site list --format=json`) and ask which one, unless there is exactly one. Never pick a site by the look of its name: the run changes the site it is given.
- **Theme** (optional) — the theme to build into, when the user names one. Otherwise the run makes a new theme, or in template mode uses the repository's (Preconditions step 10).

## The run's state is on disk

A run lasts hours, and what is in context at its start is summarised away before its end. So nothing the run needs later is kept in context alone. It is all under `<site-path>/.h2bt/`:

| File | Holds | Written by |
|---|---|---|
| `run.json` | The facts of the run (below). | the orchestrator |
| `serve.json` | Where the design server is: its base URL, the harness URL, the sink directory. | `serve-html.sh` |
| `blueprint.md` | The build contract: the target table with each view's status, the tokens, the decisions, the behaviour table, the build notes. | the orchestrator |
| `analysis/` | `groups.json`, `tokens.json` and one report per analysed view. | `group-designs.py`, the analyzers |
| `results/<name>.json` | Each builder's hand-back. | the builders |
| `pages/<name>.html` | Each page's source markup. | the builders |
| `media.json` | The media manifest: file name → attachment id, URL and dimensions. | the orchestrator |
| `report.md` | The report. | the orchestrator |

`run.json` has these keys. Write a fact when it is settled; the builders read this file, so it is also what a brief does not have to repeat.

| Key | Value |
|---|---|
| `design_dir`, `source` | The design directory, and `design` or `live-site`. For a live site also `source_url`, its address. |
| `phase`, `approved` | `blueprint`, `foundation`, `build`, `verify` or `done`; and when the user approved the blueprint, or `null`. |
| `site` | `path`, `url` (its `localhost` address) and `wordpress` (the core version). |
| `theme` | `slug`, `dir` and `made_by_run` (whether a run of this skill made it). |
| `template` | Template mode only: `repo`, `features_dir`, `prefix` and the two text domains. |
| `widths`, `narrowest` | The widths every view is swept at, and the narrowest the design must hold. |
| `defects` | Live site only: `copy` or `fix`. |
| `builder` | The builder that is running: `name`, `agent`, `started`, `continuations`. `null` between builders. |
| `temporary` | What the run made and must remove before it ends: a mu-plugin shim, a throwaway site. |
| `changed` | What the run changed on the site and leaves, for the report: the PHP version, the active theme, the front page, plugins installed, pages overwritten. |

**The files are the state, not your memory of them.** At the start of every turn after approval, read the target table and `run.json` before acting.

## Critical environment quirks

These will silently corrupt output if missed. They come from Studio, not from WordPress:

1. **Use `studio wp ... --path=<site>`, never bare `wp`.** Studio sites use SQLite; the Studio-managed `wp` wrapper handles that connection. Bare `wp` from the host shell connects to nothing useful.
2. **Stage every file PHP must read inside the site directory.** On a site that runs Studio's sandboxed PHP runtime, `wp` cannot see the host `/tmp/`; on the native runtime it can (`studio site status` shows which a site uses). A file inside the site directory is readable on both, so this skill stages such files at `<site-path>/.h2bt/` and cleans them up, whatever the site.
3. **`studio wp eval-file -` (a script on standard input) can silently no-op** on the sandboxed runtime — exit 0, no output, database unchanged. Always pass a real file path and have the PHP echo a sentinel line the caller greps for. Trust nothing without the sentinel.
4. **Build files serially — all of them, not just page-content writes.** Concurrent `wp_update_post`/`wp_insert_post` under SQLite trips Yoast indexable errors and corrupts results, and every builder also mutates shared theme files (`functions.php`, `theme.json`, block CSS) and refines against the same live site — a parallel builder would screenshot another's half-applied changes. So template-only files are serial too. One `section-builder` at a time — and "no file writes for a while" is **not** a completion signal (builders go quiet for long stretches during browser refinement); wait for the agent's completion notification before dispatching the next.
5. **`studio wp` output is not a clean value.** Under a newer PHP the `studio` CLI can print PHP deprecation notices on standard output, so `$(studio wp … --field=…)` captures a notice. Read values with an `eval-file` script that prints one sentinel line. And the Studio MCP's WP-CLI tool is not a drop-in for `studio wp`: it can run a different PHP version from the site's, below which a plugin with a PHP floor loads nothing, with no error.
6. **A PHP file just saved can still run as it was.** PHP's opcache revalidates a changed file on a timer, so the first request after an edit may run the old code. Request the page twice before concluding that a filter or a render change does nothing.

## Tooling

This skill uses two MCP tool sets, the `studio` CLI, and the plugin's own scripts.

- **Claude in Chrome** — the Claude in Chrome browser extension's MCP tools (`mcp__claude-in-chrome__*`); the extension must be installed, connected to the session, and granted access to `localhost`/`127.0.0.1` sites. Used to load the original HTML (served locally) and the WordPress output in real Chrome, side by side in the comparison harness at an exact width, to screenshot both, and to measure DOM and computed styles. `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/visual-refinement.md` lists the tools to load and how to use them. There is no substitute for it: a screenshot of the WordPress side alone is not a comparison.
- **Studio MCP** — ships with the `studio` CLI; register once at user scope: `claude mcp add --scope user wordpress-studio -- studio mcp`. Relevant tools (confirm exact names in-session before relying on them — the validator has been renamed across Studio versions, e.g. earlier split `validate_html_blocks` / `validate_and_fix_blocks` tools):
  - `mcp__wordpress-studio__validate_blocks` — the combined validator: a static core/html policy check (policy: `mapping-guide.md`) followed by validation in the site's real block editor. Usage rules — argument forms, the two-call ceiling, what to do with rejects — live in the `section-builder` agent, which is what calls it.
  - `mcp__wordpress-studio__scaffold_theme` — makes the run's new theme. It fails when the directory exists, so it cannot overwrite one.
- **Blocks monorepo** — [`a8cteam51/special-projects-blocks-monorepo`](https://github.com/a8cteam51/special-projects-blocks-monorepo), public. `${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh` lists its catalog with each plugin's latest release (`catalog`), installs release ZIPs on the Studio site (`install`), and clones it with its autoloader for building a new block (`clone`). It needs `git` and `python3`, and uses `gh` for release lookups when signed in. Building a new block also needs Node/npm, and Composer for PHPCS. See `custom-blocks-guide.md`.
- **The plugin's own scripts** (`${CLAUDE_PLUGIN_ROOT}/scripts/`). Each prints a sentinel line (`H2BT_…`) that says what happened, and a failure has its own (`…_FAIL`, or a `reason=`). A script that ends without one, or with a non-zero exit, did not do its work: read what it printed, do not go on as if it had:
  - `serve-html.sh` serves the design files with the comparison harness and a results sink, and keeps `serve.json` (`visual-refinement.md`);
  - `group-designs.py` groups the design files before they are analysed;
  - `dev-mode.sh` turns WordPress's development mode on for the build and puts back what was there;
  - `render-probe.sh` renders a block-markup file on the site and prints its HTML and CSS, with no database write (`mapping-guide.md`);
  - `write-page.sh` writes a page, verified by a sentinel;
  - `import-media.sh` imports design images into the media library and keeps the media manifest (`mapping-guide.md` § Asset routing);
  - `mirror-site.py` captures pages of a live site into a design directory (`live-site-guide.md`);
  - `wait-for-result.sh` is a clock for a builder that may never report;
  - `collate-results.py` turns the builders' results into the report's tables;
  - `standards-audit.sh` and, in template mode, `template-checks.sh` and `parity-check.sh` are the gates.

## Preconditions to verify

Check these before any work, in this order. Steps 1 to 6 only read, so that nothing is changed on a site the run then stops on. If any fails, stop and report — do not work around a missing precondition.

1. **The session is on the pinned model.** This plugin's guides are checked against one model, `claude-opus-5-5`, and both subagents are pinned to it. The orchestration runs on the session's model, which a skill cannot hold across turns. If this session is on another model, say which, ask the user to switch (`/model claude-opus-5-5`), and stop. A suffix for the context window, such as `[1m]`, is the same model. The builder runs at `xhigh` effort and the orchestration at the session's, which is `${CLAUDE_EFFORT}`: if that is lower, say so in the blueprint summary and carry on.
2. **`studio` CLI installed.** `command -v studio` and `studio --version`. If missing, point the user to https://developer.wordpress.com/studio/ and stop.
3. **Design directory exists** and contains at least one `.html` file. When the source is a live site there is no directory yet: skip this check here. The mirror is made after step 6 (`references/live-site-guide.md`), because it lives in the site and a resumed run already has one, and the check runs on it then.
4. **Tools and subagents exposed.** Confirm the Claude in Chrome browser tools and the Studio validator (see Tooling) are available in the session, and that the `html-to-block-theme:blueprint-analyzer` and `html-to-block-theme:section-builder` subagent types resolve (they ship with this plugin). A missing subagent type means the plugin is not installed whole: stop. A general-purpose agent is no substitute, because it has neither the agent's instructions nor its pinned model. Load `SendMessage` and `TaskStop` now if they are deferred: the first continues a builder that stopped short, the second stops one that is stuck, and both are needed when nobody is there to ask.
5. **Site resolves, and its address is loopback.** `studio site status --path=<site-path>` exits zero. The comparison harness frames only loopback addresses, so the site is addressed as `http://localhost:<port>` (`url` and `port` in `studio site list --format=json`). If the site has a custom domain and does not answer on its `localhost` address without redirecting to it, say so and ask the user to switch the custom domain off in Studio for the build.
6. **Is there a run on this site already?** Read `<site-path>/.h2bt/run.json` and `blueprint.md`, if they are there, and follow *Start or resume* below before any later step. A run that is resumed must not be set up as a new one.
7. **Site is running.** If stopped, `studio site start --path=<site-path>` and wait. If start fails, stop.
8. **WP-CLI works, and note the core version.** `studio wp core is-installed --path=<site-path>` exits zero. Read the WordPress version (`studio wp core version --path=<site-path>`; the version is the line that is one, since notices can precede it): attribute forms depend on it, and the per-viewport attributes in `mapping-guide.md` need 7.1 or later.
9. **Detect the layout.** Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-template.sh" --site-path <site-path>` and read its `H2BT_TEMPLATE` sentinel.
   - `mode=standalone` → continue with step 10. If the user named a project-template repository but the site's `wp-content` is not a clone of it, set that up first with the `studio-repo-clone` plugin (`clone-into-existing-site` keeps the site's database and uploads; `clone-new-site` for a new site), then re-run detection.
   - `mode=template` → load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/project-template-guide.md` and satisfy its Preconditions (feature branch, PHP floor, toolchain, dependencies). Record `<repo>`, `<features-dir>`, `<prefix>` and the text domains under `template` in `run.json`.
   - `mode=template-unreadable` → the site's `wp-content` is a project-template repository whose theme could not be read. Stop and report the sentinel's `reason`: building a standalone theme into that repository would ignore its conventions.
10. **Decide which theme the run builds into.** The run replaces a theme's `theme.json`, parts and templates, so it builds only into a theme it may replace. The active theme is not that just because it is active: a new site's active theme is a default theme, and writing into it replaces it under its own name.
    - **Standalone.** Build into an existing theme only when `run.json` says a run made it (`theme.made_by_run`), or the user named it in this conversation. Otherwise make a new one with `mcp__wordpress-studio__scaffold_theme`, with a slug from the project and `activate: false`. It is activated when the blueprint is approved.
    - **Template mode.** The theme is the repository's (the sentinel's `theme_dir`). On a new run, a working tree with uncommitted changes, or one whose theme no longer holds the template's example content (the sentinel's `examples` lists none of `footer-default-pattern`, `index-query-pattern` and `singular-template`), holds work that is not this run's: say what the run would replace, and ask before going on.
    - **Either way,** list what is stored in the database for that theme: `wp_template`, `wp_template_part` and `wp_global_styles` posts made in the Site Editor win over the theme's files, so with one in place an edit to the file shows nothing. Name any in the blueprint summary and ask whether to remove them. An empty `wp_global_styles` post is not one of them: loading an editor stores it, and it overrides nothing.
    - Record `theme` in `run.json`, and bind its `dir` as `<theme-dir>`.
11. **Working directory, and prior lessons.** Create `<site-path>/.h2bt/` with `analysis/`, `pages/` and `results/` in it, and remove the loose staged files of a prior aborted run (`content-*`, `title-*`, `excerpt-*`, `write-*`, `probe-*`) with `find <site-path>/.h2bt -maxdepth 1 -type f -name '<prefix>*' -delete`, one `-name` per prefix: in zsh a glob that matches nothing stops the whole command. Keep everything else there: the records a run leaves and every directory. Read `lessons.md` if present: it holds lessons recorded by previous runs against this site and environment, and they apply to this run.

### Start or resume

Step 6 reads `<site-path>/.h2bt/run.json` and `blueprint.md`. What it finds decides how the run starts:

- **No `run.json`:** a new run. Write it now, with the design directory (for a live site its address, as `source_url`), the source, the site and `phase: blueprint`. The later steps add to it; none of them writes it afresh.
- **A run for this design directory, or for this live site:**
  - No `blueprint.md`, or `approved` is `null`: the run stopped before its blueprint was approved. Keep what the analysis left in `analysis/`, take Phase 1 up at the first step whose output is missing, and show the summary and ask. Do not analyse a view again unless the user asks for it or its design file changed.
  - `approved` is set and `phase` is not `done`: the run was interrupted. Do not analyse again, and do not rewrite the blueprint: its statuses, its build notes and the user's amendments are the run. Go through the remaining preconditions, which refresh what `run.json` holds about the site. Then turn development mode on and bring the design server back, as on approval (Phase 1, step 8), and go on: from the first step of Phase 2 when `phase` is `foundation`, looking at what each step left before redoing it, and otherwise from the target table.
  - `phase` is `done`: the run finished. Ask what is wanted now: changes on top of it, which keep the records, or a new run. Changes on top of it follow the `change-built-theme` skill.
- **A run for another design,** or the user wants a new run: ask first. Then stop the design server (`serve-html.sh --stop --site-path`), move the run's own records to `<site-path>/.h2bt/archive-<date>/` (`run.json`, `blueprint.md`, `analysis/`, `results/`, `pages/`, `media.json`, `measurements/`, `report.md`), and start a new run. What belongs to the site stays where it is: `lessons.md`, `plugin-findings.md`, `dev-mode.prior`.

This is also where a turn starts after the conversation has been summarised: the files say which case it is.

## Procedure

### Phase 1 — Analyze and blueprint (plan the map first)

1. Start the design server, or bring it back:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --ensure --site-path "<site-path>" --dir "<design-dir>"
   ```

   It prints `H2BT_SERVE url=<base-url> …` and `H2BT_HARNESS url=<harness-url> site_copy=<path> sink=<dir>`, and writes the same to `<site-path>/.h2bt/serve.json`. Each design file is at `<base-url><its path in the design directory>`. A copy of the comparison harness is placed in the site root while the server runs (`visual-refinement.md`). The command is safe to repeat: it reuses a server that still answers and starts a new one when it has died, so run it again whenever the original stops loading.

2. Group the design files:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/group-designs.py" --dir "<design-dir>" --out "<site-path>/.h2bt/analysis/groups.json"
   ```

   A design whose pages are assembled by a build script keeps its fragments in folders of their own (`src/` and `parts/` beside a `build.js`, say). Pass each such folder with `--exclude <its path in the design directory>`, or every fragment is grouped as a view.

   For each file it gives a `name`, unique in the set and used for that view's report, page source and result; its `template` group; and its `role`: `representative`, `same` (same template, same sections, stylesheets and `<style>` blocks as its representative) or `differs` (with `differs_by`). It also lists every stylesheet with the number of files that use it (`stylesheets`), and the CSS that pages carry in `<style>` blocks (`inline_styles`). The groups are a proposal made from markup alone: look at one `same` file beside its representative before relying on it.

3. Read the design's tokens once. Dispatch one **`blueprint-analyzer`** with `mode: tokens`, the design directory, the path of `groups.json` and the report path `<site-path>/.h2bt/analysis/tokens.json`, and for a mirror of a live site that it is one. It reads the stylesheets, and the `<style>` blocks where a design keeps its CSS in the pages, and reports colours, type, spacing, widths, font faces and every breakpoint.

4. Analyse the views. Dispatch one **`blueprint-analyzer`** for each file whose role is `representative` or `differs`, **at most six at a time**: send a batch in one message, wait for all of it, then send the next. Each changes nothing but its own report, so a batch is safe in parallel. Use the Agent tool with `subagent_type: "html-to-block-theme:blueprint-analyzer"`, passing exactly what its Inputs section lists: the file's path and served URL, the design directory, the site's WordPress version, the path of `tokens.json`, and the report path `<site-path>/.h2bt/analysis/<name>.json`; for a mirror of a live site also that it is one, with the paths of the page's reading aid and script-free copy (`live-site-guide.md`). A `same` file is not analysed: its view uses its representative's report. Each analyzer writes its full report and returns a digest of a couple of kilobytes. A full report runs to tens of kilobytes, so keep them on disk: read a report only for the facts a decision needs. A hand-back that is not the digest, or whose report file does not exist, is not a finished analysis: continue that analyzer as Phase 3 continues a builder.

5. **Reconcile** the analyses into one blueprint. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/mapping-guide.md`, `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, and `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/custom-blocks-guide.md` for the rules. **Every value an analyzer reports is derived from stylesheets, not measured: measure on the rendered original before a value goes into the blueprint or the theme.** Decide:
   - A single unified token set for `theme.json` (merge near-duplicate colours/sizes; one source of truth), with no reserved slug, and whether typography is fluid (`theme-json-guide.md`).
   - The design's two main breakpoints, which become `settings.viewport` on WordPress 7.1 and later as whole pixels, and the list of other widths at which something changes: each of those costs a block style. From them, the widths every view is swept at (`run.json` `widths` and `narrowest`): desktop, one pixel either side of each breakpoint, the narrowest width and `1900`.
   - The design's text column and wide column, which become `contentSize` and `wideSize`. Post content is laid out with them in every template; a section wider than the text column is an aligned block in the page.
   - The shared chrome (header/footer/nav present across files) → template parts, and the design file that shows each variant of it.
   - **Where content and images live** (`mapping-guide.md` § Where content lives, § Asset routing). The defaults: nothing a visitor reads is held in a PHP pattern, and design images are media-library items, with Safe SVG as a site dependency when any is an SVG. State both in the summary so the user can change them, with what they bring: no page content in the theme, and a content migration for any other environment.
   - Each view's target: core templates (`templates/index.html`, `single.html`, `archive.html`, `404.html`, …) vs pages that share a wrapper template and differ only in content → a WordPress page assigned to that template. Files that show one template with different content, such as twenty posts, are one target: the template. A page is a target of its own, also when it shares its wrapper template and its report with other pages. **The homepage is always a page, never `templates/front-page.html`** — template choice and Reading-settings wiring per the homepage rule in `mapping-guide.md`.
   - A search view, when the design has none. WordPress then shows search results with `templates/index.html`, which in one build gave them no H1. The chrome row adds `templates/search.html` with one (`standards.md` § Accessibility).
   - Where each behaviour comes from, per `custom-blocks-guide.md`: a core route; a monorepo plugin to reuse (run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" catalog` once and check every candidate against it); a new `a8csp/<slug>` block to build in the monorepo; or, in template mode and only when the user states an engineering lead approved it, an exclusion kept in the features plugin. Record why each earlier step fails.
   - What cannot be carried over as it is and needs the user's answer: a control whose accessible name differs from its visible text, and, for a live site, everything `live-site-guide.md` lists.

6. Write the blueprint to `<site-path>/.h2bt/blueprint.md`: the token set and breakpoints, the content and image decisions, the behaviour table with each behaviour's source, the per-section mapping, an empty **build notes** section that Phase 3 fills, and the **target table**. The table has one row per target, in build order. A row holds:
   - its `name`: the one `groups.json` gives its design file (for a template shown by several files, its representative's), which is also the name of its page source and its result;
   - what it becomes, in full, because the builder has nothing else to go by: the part and template files; or the page's title, slug, parent path if its address is nested, template slug, and whether it is the front page;
   - the design file or files it comes from, and the report it uses;
   - a status, `pending` at first.

   The order:
   - **The shared chrome is the first row**, named `chrome`: the parts and the wrapper templates, with the design file to compare them on. `templates/index.html`, which every theme must have, belongs to this row when no view of the design is the posts index. It is built and refined like any view, before any view that sits in it.
   - Then the view that uses the most of the shared styles, usually the homepage; then the rest. A view that uses another's report comes after that one.

7. **Try everything the unattended part needs, while the user is here.** A permission prompt now costs them one click; the same prompt in Phase 3 stops the run until they come back.
   - Write and remove a file in `<theme-dir>` and in `<site-path>/.h2bt/`.
   - Run `render-probe.sh` on one line of markup: it stages a file in the site and runs `studio wp eval-file`.
   - Call the validator on one block.
   - Open the harness with a design file and the site's front page, and run `h2bt.ready()`: it must report `status: 200` for both panes. If the extension asks before it runs the script, have the user grant it `localhost` and `127.0.0.1` for good: a builder cannot answer that prompt, and its script calls then time out while navigation and screenshots still work.
   - Open `<site-url>/wp-admin/` in Chrome. If it asks to log in, ask the user to open WP Admin from Studio once. Do not type the site's password into the browser yourself.
   - In template mode, run `npm run build` once.

8. **Present a summary to the user, ask them to approve or amend it, and end the turn** — the blueprint is the build contract, and Phase 2 starts only on their approval. The summary names what the run will change, so that the approval covers it:
   - the site, by name and path, and the theme: a new one with its slug, or the existing one and why the run may build into it;
   - pages that exist and that the run will overwrite, by slug, and the change of front page;
   - plugins it will install, and Site Editor overrides it found (Preconditions step 10);
   - the content and image decisions, and anything from step 5 that needs an answer.

   Before the turn ends, stop the design server (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --stop --site-path "<site-path>"`): the harness does not stay in the site while the run waits for an answer. Do not end the turn on a promise to build.

   **On approval:**
   - Record `approved` in `run.json`. When the user had already said to run without check-ins, that is the approval: record it, go on without asking, and say in the report that the blueprint was applied unreviewed.
   - Turn development mode on for the build: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dev-mode.sh" on --site-path "<site-path>"`. WordPress caches a theme's file list and its `theme.json`; without this, a new or deleted file shows stale results. The script records the value the site had, and its `restore` puts that back at the end.
   - Activate the run's theme (`studio wp theme activate <slug> --path=<site-path>`), in template mode too, unless the run ports a build that must stay active until its parity baseline is taken (`project-template-guide.md`). Record the theme that was active under `changed`.
   - Bring the design server back (step 1).

### After approval — one run, to the report

Phases 2 to 4 are one run. The user approves the blueprint and may not be watching after that, and a message with no tool call in it ends the turn: the work stops there until they come back. So do not end a turn:

- on a summary of what was just built or checked that announces the next step. Take the next step in the same message;
- on an offer to carry on unless the user would prefer otherwise;
- on a list of decisions for the user when none of them blocks the remaining views. Record each in the blueprint's build notes for the report, and carry on with everything it does not block;
- because a phase or a view is finished, or the turn has been long.

Status notes are welcome, in the same message as the next tool call. Waiting for a running builder or analyzer is not an early stop: its completion notification restarts the run. The stops that are wanted are the ones under *Things that should stop the run*, and a question without whose answer nothing can move. Work that waits for the user's approval (a push, a pull request, a block proposal) does not stop the run either: finish everything else and list it in the report. None of this removes a confirmation this skill asks for.

**The target table is the run's checklist.** A view's status is one of:

| Status | Means |
|---|---|
| `pending` | Not started. |
| `building` | Its builder is running, and `run.json` `builder` names it. |
| `checked` | Its hand-back passed the orchestrator's checks. |
| `recheck` | It was `checked`, and a shared file changed since. |
| `generated` | The orchestrator built it itself, and checked it. |
| `partial`, `failed` | What its builder reported, or what its checks found, with the reason. |

A turn that ends with a view still `pending`, no builder running and no blocker stated has ended early, and the next turn starts from that table.

### Phase 2 — Foundation (theme.json is the source of truth)

Build what every view shares, before any view. Load `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/theme-json-guide.md`, `block-styles-guide.md`, and `custom-blocks-guide.md`. Set `phase` to `foundation` in `run.json`, and to `build` when this phase is done.

1. Write `theme.json` from the unified token set: palette, typography/`fontFamilies`, spacing scale, layout `contentSize`/`wideSize`, the two viewport breakpoints, radii/shadows, and element styles. A scaffolded theme comes with values, `style.css` rules and templates of its own: they are placeholders, not givens. Replace its `theme.json` whole, and keep in `style.css` only the rules this design needs, without the scaffold's comments. Register in `customTemplates` every custom page template the target table names: a page can be given a template that is only a file, but the editor does not offer it. Declare in `templateParts` every part the table names, with its area: a part that is not declared prints as a `<div>`, not as a `<header>` or a `<footer>` (`theme-json-guide.md` § Template parts). **Every value in pixels is a whole number of pixels,** breakpoints included (`mapping-guide.md` § Pixel values are whole pixels). **Measure which font file draws each weight** before declaring the font faces (`theme-json-guide.md` § Font faces): it cannot be read from the original's stylesheet. Write the two root layout rules into the root stylesheet, before any view: no gap between the parts and `main`, and none between two full-width bands in post content (`mapping-guide.md` § Layout traps). The text-wrapping rule goes there too (`standards.md` § Text wrapping).
2. Leave the parts and the templates to their builders: the shared chrome is the first row of the target table, and it is built and refined against the original like any view. Delete the templates and parts no row of the table replaces (a scaffold's placeholders, the template repository's examples), all but `templates/index.html`: nothing that no view owns ships with the theme. One rule holds for whoever writes a template: give `core/post-content` a constrained layout, also where the design is a stack of full-width bands. Those are `alignfull` blocks in the page's content (`mapping-guide.md` § Post content sits at content width).
3. Register block styles per `block-styles-guide.md` — `register_block_style()` in `functions.php` (one variation per mapped custom CSS class), with one CSS file per block type under `assets/css/blocks/`, enqueued via `wp_enqueue_block_style()`.
4. Put each behaviour's block in place, per the blueprint and `custom-blocks-guide.md`:
   - **Reused monorepo blocks:** install their release ZIPs with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" install --site-path <site-path> <plugin-dir>...`.
   - **New blocks:** build them in a monorepo clone (`bash "${CLAUDE_PLUGIN_ROOT}/scripts/monorepo-blocks.sh" clone --site-path <site-path>`, then `npm run new-block`, on an `add/<slug>` branch), keep them project-agnostic and wireframe-styled, check them in the newest Twenty-* theme on a throwaway Studio site, add the screenshot, and draft the New block proposal. Pushing the branch, opening the monorepo pull request and filing the proposal wait for the user's approval.
   - **Styling:** style every reused or new block from the theme with its own block stylesheet (`block-styles-guide.md`), and adapt behaviour with project-side filters, never by editing the block.
   - **Approved exclusions** (template mode only): see Template mode below.

5. Route assets per `mapping-guide.md` § Asset routing: fonts → `theme.json` `fontFamilies` with files copied into `assets/fonts/`; design images → the media library, with Safe SVG installed first when any of them is an SVG (`studio wp plugin install safe-svg --activate --path=<site-path>`), imported with `bash "${CLAUDE_PLUGIN_ROOT}/scripts/import-media.sh" --site-path <site-path> --list <list.json>`, which must end `H2BT_MEDIA … failed=0` and writes the one manifest every builder takes ids from (`<site-path>/.h2bt/media.json`); only the images a template, part or stylesheet itself needs → theme `assets/`.
6. **Write the dynamic pieces a view needs before its builder starts, and test them through a rendered template** (`custom-blocks-guide.md` § Test groundwork): bindings sources, render filters, sample content for a post type.
7. **A store's pages must answer a logged-out request.** A new WooCommerce install (9.3 and later) switches coming-soon mode on for the store pages. A logged-in administrator still sees the store, but the harness requests pages logged out, so it would compare the original with the coming-soon page. Switch it off (`studio wp option update woocommerce_coming_soon no --path=<site-path>`) and record that under `changed`.

Whatever this phase changes on the site and leaves goes under `changed` in `run.json` (a plugin installed, the PHP version), and whatever it makes and must remove goes under `temporary` (a throwaway site, a mu-plugin shim), at the moment it is made.

End the phase by writing the blueprint's first **build notes**: what the foundation holds (the presets and their slugs, the registered block styles, the blocks installed, the media manifest). The first builder has nothing else to tell it what exists.

**Template mode.** `project-template-guide.md` overrides the locations above and adds steps. In short:
- Strip the template's example features, each by the recipe in its own file. They are there to show how a feature is built in this repository: read them for that, and keep one only where the build itself uses it. The conversion writes no tests: under `tests/` it only deletes what such a recipe names.
- Replace `theme.json` in `<theme-dir>`, and remove the example patterns. The parts and templates are replaced by their builders.
- Put root styles in `assets/sass/` partials.
- Put block CSS in `assets/sass/blocks/<block>.scss`, built to `assets/css/blocks/<block>.css` and registered from `includes/block-styles.php` against that built path. Point the template's build scripts there first (`project-template-guide.md` § Build pipeline).
- Write all Sass nested (`block-styles-guide.md`, template mode).
- Put theme JS in ES modules under `assets/js/src/`.
- Blocks still come from the monorepo. Only an approved exclusion (the user states an engineering lead approved it) is scaffolded into the features mu-plugin, with `scaffold-custom-block.sh --exclusion-approved --features-dir <features-dir> --namespace <theme_slug> --slug <slug> --title "<Title>"`.
- Delete `<features-dir>/.disabled` once the features plugin carries real features (an approved exclusion, a redirect, a post type). Its examples are stripped by then: enabling the plugin with one in place publishes the example post type on the site.

Run `npm run build` after the foundation and after every source edit, since the site serves built files.

### Phase 3 — Build and refine, section by section (serial)

Build the views **one at a time**, in the order of the target table (serial — see quirk 4). For each, dispatch a **`section-builder`** subagent via the Agent tool with `subagent_type: "html-to-block-theme:section-builder"`. Its brief is short, because the rest is on disk where it reads it:

- the site path;
- the view: its `name` and its row of the target table;
- anything about this view that is in no file yet.

Set the view to `building` and record the builder in `run.json` (its view and when it started; its agent id as soon as the dispatch returns one). With the dispatch, start its clock in the background (the Bash tool's `run_in_background`):

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/wait-for-result.sh" --site-path "<site-path>" --name "<name>" --minutes 90 --watch "<theme-dir>"
```

The builder's own instructions say how it builds, writes, validates and refines: `${CLAUDE_PLUGIN_ROOT}/agents/section-builder.md`. Read that file before building a view yourself (below), so that both follow one set of rules. It writes its hand-back to `<site-path>/.h2bt/results/<name>.json` and returns a short pointer to it: the view's `name`, its `status` (`success`, `partial` or `failed`), the file, and what is open. The hand-back is the file: read it there.

**A hand-back whose result file is not there, or does not parse, is a progress note, not a result.** So is one that names work it stopped before doing (sections not built, no final validation, widths not swept) with no reason it could not go on. Continue the same builder with `SendMessage`, naming what is open: it keeps its context, and a second builder for the view would start without it. If the session cannot continue an agent, dispatch a new builder with the first one's hand-back and the open items. After two continuations, set the view to `failed` with what is missing, run the hand-back checks below so that the shared files are sound, and go on to the next view.

When the clock ends because the result is there (`H2BT_RESULT`), the builder's own completion notice has arrived or follows: act on the hand-back once. The clock counts only a result written after it started, so start a new one with every continuation: a result left by an earlier attempt is not the answer to this one. A clock that ends for a view that is no longer `building` is of no account.

**When the clock ends first** (`H2BT_RESULT_TIMEOUT`), the builder has not reported in that time. Its `quiet_minutes` says how long ago anything was last written. A builder that wrote something in the last half hour is working: start the clock again. One that has been quiet for longer is stuck on a call that will not return: stop it with `TaskStop`, then continue it with `SendMessage`, saying that it was stopped and what its result file must hold. That counts as a continuation.

**A view found `building` when a run is resumed** has no builder that will report to this session. If its result file is there, and was written after that builder started (`run.json` `builder.started`), it handed back: check it. If not, continue its builder with `SendMessage` when `run.json` names one the session can reach. Otherwise dispatch a new builder and say that the view may be half built, so that it reads what exists before it writes.

**A failed environment is not a failed view.** When a builder reports `failure_kind: environment` (the original does not load, the site is down, the browser tools are gone, a tool was refused), repair it first: `serve-html.sh --ensure`, `studio site start`, the check of Preconditions step 4. Then continue the same builder. If it cannot be repaired, dispatch no further builder into the same failure: go to *Things that should stop the run*.

**Not every view needs a builder.** A page that is one template plus one run of text is generated, validated, written and compared by the orchestrator, and two views of one design come from one generator (`mapping-guide.md` § Long-form and repeated content). Its status is `generated`. Write its result to `results/<name>.json` yourself, in the builder's form, and do the same for a view you set to `failed` that left none: the report's tables are made from those files, and a view without one is missing from them.

**Carry what each builder learns to the next one.** Builders start without memory, and the next builder copies what exists. After every hand-back:

1. **Check it, don't take it on trust.** Rebuild and confirm the built files do not change (template mode), lint the tracked paths (template mode), run the standards audit (Phase 4, step 3), and compare the view at two widths in the harness (document height and overflow on both sides). This is the only window in which the browser and the shared stylesheets are free, and the builder can still be continued with what a check finds.
   - **Leave the audit passing before the next view starts.** It reads the whole theme and every page source, so one view's violation fails every audit after it. A violation in this view's files goes back to its builder. If the view ends `failed`, take the violation out yourself, so that the next view starts clean.
2. **Fix what it reported about shared files** — `changed_outside_view`, drift entries on shared parts, the TODOs — and measure the fix. Budget for this: in practice most hand-backs carry at least one real defect in shared chrome, a token or a shared section.
3. **Look again at what a shared change touches.** After any change to a part, a token, a shared block style or a wrapper template, by you or by the builder, every view that was `checked` is `recheck`: sweep its widths for document height and compare its text at desktop and phone width, against the drift its result records. Nothing new: `checked` again. Something new: fix it, or record it.
4. **Rewrite the blueprint's build notes** (what exists and is checked, the authoring procedure that worked, scope reminders, how to compare) **and set the view's status in the target table.** Clear `builder` in `run.json`, and record under `changed` what the view changed on the site: a page it overwrote, the front page.
5. Add the builder's `quirks_fixed` to the register (live sites) and its `plugin_findings` to the findings file (Phase 4, step 5).

While a builder runs, do only work that touches neither the theme, the database nor the browser: documentation, content conversion, the next builder's brief.

### Phase 4 — Verify and report

Set `phase` to `verify` in `run.json`.

1. Full-page comparison per view in the harness: a sweep of the run's widths for document height, sideways overflow and text; then a look at each page top to bottom at desktop and phone width. Read the `loading` attribute of the largest image on each view's first screen (`standards.md`).
   - **Pages the blueprint leaves to a plugin's own templates are views too:** WooCommerce's cart, checkout, account and order confirmation, say. Load each at desktop and phone width, in the state that fills it (a product in the cart), and check that it carries the theme's header and footer, before the report says anything about it. A plugin's template need not use the theme's parts (`mapping-guide.md` § WooCommerce).
2. Block-validity summary across all views, and one check in the editor itself (`visual-refinement.md` § The editor canvas): open a page per template in the block editor and confirm it loads with no invalid block, that every section is there and none is collapsed or unstyled, that the content's root is constrained, that its full-width sections span the canvas, and that a block at the root with no alignment is as wide as the content column. Each builder has looked at its own view there; this pass sees what changed since. Read, do not edit: type nothing and insert nothing, so that the editor has nothing to save or to warn about when the tab closes. What an unaligned block gets can be measured without inserting one: append a plain element to the canvas's root container, measure it and remove it in the same call.
3. Standards audit:

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/standards-audit.sh" --theme-dir "<theme-dir>" --content-dir "<site-path>/.h2bt/pages"
   ```

   It must end `H2BT_AUDIT_OK`. On `H2BT_AUDIT_FAIL`, each violation is a line of its output that starts with a label in capitals and says what to change, and each counter in the sentinel that is not `0` names a kind of violation: fix them and run it again. `H2BT_AUDIT_FAIL reason=<why>`, with no counters, means the audit could not run (a wrong directory, a tool that is missing): put that right first. `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/standards.md` says what each rule is for. The audit detects a template-mode theme itself. It also lists theme-file images that reserve no space (`REVIEW` lines, counted as `image_review`), which does not fail it: fix or explain each. It itemises the custom-CSS footprint for the report, with the total as `css_lines`. It does not read a project repository's Sass, or any JS, for comments: read what the run wrote for them (`standards.md` § Comments).
4. **Template mode gates.** Run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/template-checks.sh" --repo <repo>`. Add `--tests --e2e` only when Docker is already running: do not start it, and say in the report that the two suites were not run. It must end `H2BT_TEMPLATE_CHECKS_OK`; fix each failing gate by the table in `project-template-guide.md` § What fails CI. Take a `parity-check.sh` baseline before running any formatter or auto-fixer, and compare afterwards. **The conversion writes no tests:** it adds none and rewrites none to fit the build, and under the repository's `tests/` it only deletes what an example's removal recipe names. A suite that fails on the build is answered in the theme, never in the test. Commit in logical conventional-commit units on the feature branch; push and open a **draft** PR against `trunk` only with the user's permission.
5. **Record lessons, in two files.**
   - `<site-path>/.h2bt/lessons.md`: anything a future run against **this site** should know — corrections, confirmed approaches, environment quirks discovered this run. One lesson per entry, a one-line summary first, then why it mattered. Don't record what `blueprint.md` or the theme itself already captures; update an existing entry rather than duplicating it, and delete entries this run proved wrong.
   - `<site-path>/.h2bt/plugin-findings.md`: what this run learned that applies to **any** site built with this skill, ready to be ported into the plugin's guides. Keep it through the run, not at the end: add each builder's `plugin_findings` as it reports. Nothing in it names the site, its owner or a design value. Each entry says what was observed, how it was checked (or that it was derived and not checked), and which plugin file it changes. Mark an entry that is the user's decision on this project, as opposed to an observation.
6. **Clean up, write the report, then say so.** In that order: the report says what was put back, so that has to have happened, and the message that carries the report ends the turn, so nothing can come after it.
   - Put back what the run borrowed: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/dev-mode.sh" restore --site-path "<site-path>"`, then everything under `temporary` in `run.json`. The restore must end `H2BT_DEV_MODE restored …`; an `H2BT_DEV_MODE_FAIL` goes into the report as it is. Reload one view per template afterwards: with WordPress's caches back on, the site must still show the build.
   - Stop the design server, which also removes the harness copy from the site: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/serve-html.sh" --stop --site-path "<site-path>"`.
   - Remove the loose staged files in `<site-path>/.h2bt/` and keep everything else, as in Preconditions step 11.
   - Write the report (below) to `<site-path>/.h2bt/report.md`. `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/collate-results.py" --site-path "<site-path>"` prints its tables from the result files: use them, do not rebuild them from memory. Set `phase` to `done`.
   - End with the report's summary and the path of `report.md`.

## Report

Write to `report.md`, and summarise in the last message. Every statement in it rests on a file or a tool result of this run: a builder's result, the audit's output, a measurement in `measurements/`. What was not checked is listed as not checked, and what failed is said first.

- The theme built (name + path) and the target table from the blueprint (what became a template, a part, or a page), with each view's status. A view that is `failed` or `partial` is said first, with its reason.
- Per-view fidelity at each viewport, and the **residual drift list** — every detail that did not match 1:1 and why.
- **Where the content is.** Page content and design images live in the site's database and media library, not in the theme: another environment gets them by a content migration, and stored image blocks name this environment's attachment ids and URLs. Name the plugins the content depends on (Safe SVG when any image is an SVG).
- **What the run changed on the site and left** (`changed` in `run.json`): the active theme, the front page, the PHP version, plugins installed, pages overwritten. And what it put back.
- **What was not checked:** other browsers, touch devices, screen readers, the editor beyond the pages opened, and anything a local site cannot show (a connected plugin's output, production-scale content).
- **First-screen images:** the `loading` attribute of the largest image on each view's first screen, and whether the theme changes the lazy-loading threshold.
- **Every custom CSS rule written and why** (which ladder rung it sits on), plus the total custom-CSS footprint from the audit.
- **Every block beyond core and where it came from**: each behaviour's source and why the earlier steps failed.
  - Reused monorepo plugins, with their versions.
  - New monorepo blocks: the clone branch, the Twenty-* check result, the screenshot, and the proposal draft path. Their pull requests and proposals await the user's approval, and pages using them can't deploy until the block is released.
  - Approved exclusions.
- Block-validation summary (`validated_ok`, `auto_fixed`, `downgraded`).
- **The editor:** what each view showed in the editor canvas that the front end does not (a section missing, collapsed or unstyled), and whether it was fixed.
- TODOs the user should inspect (lossy mappings, dropped animations, JS not yet ported).
- Live site sources: the capture date, the out-of-scope inventory, and the defects register with its "found, not changed" list (`live-site-guide.md`).
- Where the run's records are, and that `plugin-findings.md` holds the generic findings to port into this plugin.
- Template mode: the `H2BT_TEMPLATE_CHECKS_*` line and whether the wp-env suites were run, the parity result, the template's example features that were stripped, and any the build kept and why, the branch and commits (and the PR link if pushed), the plugins the content depends on (including every monorepo block plugin, and any still awaiting release), and that page content lives in the Studio database — deploying ships code only.

## Things that should stop the run

Each precondition and each post-write verification is a hard gate. Never report success when a page-content write's sentinel grep fails, when block validation still shows invalid blocks after the builder's last call (it rebuilds them as editable blocks; `core/html` is not a fallback outside its policy in `mapping-guide.md`), when the standards audit ends `H2BT_AUDIT_FAIL`, or — in template mode — when `template-checks.sh` ends `H2BT_TEMPLATE_CHECKS_FAIL` or the work would land on `trunk`/`develop`.

What stopping means depends on whether the user is there:

- **Before the blueprint is approved,** stop and say why, after stopping the design server if it runs. The user is there to answer. Say what the run has made so far, which is at most an inactive theme and its records in `.h2bt/`.
- **After it,** nobody is. One view that fails is not the run: set it to `failed` with its reason and build the next. When what failed is the run's (the environment cannot be repaired, a gate of Phase 4 still fails after its fixes, the work would land on a deploy branch), build nothing more on top of it. Finish what does not depend on it, write the report with what failed and what was checked, clean up as in Phase 4 step 6, and end with that.

Never leave the comparison harness in the site: every way out of the run goes through `serve-html.sh --stop --site-path`, which removes `<site-path>/_h2bt/viewport.html`. The harness runs code it is sent, by design, and only loopback origins can reach it.

For blocks, also stop rather than work around these rules:
- Never create a block inside a theme.
- Never edit a reused monorepo block in place; adapt it from the project.
- Never push to the monorepo, open its pull request, or file a block proposal without the user's approval.
- Scaffold an exclusion only when the user states that an engineering lead approved it.

For a project repository, also: never write a test. The conversion adds no test file, no test and no assertion, and rewrites none to fit the build. Under `tests/` it only deletes what a template example's removal recipe names.
