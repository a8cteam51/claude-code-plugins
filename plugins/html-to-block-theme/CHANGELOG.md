# Changelog

## [0.7.2] - 2026-10-12

### Fixed
- **`standards-audit.sh` took a class named in a Sass `//` comment for one the stylesheet selects.** In a project repository, a block `className` that only such a comment mentions failed the class check (`class_hooks`), and with it the audit. Line comments in `.scss` sources are now left out before the selectors are read, as they already were for the whole-pixel check. Reproduced on 0.7.1 and tried again after the fix.

## [0.7.1] - 2026-10-12

From the feedback on issue #11 (a review of a built site, and a run of 0.4.0 on a one-page design) and a code review of 0.7.0. Each fact about WordPress below was checked on WordPress 7.1.3, by rendering or in its source, and the one about Jetpack in the source of Jetpack Forms 16.1.2. Each script defect was reproduced on 0.7.0 and tried again after its fix. Two things were not checked. That a preset class with no attribute validates was; that the editor then lists it under Additional CSS class(es) is how the block parser treats such a class, and what the site review reported. And no build has followed the new section on the editor canvas yet. No run has been made end to end with these changes.

### Changed
- **Builders look at their view in the editor.** 0.7.0 kept builders to the front end, because loading an editor stores an empty `wp_global_styles` post. The skill builds on new sites, where that post overrides nothing, so it is now left alone: nobody records it or removes it. Each builder opens its view in the block editor or the Site Editor once, after its final validation, reads and does not edit, fixes what the theme causes and records the rest as drift. Its result says what it found (`checks.editor_canvas`), the report's table has the column, and `visual-refinement.md` has a section on the canvas: what to check, and where to look when a section is right on the front end and broken there.
- **A new block has to be usable in the editor.** The monorepo rules for a new block say what its `edit` shows, and the Twenty-* check opens the block in the editor as well as on the front end.
- **`group-designs.py` compares the CSS in `<style>` blocks.** A page whose `<style>` block differed from its representative's was `same`, and got no analysis of its own. It is now `differs`, with `inline_styles` in `differs_by`. What it costs: WordPress prints per-page block CSS, so on a mirror of a WordPress site pages of one template that use different blocks are each analysed. In a sample of four pages, one of the two `same` pages changed.

### Added
- **Three checks in the standards audit:**
  - `class_hooks`: a setting written as a class. It fails on a `has-*` class in a block's `className`, on a font family or font size class with no `fontFamily` or `fontSize` attribute behind it, and on a `className` the theme's own stylesheets select that is not a registered style. A preset class without its attribute validates, and the editor then shows it as an additional CSS class and in no control. Two themes built by earlier versions had this.
  - `template_parts`: a file under `parts/` that `theme.json` does not declare in `templateParts`. Without its area a header or footer part prints as a `<div>`: the page loses both landmarks, and the guides' own `header.wp-block-template-part` selectors match nothing.
  - `css_comments`, in a standalone theme: a comment in `style.css` or a block stylesheet after the file's header. A scaffold's explanatory comments were kept with its rules.
- **In the guides:**
  - `theme-json-guide.md`: a section on `templateParts`; the root padding properties are declared on `body`, so `:root:root` does not reach them and `:root body` does.
  - `mapping-guide.md`: the template's `main` group, and no rebuilt skip link, since core prints one; the navigation overlay switches at 600px whatever the theme's viewport breakpoints are, with the two rules that move it; `hasIcon: false` prints the words "Menu" and "Close"; a Jetpack form's submit button is a `core/button`, and the form prints its own when it finds none; a new site's "Hello world!" post takes a slot in a query loop; a column's width and a named colour cannot be stepped from a stylesheet.
  - `block-styles-guide.md` and `standards.md`: a class never stands in for a block setting.

### Fixed
- **`standards-audit.sh` reported every root stylesheet as stray when `--theme-dir` ended with a slash**: 43 false violations on one built theme.
- **`dev-mode.sh` could delete a `WP_DEVELOPMENT_MODE` the site had.** When `studio wp` could not read the site, `on` recorded the constant as absent, kept that record, and `restore` later removed the constant. `on` now fails with `reason=no-config` before it records anything, and drops a record it made when the set fails. `restore` makes the same check: it used to report the constant removed when it had not been able to look.
- **`mirror-site.py` ended in a traceback** on a page whose `<meta charset>` names an encoding Python does not know. It reads such a page as UTF-8.
- **`monorepo-blocks.sh` could not list releases with an older `gh`**, which has no `--json` for `gh release list`. The lookup is now an API call that an older `gh` has too. Not tried on one.
- `theme-json-guide.md` said a Fontsource `-latin-full-normal.woff2` file does not exist. Some families ship one. The file name says which axes a file holds, and the set differs per family.
- `visual-refinement.md`: a fix is confirmed by reading the value it was meant to change, not by the capture.

