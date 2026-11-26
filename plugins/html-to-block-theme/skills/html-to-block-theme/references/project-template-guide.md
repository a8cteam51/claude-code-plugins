# Project template guide (template mode)

Template mode is on when the Studio site's `wp-content` is a git clone of a repository generated from [`a8cteam51/a8csp-project-template`](https://github.com/a8cteam51/a8csp-project-template). The run then builds into that repository's theme and features mu-plugin instead of a standalone theme.

**What this guide overrides and what it keeps:**
- It overrides the file locations and wiring in `block-styles-guide.md`, `custom-blocks-guide.md`, and `standards.md` § Theme structure.
- Every other rule is unchanged: the escalation ladder, one stylesheet per block type, registered block styles as the only CSS hooks, the core/html policy, and the homepage rule.

## Detect and bind

```bash
bash "<plugin-root>/scripts/detect-project-template.sh" --site-path <site-path>
```

The last line is `H2BT_TEMPLATE mode=template …`, `H2BT_TEMPLATE mode=standalone reason=…` or `H2BT_TEMPLATE mode=template-unreadable reason=…`. The last one is a project-template clone whose theme could not be read (no single tracked theme, or its `style.css` is gone from the working tree): stop and fix that, and never build a standalone theme into the repository. Paths in the sentinel are quoted. In template mode, bind these from the sentinel for the rest of the run:
- `<repo>`, the site's `wp-content`;
- `<theme-dir>`, which is `themes/<theme_slug>`;
- `<features-dir>`, which is `mu-plugins/<features_slug>`;
- `<prefix>`, the text domains, and the PHP, WordPress and Node floors;
- `examples`: the template's example features still present.

**The user named a template repository, but `wp-content` isn't a clone yet.** Set it up with the `studio-repo-clone` plugin rather than cloning by hand:
- `clone-into-existing-site` for an existing site. It keeps the database, uploads, plugins and themes.
- `clone-new-site` for a new site.

`clone-into-existing-site` doesn't move loose `mu-plugins/*.php` files back from `wp-content-temp`. Copy local-only ones back yourself, such as a Jetpack offline-mode shim. The template's `.gitignore` already excludes `mu-plugins/*`.

**There is no repository yet, and the user has not approved creating one on GitHub.** Generate it locally:
1. Run the template's fill-in workflow by hand on a fresh `git init` of the template tree: rename, substitute, re-resolve both lockfiles, format, build, syntax-check, and remove the spent workflow.
2. Hand the result to `studio-repo-clone` as a local path.
3. Remove the `origin` remote, which points at the temporary directory.

Creating the GitHub repository and pushing stay the user's decision. Say in the report that the repository exists on this machine only.

## Preconditions (template mode)

0. **No one else's work in the way.** On a new run (one that is not the resumption of an earlier one), a working tree with uncommitted changes, or one whose theme no longer holds the template's example patterns and templates, holds work that is not this run's. Say what the run would replace (`theme.json`, the parts, the templates) and ask before going on. Uncommitted work is the only kind that cannot be got back.
1. **A feature branch.** `trunk` deploys to production and `develop` to staging, so never build on either. Use the repository's branch prefixes (`add/`, `feature/`, `fix/`, `update/`, `remove/`), for example `git switch -c add/block-theme`.
2. **The site runs the PHP floor.** Run `studio site set --path <site-path> --php <php_floor>`, and record the version it had under `changed` in `run.json`: the report says that it was changed. Below the floor, the features plugin prints an admin notice and loads nothing, so its blocks and redirects silently disappear.
3. **Toolchain.**
   - Node must meet `engines.node`; switch with `nvm`.
   - Composer needs a PHP CLI at or above the floor. `a8csp/configs` requires it, and `--ignore-platform-req=php+` only lifts *upper* bounds. Studio keeps its PHP builds in `~/.studio/php-bin/<version>/php`, so put that directory first on `PATH`. Switching any site to the floor version downloads it.
   - Install with `npm` the way the user normally does. Some users alias it through a security wrapper.
4. **Dependencies.** Run `composer packages-install` and `npm ci` in `<repo>`.
5. **Docker**, only if the integration or end-to-end suites will run.

## Permanent identifiers

The template's CI, tests and wp-env configuration depend on these. Read them from the detection output, and never rename them.

