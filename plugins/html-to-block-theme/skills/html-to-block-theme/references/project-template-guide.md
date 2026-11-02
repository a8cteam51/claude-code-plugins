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
  --paths "/,/about/,/contact/" --mode baseline [--local-storage <popup-key>=1]
# … change code, rebuild …
bash "<plugin-root>/scripts/parity-check.sh" --repo <repo> --base-url <site-url> \
  --paths "/,/about/,/contact/" --mode compare [--local-storage <popup-key>=1]
```

**When to take a baseline:** before porting a theme, before running any formatter or auto-fixer, and before refactoring Sass.
- **How it captures:** full-page shots at 1440 and 390, with reduced motion, CSS animations disabled, lazy images scrolled into loading, and popups suppressed through `localStorage`.
- **Why a zero tolerance is safe:** two captures of an unchanged site are pixel-identical, so `compare` fails on any difference: no differing pixel is allowed, and no colour tolerance either.
- **`compare` never writes a baseline.** A path or width with no baseline ends `H2BT_PARITY_FAIL … reason=no-baseline` and names what is missing. Take the baseline on the unchanged site first. Two paths that are one page (`/about` and `/about/`) are refused in one run.
- **Screenshot names carry a short hash of the path,** so that `/` and `/home/` are different files. A baseline taken with an earlier version of the script has other names and has to be taken again.
- **What it runs on:** the repository's own `@playwright/test` with local Chrome, writing to the git-ignored `tests/.cache/h2bt-parity/`.
- **Where to run it:** against the Studio site, because wp-env has no content.

## Content and dependencies

- **Content isn't in the repository.** Page content, media and menus live in the Studio database. Deploying ships code only, and moving content to the host is the user's step. Never write to production; the repository's `AGENTS.md` treats production as read-only.
  - **Stored content names its environment.** Image blocks hold attachment ids and the local site's URLs. A full push to a fresh environment keeps them; merging pages into an existing database needs an id and URL remap. Say in the report which the project needs, and keep each page's source (`.h2bt/pages/*.html`) and the media manifest as the record a migration starts from.
- **A later change to a page's content** is a WP-CLI `eval-file` script that changes only what it must. `write-page.sh` writes the whole page, so it overwrites whatever an editor changed since. The script:
  - replaces exact strings, each with the number of matches it expects;
  - refuses a page whose counts differ, and changes nothing on it;
  - does nothing on a second run;
  - saves a revision and calls `kses_remove_filters()` before it writes;
  - has a dry-run mode, run on the dev site first. It never runs on production.

  A dry run on a dev site matched every expected replacement before the change was applied.
- **Renaming a block namespace** (for example when porting): update stored content directly, then validate the pages.
  - Replace `<!-- wp:old/` and `<!-- /wp:old/` with a `$wpdb` string replace across *all* posts, revisions included, in a sentinel-echoing `studio wp eval-file` script. Going through `wp_update_post` runs kses under WP-CLI.
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