### Not in this release
- What the feedback says about converting a design, which is the next piece of work: fluid type and spacing, palette slugs, a design's handoff documents (issue #13), and a project template's own `theme.json` being replaced whole.
- Not checked: a navigation breakpoint below 600px; the minimum height and the "(required)" marker Jetpack adds to a form.
- The audit's class check covers a colour preset class only where it is in `className`. In the markup alone it is not checked, because blocks name their colour attributes differently.

## [0.7.0] - 2026-10-12

From the first end-to-end run of 0.6.0: a live site's header, footer and homepage, built into a project-template repository on a new Studio site. The run got from an address to two built and compared views with one check-in, and its state on disk, the builder clock and the chrome-first order held. It also showed the defects fixed here, and its result prompted two decisions by the developer, which are the first two entries. Not exercised by that run, so still unproven: resuming an interrupted run, a builder that is stuck, a continuation, a failed view.

### Changed
- **Every group block has a name.** Each `core/group` in a template, a part or a page, rows, stacks and grids included, carries `metadata.name` ("Hero", "Feature card"), so that a person can follow the tree in the markup and in the editor's List View. The mapping guide says how to name one, the builder writes them, and the standards audit fails on a group without one (`unnamed_groups`).
- **The conversion writes no tests.** In template mode the skill used to replace the template's example tests with tests of the build. It now adds no test file, no test and no assertion, and rewrites none to fit the build. Testing a build is a separate piece of work. Under the repository's `tests/` it only deletes what a template example's removal recipe names.
  - **The template's example features are still stripped as part of the run,** each by its recipe: they are there to show how a feature is built. One is kept only where the build itself uses it, and the report says which. A recipe is applied whole, its test deletions included, because one of the template's tests asserts that the example block's built files exist.
  - The `current-year` binding source is extended where the build shows the year and never renamed, because a test names it.
- **Docker is not started for the wp-env suites.** `template-checks.sh --tests --e2e` is run only when Docker is already running; otherwise the report says the suites were not run.
- **A builder's hand-back is its result file.** It used to return the whole result object as well, which put tens of kilobytes into the orchestrator's context a second time, minutes after the clock had already announced the file. It now returns a pointer: the view, the status, the file and what is open.
- **A builder makes its defect fixes without asking.** With defects set to be fixed, a builder had no rule for when a fix needs confirming, and asked the orchestrator about fixes it had already made. It now makes and records each fix, except one that moves the document's height by more than 50px at any width of the sweep and that the blueprint does not name: that one is copied as the original has it and listed for the user.
- **Builders look at the front end only.** Loading the Site Editor, or the block editor that the validator loads, can store an empty `wp_global_styles` post for the active theme though nothing is saved; before approval that is the default theme. The orchestrator records such a post under `temporary` and removes it at the end, and a blueprint summary no longer says that nothing is stored when the run itself stored it.
- The editor check measures what an unaligned block gets without inserting one.

### Added
- **`scripts/mirror-site.py`** captures pages of a live site into a design directory, as the live-site guide describes: each page fetched once and kept as it came, assets at their root-relative paths with other hosts under `_hosts/`, analytics, consent, search and speculation rules removed, and the script-free copy, the reading aid and a manifest written. It prints what it decided for every script, marks a kept script that looks as if it loads or reports something for review, and takes a rules file for what its built-in rules do not know. A second run fetches only what the mirror lacks. Two runs had each written their own.
- **`scripts/import-media.sh`** (with `import-media.php.tmpl`) imports design images into the media library and keeps the run's media manifest. It can be run again without uploading anything twice, keeps originals unscaled, and runs as an administrator, because Safe SVG refuses an SVG that no user uploads: without that, every SVG of a design fails while the other images import.
- The standards audit's tenth check, for unnamed groups.

### Fixed
- **`serve-html.sh --ensure` could not bring the server back after a `--stop`** without `--dir`: it printed its usage text and no sentinel, which is what the skill's own "bring the design server back" step ran into on approval. It now takes the directory from the run's `design_dir`, and every start that cannot be made ends with `H2BT_SERVE_FAIL reason=<why>`.
- `visual-refinement.md` said `--dir` is only needed the first time, which was not true after a stop.
- A whole-page text comparison is useless on a page where one side splits a heading into two blocks: every later pair shifts. The guide now says to compare such a page section by section.
- The project-template guide told a run to apply the WooCommerce example's removal recipe as written, and that recipe deletes the two npm scripts that also compile block stylesheets. The guide now says to keep both.