| Identifier | Rule |
| --- | --- |
| Theme directory, theme text domain | `themes/<theme_slug>` and `<theme_slug>`. Replace the theme's *contents*, never its name. |
| PHP prefix | Taken verbatim from `<theme-dir>/.phpcs.xml`. It can look truncated (for example `examplesite_202_` for a repository named `examplesite-2026`). Theme globals use `<prefix>theme_*`; features globals use `<prefix>features_*`. That includes `render.php` variables. |
| Features text domain | `<features_slug>`, used in every features PHP and JS string. |
| Block namespace, pattern slugs | `<theme_slug>/<name>`. |
| Pattern category | `<theme_slug>`, which the theme registers (`mapping-guide.md` § Where content lives). |
| CSS classes, keyframes, custom properties, data attributes, handles | Prefixed `<theme_slug>-` (for example `<theme_slug>-block-core-image`). |
| Post type keys | Prefixed `<prefix>` and **at most 20 characters**: WordPress refuses a longer key, and PHPCS fails it (`WordPress.NamingConventions.ValidPostTypeSlug.TooLong`). A long prefix leaves room for a few letters only (`examplesite_202_` leaves four), so agree a shorter key with the user before content exists: every post stores it. |

## The theme contract the template's tests encode

- **`functions.php` stays as the template ships it:** the slug helper, the asset-metadata helper, and the loader for `includes/*.php`. Add code as new `includes/<concern>.php` files, one concern each, with typed signatures.
- **`includes/theme-setup.php` keeps the handles the tests check:**
  - the body class `<theme_slug>`;
  - `<theme_slug>-style` (`get_stylesheet_uri()`, with RTL `replace`);
  - `<theme_slug>-script` (from `assets/js/build/index.js`, versioned from `index.asset.php`);
  - `add_editor_style( 'style-editor.css' )`.

## Where each piece goes