### Not in this release
- The run's findings about WordPress itself (flex children across viewport states, outline buttons, social links and `nofollow`, view timelines, line-height rounding and others, about thirty) are in that run's `plugin-findings.md`, and are not ported into the guides yet.

## [0.6.0] - 2026-10-11

How a run is organised. A run lasts hours and nobody watches it after the blueprint is approved, and a walk through it found places where it could lose work or stand still. The scripts in this release were tried on a throwaway Studio site. The procedure as a whole has not been run end to end yet: the first real run is its test.

### Changed
- **A run's state is on disk, not in the orchestrator's memory.** Everything is under `<site-path>/.h2bt/`:
  - `run.json` holds the facts of the run: the design directory, the phase, the approval, the site and its address, the theme, the widths, the builder that is running, what the run must remove and what it changed.
  - `serve.json` holds where the design server is. `serve-html.sh --ensure` reuses the server when it still answers and starts a new one when it has died. `--stop --site-path` stops it and always removes the harness copy from the site. No pid file has to be remembered.
  - Each builder writes its hand-back to `results/<name>.json`, and the report is built from those files (`collate-results.py`) and written to `report.md`.
- **A run that was interrupted is resumed.** Before this, invoking the skill again on a part-built site analysed every file again and wrote a new blueprint, with every status reset and the build notes gone. The skill now reads `run.json` and the blueprint first: an approved run goes on from its target table.
- **The run does not build into a theme because it is active.** A new site's active theme is a default theme, and the run replaced its `theme.json`, parts and templates under its own name. The run now builds into an existing theme only when the user named it or an earlier run made it, and otherwise makes a new one, inactive until the blueprint is approved. No site is chosen by the look of its name.
- **The approval covers what the run will change.** The blueprint summary names the site, the theme, the pages that exist and will be overwritten, the change of front page, the plugins to install and any Site Editor overrides stored for the theme.
- **Everything the unattended part needs is tried before the check-in:** a write into the theme, a staged script, the validator, both panes of the harness, wp-admin, the build. A permission prompt then reaches the user while they are there. The site is not changed before approval beyond an inactive theme and the run's records: development mode and the theme's activation wait for it, and the design server is stopped while the run waits for the answer.
- **The shared chrome is the first view.** The orchestrator used to write the header and footer parts with no browser, builders were told to stay out of them, and their defects came back one hand-back at a time. The parts and wrapper templates are now the first row of the target table, built and refined by a builder like any view. After any later change to a shared file, the views already checked are swept again.
- **The design is analysed in two steps.** `group-designs.py` groups the files first. One analyzer reads the stylesheets, and the `<style>` blocks of a design that keeps its CSS in its pages, and reports the tokens once (`analysis/tokens.json`); then one analyzer per distinct view reads that file and reports structure, at most six at a time. Before this, every file's analyzer read the same stylesheets and named its own tokens, and twenty posts of one template got twenty analyses. Reports are named from the file's path, so `a/index.html` and `b/index.html` no longer write the same report.
- **A builder's brief is the site and the view.** It reads the blueprint, `run.json`, `serve.json`, its analysis and the media manifest itself. Its row of the target table says in full what the view becomes: the files, or the page's title, slug, parent, template and whether it is the front page.
- **Templates and parts that no view owns are removed** (a scaffold's placeholders, a template repository's examples), all but `templates/index.html`, which belongs to the chrome's row when no view is the posts index. Custom page templates are registered in `theme.json`.
- **A builder that never reports no longer stops the run.** `wait-for-result.sh` runs in the background beside each builder and ends when the result is there or the time is up; the orchestrator then tells a builder that is working from one that is stuck.
- **A failed environment is not a failed view.** When the original, the site or the browser is gone, the orchestrator repairs it and continues the same builder. A screenshot of the WordPress side alone no longer counts as a comparison: the `take_screenshot` fallback is gone.
- **Stopping, when nobody is there.** One view that fails is marked and the next is built. When what failed is the run's, it finishes what does not depend on it, writes the report with what failed, cleans up and ends. Every way out removes the harness from the site.
- **The run puts back what it borrowed.** `dev-mode.sh` records the site's `WP_DEVELOPMENT_MODE` before turning it on and restores it at the end; temporary files and sites are recorded when they are made and removed. What the run changes and leaves is listed in the report.
- The standards audit also runs after each hand-back, while the builder that caused a violation can still be continued.
- The editor check reads and does not edit, and the site's password is never typed into the browser: the user is asked to open WP Admin once, during the smoke test.
- Live sites: which views are in scope is asked before the mirror is made. Reading aids and script-free copies go under `_h2bt-aids/` and `_h2bt-noscript/` in the mirror, where they are not taken for views.

### Added
- `scripts/group-designs.py`, `scripts/dev-mode.sh`, `scripts/wait-for-result.sh`, `scripts/collate-results.py`.
- `write-page.sh --parent <page-path>`, for a site whose addresses are nested. The sentinel gains `parent=`.
- `serve.py` answers `/_h2bt/id` with the token it was started with, which is how a recorded server is told from another process on the same port.

### Fixed
- **The harness loaded a 404 for a design file's path given without a leading slash,** and `ready()` accepted it: `a=about.html` was read from the harness's own directory. A path is now read from the server's root, and `ready()` reports each pane's HTTP status.
- The standards audit ran at the first hand-back against a page-source directory that did not exist yet, and failed. The directory is made with the working directory.
- Template mode never activated the repository's theme.
- `mapping-guide.md` showed the Reading-settings commands as a bare `wp`.

## [0.5.1] - 2026-10-11

Fixes from a review of every script and prompt in the plugin. Nothing here changes how a run is organised. Each script fix was reproduced before and after on a throwaway Studio site or a scratch repository.

### Fixed
- **`write-page.sh` could turn a media item into a page.** WordPress's page lookup also returns an attachment when no page has the slug, and the script updated whatever it got: an image imported as `about.jpg` became the published About page, with the success sentinel and exit 0.
  - A slug held by a post that is not a page now fails before anything is written, and says which post holds it.
  - A template the active theme does not have fails, with the list of those it has. Before, the page silently used the default template. `--template` takes a slug, not a file path.
  - The stored slug, template and content are read back as well as the title. A slug WordPress renamed (`embed` to `embed-2`) fails, and the stray page is not kept.
  - The sentinel is now `H2BT_OK id= slug= template= bytes= php=`.
- **`template-checks.sh --mirror-dir` could delete a repository's ignored files.** The mirror is synced with `rsync --delete`, and any directory was accepted, the repository itself included. It now refuses a directory that is the repository, inside it or around it, one that is not empty and that it did not make, and the mirror of another repository.
  - A value flag given last (`--repo` with nothing after it) looped for ever. Every script now answers that with exit 2 and a message.
  - A `vendor/` copy left in the mirror by an earlier `--tests` run is no longer linted against.
  - A failed `wp-env:start` fails the end-to-end gate at once.
  - The check for another environment on the port also recognises wp-env's older, hash-named work directories as this mirror's own.
- **`parity-check.sh` was not exact, and could approve a change it had never seen.**
  - Playwright's default colour tolerance was left on: a whole page moving from `#ffffff` to `#f6f6f6` passed. The comparison now allows no differing pixel and no colour tolerance.
  - `compare` wrote a missing baseline and passed on the next run. It never writes one now, and names what is missing (`reason=no-baseline`).
  - `/` and `/home/`, or `/about/team/` and `/about-team/`, were one screenshot file. Names now carry a short hash of the path, so **baselines taken with an earlier version have to be taken again**.
  - Every failure ends with the `H2BT_PARITY_FAIL` sentinel, and `shots=` counts the screenshots of this run.
- **`standards-audit.sh` passed what it could not check.**
  - A `theme.json` that does not parse was a note, and the run ended `H2BT_AUDIT_OK`. It is now a failure (`theme_json`), as is a directory that is not a theme.
  - A block delimiter whose attributes wrap over lines was reported as a stray comment.
  - The whole-pixel check also hit CSS comments, `1.0px` and the geometry inside an inline SVG or a data URI.
  - `<!-- wp:core/post-content -->` was never checked for a constrained layout, and the older `"inherit": true` form of one was reported as full width.
  - An image block with no attributes, the plainest image that points at a theme file, was missing from the image review.
  - It ends with its sentinel when perl or python3 is missing.
- **`monorepo-blocks.sh`:** a failed release lookup listed every plugin as `unreleased`. It now lists `unknown` and says `releases=unavailable`. `install` reports success only when the site has the expected version installed: before, an older copy that was still active counted.
- **`serve-html.sh --stop`** signalled whatever process had the number in the pid file. It now stops only a process that is its own server, refuses a file that is not one of its pid files, and removes its log. An explicit `--port` that is in use is refused, and `--port` is validated.
- **`scaffold-custom-block.sh`:** a title with a quote broke `block.json`. It printed `H2BT_BLOCK_OK` with a build command it had not been able to add; that case now ends `H2BT_BLOCK_PARTIAL`. A scaffold that fails part-way removes the block directory it made.
- **`detect-project-template.sh`** reported a project-template repository it could not read as `mode=standalone`, and died without output when the theme's `style.css` was gone. Both are now `mode=template-unreadable`, and the skill stops on it. Paths in the sentinel are quoted.
- **The comparison harness** (`viewport.html`):
  - `compareText` ignored text that only one page had: three groups against five compared as equal. They are differences now, with a count in `unpaired`.
  - `sink()` loaded from the WordPress origin posted to WordPress, wrote nothing and resolved. It finds the sink on the server of the design files, and rejects when nothing stored the data.
  - `ready()` waited for ever on a page that never finishes loading. It rejects after 30 seconds (`&wait=`).