| Standalone build | Template mode |
| --- | --- |
| `theme.json` | `<theme-dir>/theme.json`, replaced wholesale. |
| Root `style.css` rules | Sass partials under `assets/sass/`, built to `style.css` (plus `style-rtl.css` and `style-editor.css`). The theme header lives in `assets/sass/style.scss`. Put responsive token overrides (`:root:root`) in a partial that both `style.scss` and `style-editor.scss` load, and the root layout rules too (`mapping-guide.md` § Layout traps), since they are written for the editor as well: the template's `style-editor.scss` loads only `base`, so a rule in `layout/` never reaches the canvas. |
| `assets/css/blocks/<block>.css` | `assets/sass/blocks/<block>.scss`, built to `assets/css/blocks/<block>.css`. The template builds `assets/css/src/` into `assets/css/build/`; the foundation points its scripts at this layout instead (§ Build pipeline), so every Sass source sits under `assets/sass/` and every built stylesheet under `assets/css/`. |
| `register_block_style()` and `wp_enqueue_block_style()` in `functions.php` | `includes/block-styles.php`. Enqueue the **built** path, and write it whole in each call, `assets/css/blocks/<block>.css`: the audit greps for that string, so a helper that adds the directory itself fails it as `UNENQUEUED`. Version it with the asset-metadata helper. |
| `render_block_*` filters | `includes/<concern>.php`. |
| `assets/js/*.js` | ES modules in `assets/js/src/`, imported by `src/index.js` and built into the one always-enqueued bundle. Each module returns early when its markup is absent. |
| Custom behaviour | The same as standalone (`custom-blocks-guide.md`): core features first, then blocks from the A8C Special Projects blocks monorepo, installed as plugins and never tracked here. Only an approved exclusion is scaffolded into the features plugin (`blocks/src/<slug>/`, `scaffold-custom-block.sh --exclusion-approved`), because page content stores it and a theme swap must not unregister it. Project-side filters that adapt a monorepo block go in `<features-dir>/includes/<concern>.php`. |
| Site-config mu-plugins (redirects and the like) | `<features-dir>/includes/<feature>.php`. The features plugin has to be enabled for it to load (§ Template example features). |
| Local-only shims (for example `jetpack_offline_mode`) | Untracked `mu-plugins/<file>.php`. Never commit them. |
| A directory a plugin writes into `wp-content` at runtime (for example Jetpack's `jetpack-waf/`) | A `.gitignore` line in the repository's own section (`/jetpack-waf/`), added when the plugin is installed. Check `git status` after each install: the template's WordPress rules cover only `plugins/`, `mu-plugins/`, `themes/`, `languages/`, `uploads/` and `upgrade/`, past its tracked entries. |
| `templates/`, `parts/`, fonts | Same paths. Parts and templates are plain block markup. |
| `patterns/` | Only when the blueprint calls for patterns (`mapping-guide.md` § Where content lives). They keep `Slug: <theme_slug>/…` and `Categories: <theme_slug>`. |
| A dynamic year or other theme-owned text | A block-bindings source in `includes/theme-dynamic-content.php`, following the template's own. |

## Build pipeline

The features-plugin block wiring below applies only to approved exclusions. Monorepo blocks build in the monorepo.

- **`package.json` edits:**
  - Build the block stylesheets from `assets/sass/blocks/` into `assets/css/blocks/`: `build:theme:css` becomes `sass <theme>/assets/sass/blocks:<theme>/assets/css/blocks && postcss '<theme>/assets/css/blocks/*.css' --replace`, `start:theme:css` gets the same two paths, and `lint:styles` drops its `<theme>/assets/css/src/**` glob, since `<theme>/assets/sass/**` covers the blocks. Quote the PostCSS glob: npm's `sh` would otherwise expand it before PostCSS sees it.
  - A `url()` in a block stylesheet is relative to the built file in `assets/css/blocks/`: a theme image is `../../images/<file>`.
  - The template's `assets/css/src/` and `assets/css/build/` then hold only its examples' stylesheets, which go with their examples. A per-purpose stylesheet the build keeps (the cart, say) moves to `assets/sass/<name>.scss`, built to `assets/css/<name>.css` by a line of its own in `build:theme:css`.
  - Add `build:features:blocks` and `start:features:blocks`:
    `wp-scripts build|start --webpack-src-dir=<features>/blocks/src --output-path=<features>/blocks/build --webpack-copy-php --blocks-manifest`.
  - Add `<features>/blocks/src` to `lint:scripts`, `format:scripts` and `lint:styles`.
  - Add every imported `@wordpress/*` package (for example `@wordpress/blocks` and `@wordpress/block-editor`) as a devDependency. Otherwise ESLint's `import/no-extraneous-dependencies` fails.
  - The exclusion scaffold does all of this except the devDependencies, which it prints as a manual step.
- **Block assets under wp-scripts:**
  - Import `./style.scss` in `index.js` and reference it as `"style": "file:./style-index.css"`.
  - Import `./editor.scss` and reference it as `"editorStyle": "file:./index.css"`.
  - `"viewScript": "file:./view.js"` builds by default. `viewScriptModule` needs `--experimental-modules` added to the build script.
  - The output directory is cleaned on every build, so never hand-edit `blocks/build/`.
- **A script module outside a block cannot be built** (an Interactivity store that adapts a monorepo block, say). `wp-scripts` (35.0.0) finds modules only in `block.json` fields: a file named on the command line is always built as a classic script, so with `--experimental-modules` the module build has no entry and fails (`configuration[0].entry[0] should be a non-empty string`). Write it as a plain ES module, register it with `wp_register_script_module()` with `@wordpress/interactivity` as its dependency, and add `@wordpress/interactivity` as a devDependency so that ESLint's import resolver finds it.
- **Rebuild with `npm run build` after every source edit, before reloading the browser. Always the whole build.** The repository's PostCSS config writes inline source maps unless `NODE_ENV=production`, and only the top-level `build` script sets it. A single `build:theme:*` script leaves a base64 source map in each built stylesheet; committed, that fails the build-integrity gate.
- **Commit the build output.** CI rebuilds and fails on any byte difference ("Build integrity"), because the committed tree is the deploy artifact.

## Template example features

Detection lists what generation left behind. **The examples are there to show how a feature is built in this repository. Read them for that, then strip them:** every example the build does not itself use is removed as part of the run, along with the theme's example content. The conversion writes no tests (§ Checks): what a removal deletes under `tests/` is the example's own tests, as its recipe names them.

- **`book-cpt`, `book-cover-reminder`, the Book Count block, `woocommerce-cart`: remove each one the build does not use,** during the foundation. A build uses an example only when it ships that very feature, such as the cart stylesheet on a site that runs WooCommerce and whose design styles the cart. A build that needs a post type or a block of its own writes it after the example's pattern, and still removes the example. Say in the report which were stripped, and which were kept and why.
- **Delete the files, and leave the index alone.** Remove them with `rm`, not `git rm`: the run commits in Phase 4, and a builder may write a file of the same name before then. One did, and the index then recorded a deletion while the tree held the new file, so a commit of what was staged would have dropped the new file.
- **Follow the recipe at the top of the example's own file, whole:** the files, the built files, the npm scripts, the allowlist lines, the tests it names and the prose it leaves false. Then run `npm run build`. A recipe applied in part fails the suite: one of the template's tests asserts that the example block's built files exist.
- **One step of the `woocommerce-cart` recipe is wrong for a build.** It has the `build:theme:css` and `start:theme:css` scripts deleted, as building only the cart stylesheet. They build the block stylesheets from `assets/sass/blocks/` (§ Build pipeline): keep both.
- **`<features-dir>/.disabled`:** generation creates it. Delete it once the features plugin carries real features, or the build's blocks and redirects never load. The plugin's examples are stripped by then: enabling it with one in place publishes the example post type on the site.
- **`includes/theme-dynamic-content.php`:** a build that shows the year uses this example. Keep its `current-year` binding source and extend it, for example with a `format` argument that places the year in a sentence. Never rename it: a test names it, and no test is rewritten to match a new name. A build that shows no year removes it by its recipe.
- **The template's example theme content** (`parts/header.html`, `parts/footer.html`, `templates/index.html`, `templates/singular.html`, `patterns/footer-default.php`, `patterns/index-query.php`, the Sass partials, `assets/js/src/index.js`): the build replaces it. The example patterns are removed, not replaced, unless the blueprint calls for patterns, and `templates/singular.html` is removed unless a view owns it.
- **The scaffold's `theme.json` values are not givens.** Fluid typography in particular is decided from the design (`theme-json-guide.md`).

## What fails CI, and the fix

- **PHPCS (WordPress-Extra plus the a8csp ruleset):**
  - prefix every global, including `render.php` variables and closures;
  - use one text domain per component;
  - start every file with `declare( strict_types=1 );` and give every function a docblock;
  - build markup strings instead of inline `<?php if (): ?>` templates;
  - align `=` in consecutive assignments.
- **PHPStan (level 8, strict rules):**
  - no `empty()`;
  - `next_tag( array( 'tag_name' => 'nav' ) )`, not `next_tag( 'nav' )`;
  - `array<string, mixed>` parameter types, with `$block['attrs']` members guarded by `is_array()`/`is_string()`;
  - `@var array<string, mixed> $attributes` in every `render.php` docblock;
  - compare `preg_match()` to `1`, and handle `preg_split()` returning `false`;
  - `WP_Query::$posts` is nullable: take the posts from `( new \WP_Query() )->query( $args )`.
- **stylelint (`@wordpress/stylelint-config/scss`):**
  - `npm run format:styles` fixes most issues.
  - A `line-height` in `rem` is disallowed. Where the design fixes the line box, keep it with `// stylelint-disable-next-line declaration-property-unit-allowed-list -- <reason>`. The description is mandatory.
  - `clip` is deprecated; use `clip-path: inset(50%)`.
- **ESLint and Prettier:** `npm run format:scripts` fixes formatting. Use `catch {}` rather than an unused `catch ( error )`.
- **Auto-fixers rewrite code.** Take a parity baseline before running them (see Visual parity guard below).

## Checks (Phase 4 in template mode)

- **Standards audit:** `standards-audit.sh --theme-dir <theme-dir> --content-dir <site-path>/.h2bt/pages` detects the template layout by itself. It checks one Sass source per block type, each built and enqueued, and counts the SCSS sources as the CSS footprint.
- **CI does not run the standards audit.** Only a run does, so a change made after the run is not audited unless someone runs it. A fix made weeks after one run shipped three fractions of a pixel: the audit passed on the run's last commit and failed on the later `trunk`. Run it on every later change before it is pushed. The `change-built-theme` skill does, with the page content that `export-pages.sh` takes from the site.
- **CI gates:** `template-checks.sh --repo <repo> [--tests] [--e2e]` runs CI's gates in order: build integrity, blocks allowlist, `composer lint:php`, `npm run lint`, then the wp-env suites.
  - **`--mirror-dir` names a directory the script owns.** The mirror is synced with `rsync --delete`, so the script refuses a directory that is the repository, inside it or around it, one that is not empty and that it did not make, and the mirror of another repository. Leave the flag out unless there is a reason to move the mirror.
  - **It works from a mirror.** The Studio site's `wp-content` also holds Studio's SQLite integration and loader. The lint scripts scan all of `mu-plugins/`, and wp-env mounts it, so checking in place reports hundreds of errors CI never sees. The mirror holds only tracked and unignored files, synced in place so wp-env's bind mounts survive.
  - **It runs before the first commit.** A tracked file deleted in the working tree, such as the template's removed examples, is left out of the mirror. If the copy into the mirror fails, the run ends with `mirror_copy=fail` and names the step.
  - **It refuses a port another wp-env instance already publishes**, because Playwright would silently test that other site.
  - **It waits for `afterStart` to activate the theme** before the end-to-end run. If you run `npm run test:e2e` yourself on a machine where the environment has never been started, start it first (`npm run wp-env:start`) and let it finish: the smoke can otherwise reach the site before the theme is active, and fail on a default theme's page.
  - **It gives Docker a time limit.** `docker info` hangs when the engine is stuck, which stalls a run with no output. A hung engine is reported as not running; restart it with `docker desktop restart`, and put a time limit on any `docker` call you make yourself.
- **Linting while building:** run the linters on the tracked paths (`vendor/bin/phpcs <theme-dir> <features-dir>`, `vendor/bin/phpstan analyse -c ./.phpstan.neon <theme-dir> <features-dir> mu-plugins/mu-loader.php`), never the repository's whole-tree scripts in place. In a Studio site those also scan Studio's own untracked files in `mu-plugins/`.
- **No tests are written.** The conversion adds no test file, no test and no assertion, and rewrites none to fit the build. Testing a build is a separate piece of work, outside this skill. Under `tests/` it only deletes: the tests of an example it removes, as that example's recipe names them, and the prose there that the removal leaves false (§ Template example features). The suites that `template-checks.sh --tests --e2e` runs are otherwise the repository's own. Run them only when Docker is already running: do not start it, and say in the report that they were not run. When one fails on the build, the answer is in the theme (§ The theme contract the template's tests encode), never in the test.

## Visual parity guard

```bash
bash "<plugin-root>/scripts/parity-check.sh" --repo <repo> --base-url <site-url> \
  --paths "/,/about/,/contact/" --mode baseline [--local-storage <popup-key>=1] [--open-disclosures]
# … change code, rebuild …
bash "<plugin-root>/scripts/parity-check.sh" --repo <repo> --base-url <site-url> \
  --paths "/,/about/,/contact/" --mode compare [--local-storage <popup-key>=1] [--open-disclosures]
```

**When to take a baseline:** before porting a theme, before running any formatter or auto-fixer, and before refactoring Sass.
- **How it captures:** full-page shots at 1440 and 390, with reduced motion, CSS animations disabled, lazy images scrolled into loading, and popups suppressed through `localStorage`.
- **Why a zero tolerance is safe:** two captures of an unchanged local site are pixel-identical, so `compare` fails on any difference: no differing pixel is allowed, and no colour tolerance either.
- **`compare` never writes a baseline.** A path or width with no baseline ends `H2BT_PARITY_FAIL … reason=no-baseline` and names what is missing. Take the baseline on the unchanged site first. Two paths that are one page (`/about` and `/about/`) are refused in one run.
- **Screenshot names carry a short hash of the path,** so that `/` and `/home/` are different files. A baseline taken with an earlier version of the script has other names and has to be taken again.
- **What it runs on:** the repository's own `@playwright/test` with local Chrome, writing to the git-ignored `tests/.cache/h2bt-parity/`.
- **Where to run it:** against the Studio site, because wp-env has no content.
- **Exactness holds on the local site.** On a hosted site two captures of an unchanged page can differ: an image CDN encodes an image again, and a lazy image can be unpainted in one take. There a shot counts only when two takes of it are equal, each load carries a cache-busting parameter, and each shot records its HTTP status and whether an admin bar was present, which is the proof that it was captured logged out. The script takes each shot once, adds no parameter and records neither: run `compare` straight after `baseline`, before anything changes, for the two takes, and check the rest by hand. Take the baseline again when the environment's state changes (§ Content and dependencies). Seen on one hosted test site.
- **A full-page shot shows every disclosure closed.** A `details` element, an accordion item and a tab panel are captured as they load, so nothing inside them is compared. For a change to content, or to a block that collapses content, capture again with every one of them open, after waiting for the images inside: a first capture with the panels forced open showed blank images. `--open-disclosures` does this: it opens every `details` element, core accordion item and tab panel in `main`, those of a `details` group that share a `name` included, waits for the images inside, and keeps those shots apart as `<name>-open.png`, so the baseline is taken with the flag too. Its `H2BT_PARITY_OK` line adds `opened=<n>`; `0` means the page has no disclosure the script knows, such as a page builder's own accordion. One regression reached a hosted test site this way, a heading at the wrong size inside a closed accordion panel. The flag was tried in Chrome on a static page built from core's rendered accordion markup, not on a page WordPress served.
- **A text comparison proves the words and their order, not the size they render at** (§ A change that is meant to move pixels). For a change that rewrites headings, record each heading in `main`, hidden or not, as its tag, its text and the computed font size and weight of that text, before and after, and compare the two records.

## A change that is meant to move pixels

Parity proves that nothing moved. A change to the template or the content of many posts that is meant to change how they look is compared by what each page says: per address, logged out and past the cache, the status, the text of `main`, its image sources, its links with their targets, its headings and the `loading` of the first large image, before and after. The plugin has no script for it. From one project, which compared two environments this way.

- **Trust a baseline only when two sweeps of the unchanged site are equal.** They are not at first: nonces, asset versions, generated ids and a form's token differ per request. Add a normalisation only for what differs between those two, each with its reason.
- **Write down the differences the change may make before making it, and still read each one once.** A blanket allowance hid real defects that sat in the diff.
- **Compare addresses as printed as well as with the site's origin taken off.** A comparison that strips the origin cannot see a relative path turn absolute, or a scheme change (§ Content and dependencies).
- **Posts a logged-out request cannot reach** (drafts, private) are rendered in process through the template the loader resolves. Reset the content media count and the high-priority flag between posts (`wp_increase_content_media_count()`, `wp_high_priority_element_flag()`): core keeps both for the whole process, so a later post's first image otherwise prints `loading="lazy"` and no `fetchpriority`. The reason was read in WordPress 7.1.4's `media.php`.
- **List what a page sweep does not reach** (feeds, calendar exports, search results, the social image, structured data), each with how it was checked or that it was not.
- **Two things neither a sweep nor a shot shows** are in § Visual parity guard: what sits inside a closed disclosure, and the size a heading renders at.

## Content and dependencies

- **Content isn't in the repository.** Page content, media and menus live in the Studio database. Deploying ships code only, and moving content to the host is the user's step (`live-site-guide.md` § The switch on the live site has what a run leaves for it, when the content replaces an old theme's). Never write to production; the repository's `AGENTS.md` treats production as read-only.
  - **Stored content names its environment.** Image blocks hold attachment ids and the local site's URLs. A full push to a fresh environment keeps them; merging pages into an existing database needs an id and URL remap. Say in the report which the project needs, and keep each page's source (`.h2bt/pages/*.html`) and the media manifest as the record a migration starts from. Whether the live page has changed since it was captured is not read from its modified time (`live-site-guide.md` § Mirror the pages).
  - **A theme file reaches every environment with the deploy, and the posts it names do not,** so it names no database id (`standards.md` § Block markup conventions). A migration list that covers pages and menus leaves out the post a template names by `ref`. The ids that stored content names (an attachment, a synced pattern, a form, a term a query filters by) are checked on the target before the content moves (`live-site-guide.md` § When the build site is a clone of production).
  - **The migration's record leaves the machine with the run.** `<site-path>/.h2bt/` is outside the repository, so a second machine has the theme and none of it. When the run ends, pack what a migration needs, and say in the report where the pack is and how it reaches whoever migrates: each page's source with its id, slug and template; the media manifest; the content of every post the run made (a navigation, a form); every list of posts it trashed or changed outside pages, attachment alt texts included; and every script it ran against a shared environment. A script run once against a hosted site is saved with the record, not left in a scratch directory. One migration was prepared on a second machine, and a page writer, a template script and a clean-up list were written again the day before it.
  - **The menu goes first.** A header whose Navigation block names no post shows the target's newest navigation post from the moment the theme is active (`mapping-guide.md` § core/navigation notes). The step that publishes the menu comes before the step that activates the theme.
- **A later change to a page's content,** or to any other post's, is a WP-CLI `eval-file` script that changes only what it must. `write-page.sh` writes the whole page, so it overwrites whatever an editor changed since. The script:
  - replaces exact strings, each with the number of matches it expects;
  - refuses a page whose counts differ, and changes nothing on it;
  - gates per post, not on totals. A count over the whole set stops matching the day one post is edited, and from then on every re-run and the script's own undo refuse. Each post has a class: to write, already written (the stored hash is the result's), edited since (neither hash), not the script's. Only a class nobody planned for refuses;
  - does nothing on a second run;
  - refuses a planned body that holds an absolute address into `wp-content/themes/`, in any scheme, or the site's own host under a scheme other than `home_url()`'s (`mapping-guide.md` § Where content lives);
  - saves a revision, calls `kses_remove_filters()` before it writes, and hands the content to `wp_update_post()` through `wp_slash()`;
  - in its dry run, runs the content save filters that are still hooked over the new content, `wp_unslash( sanitize_post_field( 'post_content', wp_slash( $new ), $id, 'db' ) )`, and refuses a page they would change: `content_save_pre` still runs with kses removed, and core strips a block's own CSS there (`block-styles-guide.md` § Variation rules). The slashes are part of it: the save filters expect slashed content, as `wp_insert_post()` gives it to them, and a filter that unslashes changes an unslashed string;
  - passes `'edit_date' => true`: without it `wp_update_post()` gives a draft that was never published a new `post_date`;
  - keeps what an undo needs on the post: the old content in a meta row whenever it is not exactly empty, and a marker holding the post's own id, the source hash and the result hash. The marker is written as pending before the content and settled after the read-back, so that a stop between the two leaves no written post the script does not know. A marker without the id passes on a duplicated post, which copies meta;
  - reads the stored content back after the write and compares it with that filtered value, not with the string it sent. On a mismatch it restores that post and stops;
  - undoes per post, with no check of the whole set, and refuses by name a post edited since;
  - takes the site's home address as its first argument and refuses when `home_url()` differs;
  - has a dry-run mode, run on the dev site first. It never runs on production.

  A dry run on a dev site matched every expected replacement before the change was applied. The gates, the marker and the undo are from one script run through its whole life on a local site. The draft's date and the save filters were read in WordPress 7.1.4 (`post.php`, `block-supports/custom-css.php`), and the filters were run that way, slashed, on a local site with no user: plain block markup came back byte for byte, and a block with CSS of its own came back without it. Run over the unslashed string, the plain markup came back with its quotes escaped.
- **What `wp_update_post()` does besides writing the content.** `post_modified` moves on the write and again on the undo, and an undo does not put it back. Each write fires `post_updated` and `save_post` for every plugin: list the callbacks hooked for the post type first (an automation queue, a cache purge, a sync), remove the outbound ones for the run, and say in the pull request that the modified time moves.
- **Prove the script with a snapshot, taken before, after the write and after the undo:** per post, a hash of the content, the title and status, `post_date`, `post_modified`, the number of revisions, each meta row and the term relationships. After a write only the content, the modified time, the revisions and the script's own meta differ. A snapshot without `post_date` did not show a draft whose date was reset.
- **Back up before the first write.** On a Studio site, `sqlite3 <site-path>/wp-content/database/.ht.sqlite ".backup <file>"`: the database is in WAL mode, so a copy of the file is not a backup. Read on Studio 2.1.1.
- **Run the whole life of it on the local site first:** dry run, apply, a second apply that writes nothing, a post edited in between, a revision restored, a duplicated post, a forced stop, and an undo of everything.
- **On an environment other people use,** read the set, its hashes and each post's edit lock again immediately before every step that writes. A post someone duplicated since is in the set and is the user's decision: on a shared test site a colleague's duplicated draft made the next dry run refuse, and without the gate it would have been rewritten. Delete the run's own test posts before the next gate.
- **A script that stores rendered markup stores its own process's scheme and host.** Under WP-CLI an address built on `content_url()`, `get_theme_file_uri()` included, is `http://` on an https site, unless the command is given an https `--url` (`mapping-guide.md` § Where content lives). The local site is http, so the dry run on the hosted dev site is the first place a wrong scheme or host can show: scan its output for `http://` and for the site's host before anything is applied. Compare image and link addresses before and after exactly as printed, never after rewriting own-origin addresses to one form, and with every image of the body, not only those the change places. The audit lists an absolute address into `wp-content/themes/`, and an `http://` address under `wp-content/` on a host that is not a local one, in theme files and in `--content-dir` (`url_review`).
- **Whether an image CDN is on is part of an environment's state.** A local site and a fresh clone run Jetpack offline; once a site is connected, rendered content and the attachment image functions return `i<n>.wp.com` addresses, under WP-CLI too. A script that builds content from rendered output turns the CDN off for its process, proves with a probe that no render path still returns such an address, and refuses to store one. A parity baseline is taken again after the state changes: a zero tolerance holds only while the state is the same (§ Visual parity guard). Seen on one hosted site, once.
- **`wp eval-file` takes what follows the file as positional `$args`,** and rejects a flag it does not know, so a mode is a word, not `--apply`. It evals the file, so `declare( strict_types=1 )` is a fatal error there on PHP 8.3 and 8.4, which Studio's WP-CLI runs; PHP 8.5 accepts it. Tried with WP-CLI 2.12.0.
- **Renaming a block namespace** (for example when porting): update stored content directly, then validate the pages.
  - Replace `<!-- wp:old/` and `<!-- /wp:old/` with a `$wpdb` string replace across *all* posts, revisions included, in a sentinel-echoing `studio wp eval-file` script. Do not go through `wp_update_post()` for this, and do not rely on what WP-CLI's save filters do either way: on one Studio site, with no user, the kses content filter was not hooked and other save filters were, core's own that strips a block's CSS among them. `--user` and a host's WP-CLI were not tried.
  - Apply the same rewrite to `.h2bt/pages/*.html`.
  - Rename only block-comment names and prefixed identifiers. Image filenames and outbound URLs that happen to contain the old slug stay as they are.
- **Plugins the content depends on** (for example Jetpack Forms or a motion plugin) are installed on the host and listed in the README under "Site dependencies". Track one under `plugins/` only if the user decides to, following the template README's tracked-plugin recipe.
- **Monorepo block plugins** are site dependencies too: installed on the host from their release ZIPs, updated from opsoasis, and never tracked here. List each with its version. A block still awaiting its monorepo release blocks deploying the pages that use it; say so in the README and the report.

## Delivery

- **Commits:** conventional commits (`feat:`, `fix:`, `docs:`, `chore:`), in the logical units a reviewer reads.
- **Pushing needs the user's permission.** Open a **draft** PR against `trunk` using the repository's PR template, with screenshots or the parity result for visual changes. Never push `trunk` or `develop`.
- **README:** keep it true. Add what the theme now is, the site's dependencies (monorepo block plugins included), the Studio workflow and any allowlisted exclusions. Rewrite the prose that a removed example leaves false, as its recipe says; prose about an example the build kept stays. Run `npm run lint:readme-md` after editing it.

## Porting an existing standalone build into the template

1. **Baseline** with `parity-check.sh --mode baseline`, while the standalone theme is still active.
2. **Set up the repository.** Convert the site with `clone-into-existing-site`, restore local-only mu-plugins, create a branch, set the PHP floor, and install dependencies.
3. **Replace the template's example theme content,** and strip the example features the build does not use (§ Template example features).
4. **Move the build over.** Move each piece per § Where each piece goes, and rename identifiers per § Permanent identifiers.
5. **Build, activate and rewrite.** Run `npm run build`, activate the template theme, rewrite the block namespace in stored content, and validate the affected pages and parts.
6. **Verify and deliver.** Run `parity-check.sh --mode compare`, then `standards-audit.sh` and `template-checks.sh`, commit, and open a draft PR.