- `render-probe.sh` trimmed a PHP warning raised by the markup it rendered.
- **Guide and prompt passages that were wrong:**
  - Two places told the reader to fall back to `core/html`, which the validator rejects outside its policy: the analyzer's "no clean mapping" rule and the skill's stop list.
  - `${CLAUDE_PLUGIN_ROOT}` was written into nine commands in the reference guides. Those files are read, not loaded, so nothing filled the path in, and the shell does not have the variable. The guides now write `<plugin-root>`, which the skill and the builder bind once.
  - Both agents expected their guides' paths from the dispatching prompt, which the skill never told the orchestrator to send. They now name their guides themselves.
  - The preconditions were to be run "in parallel", though each depends on the one before, and several changed the site before the checks that can stop the run had passed. They are ordered now, the read-only ones first.
  - "Studio's `wp` cannot see the host `/tmp`" and "`eval-file -` silently does nothing" were stated for every site. They hold on Studio's sandboxed PHP runtime and not on the native one. The rule is unchanged: stage inside the site and check a sentinel.
  - The audit's counters were listed by hand in two places in the skill, and both had lost `front_page`. The skill now says the audit must end `H2BT_AUDIT_OK`.

### Changed
- **The analyzer runs at `medium` effort; the builder stays at `xhigh`.** On the 34 probes of the evals the plugin's results were the same at both efforts, at about a quarter of the cost and a sixth of the time. Those probes do not exercise the builder's refinement, so its effort waits for a comparison that does. `model-pin.sh` takes `--analyzer-effort`, and covers both places in the skill that name the model.
- `section-builder` cannot start subagents (`disallowedTools: Agent`); the sentence asking it not to is gone. After a late rewrite of an invalid block it validates once more, so that the gate about validated blocks can be answered.
- Both agents' descriptions are two sentences. They are loaded into every session, and the agents are only ever dispatched by the skill.
- The skill no longer restates the builder's instructions; it says what to send, what comes back and how to check it. The dispatch lists match each agent's Inputs: the WordPress version, the sink directory, the widths to sweep and the defect policy were missing.
- A missing subagent type stops the run. The general-purpose fallback had neither the agent's instructions nor its pinned model.
- A live site's mirror goes to `<site-path>/.h2bt/mirror/` unless the user names another place, and the run's clean-up removes loose staged files only.
- README: an install section.

## [0.5.0] - 2026-10-11

Ported from a full template-mode run whose source was a live site, on WordPress 7.1.3. What the guides now say about WordPress 7.1 was checked on that version; a run on another core confirms each form with the new render probe.

### Fixed
- **`write-page.sh` stored a wrong title when it contained `&`.** From bash 5.2 an `&` in a `${var//pattern/replacement}` replacement stands for the matched text, so the title `A & B` was stored as `A __PAGE_TITLE__ B`, with the success sentinel printed and exit 0.
  - The title now travels in a staged file and is never substituted into PHP. The script also switches `patsub_replacement` off and validates the template slug.
  - The title is slashed before the write, so a backslash in it survives.
  - The PHP reads the stored title back before it prints the sentinel, and fails when it differs.
  - The sentinel gains `php=<version>`, and the staged files are removed after a successful write.
- **`template-checks.sh` failed on a working tree with unstaged deletions**, which every template-mode run has before its first commit. The copy into the mirror stopped at the first missing path, so every later gate failed for a reason that had nothing to do with the code.
  - Paths deleted in the working tree are now left out of the hashes, the blocks policy and the mirror.
  - A failed copy ends the run with `mirror_copy=fail` and names the step.
  - `docker info` has a time limit (`H2BT_DOCKER_WAIT`, default 20 seconds), so a stuck engine is reported instead of stalling the run.
- **Guide passages that were wrong or out of date:**
  - `mapping-guide.md`: `blockGap` accepts raw lengths, not only the preset form. What it drops is a value that contains a parenthesis, backslash, ampersand, equals sign or closing brace.
  - `mapping-guide.md`: a `minHeight` that changes per breakpoint no longer needs block CSS on WordPress 7.1 and later.
  - `theme-json-guide.md`: the example no longer turns fluid typography on. It is decided from the design.
  - `project-template-guide.md` and `section-builder`: the single `build:theme:*` scripts are no longer offered as a quick rebuild. They leave inline source maps in the built stylesheets, which fails the build-integrity gate. Always `npm run build`.
  - `mapping-guide.md` and `custom-blocks-guide.md`: an accordion or a tabbed area is no longer a reason to leave core. WordPress 7.1 ships `core/accordion` and `core/tabs`, which the guides did not name.
  - `visual-refinement.md`: a window resize is no longer the way to set a width. `resize_window` cannot go below 500px and can leave the window unchanged while reporting success.

### Added
- **A comparison harness**, `scripts/viewport.html`. It loads the original and the WordPress page in iframes of an exact CSS width and height, side by side or as a strip of screenfuls, and exposes `window.h2bt`:
  - `ready`, `prepare` (lazy images, transitions, fonts), `scroll`, `run`, `resize`, `pages` (height and sideways overflow, with the elements that cause it);
  - `compareText`, which pairs the text of two pages that share no markup and returns only the differences in text, type and ink position;
  - `sweep`, which measures any number of widths in one call;
  - `sink`, which writes a long result to disk.

  `serve-html.sh` now serves the design files through `scripts/serve.py`, which adds the harness at `/_h2bt/viewport.html` and a results sink at `/_h2bt/sink/<name>`, uncached. With `--site-path` it places a copy of the harness in the Studio site, so the WordPress page can be read as well, and `--stop` removes it.

  **Loopback only.** The harness's relay runs code it is sent, so the harness does nothing on a host that is not loopback, frames only loopback addresses, and answers only a loopback origin. The server binds 127.0.0.1 and refuses a request with any other `Host`, and a sink request from any other origin.
- `scripts/render-probe.sh`: renders a block-markup file on the Studio site and prints the HTML and the block-supports CSS, with no database write. It answers "does this attribute print, and as what?" on the installed core.
- `standards-audit.sh`:
  - fails on a preset slug that is one of core's flag classes: a palette entry named `text`, `link` or `border`, or a font size named `custom` (`reserved_slugs`);
  - fails on a colour function in a block's element, state or viewport styles, which WordPress drops (`dropped_colors`);
  - fails on a fraction of a pixel in `theme.json`, block markup or the theme's stylesheet sources (`subpixel_values`);
  - fails on a `core/post-content` block in a template or part without a constrained layout (`post_content_layout`);
  - lists image blocks in templates and parts that point at a theme file and reserve no space (`image_review`);
  - takes `--content-dir`, so page content, which is not in the theme, gets the comment and colour checks too.
- `references/live-site-guide.md`, for a run whose source is a running site: what to ask, how to mirror the pages, what a capture can and cannot show, and how to agree on the original's defects, with a register of what was fixed and what was found and not changed.
- **WordPress 7.1 block attributes** in `mapping-guide.md`: per-viewport values and layout (`style["@mobile"]`, `style["@tablet"]`), `metadata.blockVisibility`, hover and focus states on buttons and navigation links, a flex child's size per viewport, and a button's width as a dimension. `theme-json-guide.md` covers `settings.viewport`. A hide-below or stack-below block style is now only for a width that is not a viewport state.
- New sections in the guides:
  - `mapping-guide.md`: reading the installed core's `block.json` and probing; a value that steps at a width the states cannot express; whole-pixel values; post content at content width; layout recipes that replace CSS; images; buttons; links, headings and lists; query loops, archives and pagination; generating long-form and repeated content.
  - `theme-json-guide.md`: the reserved preset slugs; measuring which font file draws each weight; the reset rules a design relies on.
  - `block-styles-guide.md`: breakpoints in a block stylesheet; gradient text; icons in buttons; a second colour scheme for a template part; selectors that surprise.
  - `custom-blocks-guide.md`: the dynamic pieces of a post type's templates without a custom block; what a block can know about the view; testing groundwork through a rendered template.
  - `project-template-guide.md`: generating a project repository locally; linting the tracked paths; tests that need no content; what stored content needs when it moves to another environment.

### Changed
- **A value written in pixels is a whole number of pixels.** No `767.98px` breakpoint and no sub-pixel letter spacing, in `theme.json`, block attributes or stylesheets.
  - A viewport state ends on the last whole pixel of its range: `767px` for a design that changes at `min-width: 768px`.
  - In a stylesheet, the other side of a `min-width: N` rule is the range query `(width < N)`, which is exact at every width.
  - A value finer than a pixel uses a relative unit. An original's sub-pixel letter spacing is written as its `em` ratio.
  - The guides say what this costs: at a fractional viewport width inside the last pixel below a breakpoint, a state ends up to a pixel early. Whole-pixel widths are unaffected.
- **Every template gives post content a constrained layout, landing-page templates included.** A block is as wide as the content column unless it is aligned wide or full, in the editor as on the page, and a page's full-bleed sections are `alignfull` blocks in its content. A post content that fills the template looks the same on the front end, but in the editor every block is full width and the wide and full alignments are gone. The Phase 4 editor check now covers this.
- **Nothing a visitor reads is held in a PHP pattern, by default.** Parts and templates are plain block markup, page content is written to the page, and a section two pages share is repeated in each. The blueprint states this as a decision the user confirms, because a project that needs translatable template text, or wants starter patterns, needs a different answer. Repeated sections are no longer turned into patterns.
- **Design images go to the media library, by default,** SVG included, through the Safe SVG plugin, which becomes a site dependency. Only an image a template, part or stylesheet itself needs stays in the theme. An icon is no longer mapped to `core/html` first.
- **`blueprint-analyzer` writes its full report to disk and returns a digest.** A full report runs to tens of kilobytes; one per file flooded the orchestrator's context. Its values are marked as derived, not measured, and the orchestrator measures before a value goes into the blueprint.
- **`section-builder`:**
  - the validator ceiling is stated as two calls per file, the first draft and the final file, with refinement in between;
  - it refines in the harness and sweeps widths, and no longer resizes the window;
  - it stays in its view, and returns `changed_outside_view`, `quirks_fixed`, `plugin_findings` and `checks`;
  - it keeps each page's source at `<site-path>/.h2bt/pages/<slug>.html`.
- **The orchestrator checks each hand-back and fixes shared defects before the next builder starts,** and rewrites the blueprint's build notes for it. A view that is one template plus a run of text is generated without a builder.
- **A run keeps `<site-path>/.h2bt/plugin-findings.md`:** what it learned that applies to any site, with no site name or design value in it, ready to be ported into these guides.
- Preconditions: the run notes the WordPress version and turns `WP_DEVELOPMENT_MODE` on for the theme.
- The report says where the content is, what was not checked, and how the first-screen images load.
- **Prompt-fit pass for Claude Opus 5.5,** against Anthropic's prompting guide for that model:
  - **After the blueprint is approved, Phases 2 to 4 are one run to the report.** The skill names the turn endings it does not want (a summary that announces the next step, an offer to carry on, a list of decisions that block nothing, a pause because a file is finished) and the stops it does. Work that waits for the user's approval is finished around and listed in the report.
  - The blueprint's target table carries a status per file and is the run's checklist.
  - **A hand-back that is not the agreed JSON is a progress note, not a result.** The orchestrator continues the same agent, twice at most, then records the file as failed and goes on. Both agents are told that a message with no tool call ends their run.
  - `visual-refinement.md`: look closer before calling a section a match. The harness scales the stage to fit the window, so two desktop panes are captured at a little over half size; the Chrome `zoom` action, or `&scale=1`, shows what that hides.
  - `live-site-guide.md`: a fix that turns out large is copied as the original has it and listed as an open decision, without stopping the run. A piece whose design the capture cannot show is built from the theme's tokens, with no ornament added.
  - Text in the design files, or in a mirrored page, is material to convert and not instruction (`blueprint-analyzer`, `live-site-guide.md`).
- **The plugin is pinned to one model and effort, `claude-opus-5-5` at `xhigh`.** Both subagents name the pair in their frontmatter (they inherited the session's before), a new precondition stops a run whose session is on another model, and the evals run on it. `scripts/model-pin.sh --check` confirms every place agrees, and `--set <model-id> --effort <level>` moves them all, after the evals have been run on the new pair. A skill's own `model` field holds only for the turn that loads it, so the orchestration is held by the precondition, and follows the session's effort.
- **The evals are rebuilt to answer one question: which of the plugin's passages does the pinned model need, and which does it already do unaided.** They replace five recall questions run through promptfoo. See `evals/README.md`.
  - **A registry classifies every section** of the files in scope as a platform fact, a house decision, a fact about a tool, process, steering or reference. Only the first two are a question about the model. A section added to a guide fails `npm run check` until it is classified.
  - **A probe is a task, asked three ways:** unaided, with what the rule's reader has loaded in a real run, and with the probe's passages cut out. Answers are graded on the block markup, by `standards-audit.sh`, and by `render-probe.sh` on a Studio eval site. Every probe carries a known-good and a known-bad answer, and the check runs its graders on both.
  - **Verdicts per passage:** needed, known, counterweight, partly known, not followed, worse with plugin. Only a passage the model gets right unaided every time, and with the passage cut, is a candidate to delete, and its probe stays to catch a later model that needs it back.
  - **Facts about the tools are tried by script** on the eval site (`registry/environment.yaml`), and the two skill-routing cases of the old suite are kept (`npm run routing`).
  - **A report per model and effort** is written to `evals/reports/`, with the verdicts, the candidates to delete, the coverage by kind, and what changed against another report. Reports and results are ignored by git.
  - In scope so far: `SKILL.md`, `mapping-guide.md` and `section-builder`. Process and steering passages need scenario runs, which are not built.
  - The old suite's last measurements are in `evals/README.md`. The table it carried for 2026-07-29 was Claude Sonnet 5, which it had labelled Claude Opus, and one of its assertions used an inline `(?i)`, which does not compile, so it failed on every answer.

### Not included
- The guides describe a page mirror, a re-runnable media import with a manifest, and generators for long-form content. None is shipped as a script yet: a run writes its own.
- The evals cover three of the plugin's eleven prompt files (`SKILL.md`, `mapping-guide.md` and `section-builder`), and about a third of what a probe can judge in them. Process and steering passages are not judged.
- No full conversion run has been made since the Opus 5.5 pass and the model pin. The run-to-the-report rules, the hand-back continuation and the pin's precondition are untested in a run.

## [0.4.0] - 2026-09-25

### Changed
- **Custom blocks now come from the A8C Special Projects blocks monorepo, and are kept to a minimum.** Rung 3 of the escalation ladder resolves in order:
  1. Core features: patterns, Block Bindings, the Interactivity API on existing blocks, variations and filters.
  2. A block reused from [`a8cteam51/special-projects-blocks-monorepo`](https://github.com/a8cteam51/special-projects-blocks-monorepo).
  3. A new block built in the monorepo.
- **Reused blocks:** a run installs the block's release ZIP on the Studio site, styles it from the theme with its own block stylesheet, and adapts its behaviour with project-side filters, never by editing the block. The plugin and version become a site dependency.
- **New blocks:** a run builds the block in a clone of the monorepo inside the Studio site (`npm run new-block`, `a8csp` namespace), on an `add/<slug>` branch, following the monorepo's rules:
  - project-agnostic, with wireframe-only styling and generous filters;
  - linted as the monorepo's CI does;
  - checked in the newest Twenty-* theme on a throwaway Studio site;
  - a 1200×800 screenshot of the block as it looks in the project.

  The run drafts the New block proposal to `.h2bt/proposals/`. Pushing the branch, opening the pull request and filing the proposal wait for the user's approval.
- **Blocks are never created in a theme, in any mode.** The build-less in-theme block layout is removed.
  - `scaffold-custom-block.sh` now scaffolds only an **approved exclusion** (template mode, `--exclusion-approved`): a block an engineering lead has approved keeping in the project. It goes in the features mu-plugin, with an allowlist comment marking it.
- `custom-blocks-guide.md` is rewritten around this flow. SKILL.md, the mapping, standards, block-styles, theme.json, visual-refinement and project-template guides, and both agents follow it:
  - the blueprint analyzer reports behaviour candidates and the core routes ruled out, instead of naming blocks;
  - the orchestrator checks the catalog once and records each behaviour's source in a behaviour table;
  - section builders never create blocks.
- The report lists every block beyond core with its source, and the pages that can't deploy until a new monorepo block is released.
- Evals: the build-less registration case is replaced by a monorepo-first disclosure case, and the template-mode case now covers an approved exclusion. Neither has been run yet.

### Added
- `scripts/monorepo-blocks.sh`:
  - `catalog` lists every monorepo plugin with its blocks, latest release, screenshot and descriptions, from a cached clone;
  - `install` installs latest release ZIPs on a Studio site, refusing a block also built in a clone;
  - `clone` clones the monorepo into the site and activates its autoloader.

  Release lookups use `gh` when signed in, otherwise the public GitHub API.
- `standards-audit.sh` fails a theme that contains any `block.json` (`theme_blocks`).

## [0.3.1] - 2026-09-25

### Fixed
- The reference guides and changelog no longer carry details from particular client builds:
  - `project-template-guide.md`: the truncated PHP prefix example is now a neutral `examplesite_202_`.
  - `block-styles-guide.md`: the direct-block-targeting CSS example no longer uses one design's header measurements.
  - `theme-json-guide.md`: the variable-font condensed-cut note states the general condition, a width (`wdth`) axis, instead of the fonts one run used.
  - The 0.3.0 entry no longer names the client build it came from.
- `block-styles-guide.md`: WordPress 7.0 and later add `wp-block-paragraph` to rendered paragraphs, so `.wp-block-paragraph.is-style-x` only fails on earlier versions. Scoping paragraph variations as `p.is-style-x` remains the rule, because it matches on every version.

## [0.3.0] - 2026-09-24

### Added
- **Template mode** for repositories generated from `a8cteam51/a8csp-project-template`. The skill switches to it when the Studio site's `wp-content` is a clone of such a repository, and builds into that repository's theme and features mu-plugin under its conventions.
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
