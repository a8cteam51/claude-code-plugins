# Project template guide (template mode)

Template mode is on when the Studio site's `wp-content` is a git clone of a repository generated from [`a8cteam51/a8csp-project-template`](https://github.com/a8cteam51/a8csp-project-template). The run then builds into that repository's theme and features mu-plugin instead of a standalone theme.

**What this guide overrides and what it keeps:**
- It overrides the file locations and wiring in `block-styles-guide.md`, `custom-blocks-guide.md`, and `standards.md` § Theme structure.
- Every other rule is unchanged: the escalation ladder, one stylesheet per block type, registered block styles as the only CSS hooks, the core/html policy, and the homepage rule.

## Detect and bind

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-template.sh" --site-path <site-path>
```

The last line is `H2BT_TEMPLATE mode=template …` or `H2BT_TEMPLATE mode=standalone reason=…`. In template mode, bind these from the sentinel for the rest of the run:
- `<repo>`, the site's `wp-content`;
- `<theme-dir>`, which is `themes/<theme_slug>`;
- `<features-dir>`, which is `mu-plugins/<features_slug>`;
- `<prefix>`, the text domains, and the PHP, WordPress and Node floors;
- `examples`: the template's example features still present.

**The user named a template repository, but `wp-content` isn't a clone yet.** Set it up with the `studio-repo-clone` plugin rather than cloning by hand:
- `clone-into-existing-site` for an existing site. It keeps the database, uploads, plugins and themes.
- `clone-new-site` for a new site.

`clone-into-existing-site` doesn't move loose `mu-plugins/*.php` files back from `wp-content-temp`. Copy local-only ones back yourself, such as a Jetpack offline-mode shim. The template's `.gitignore` already excludes `mu-plugins/*`.

## Preconditions (template mode)

1. **A feature branch.** `trunk` deploys to production and `develop` to staging, so never build on either. Use the repository's branch prefixes (`add/`, `feature/`, `fix/`, `update/`, `remove/`), for example `git switch -c add/block-theme`.
2. **The site runs the PHP floor.** Run `studio site set --path <site-path> --php <php_floor>`. Below the floor, the features plugin prints an admin notice and loads nothing, so its blocks and redirects silently disappear.
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
| Block namespace, pattern slugs, pattern category | `<theme_slug>/<name>`. |
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
| Root `style.css` rules | Sass partials under `assets/sass/`, built to `style.css` (plus `style-rtl.css` and `style-editor.css`). The theme header lives in `assets/sass/style.scss`. Put responsive token overrides (`:root:root`) in a partial that both `style.scss` and `style-editor.scss` load. |
| `assets/css/blocks/<block>.css` | `assets/css/src/blocks/<block>.scss`, built to `assets/css/build/blocks/<block>.css`. |
| `register_block_style()` and `wp_enqueue_block_style()` in `functions.php` | `includes/block-styles.php`. Enqueue the **build** path, name each file literally (the audit greps for `<block>.css`), and version it with the asset-metadata helper. |
| `render_block_*` filters | `includes/<concern>.php`. |
| `assets/js/*.js` | ES modules in `assets/js/src/`, imported by `src/index.js` and built into the one always-enqueued bundle. Each module returns early when its markup is absent. |
| Custom behaviour | The same as standalone (`custom-blocks-guide.md`): core features first, then blocks from the A8C Special Projects blocks monorepo, installed as plugins and never tracked here. Only an approved exclusion is scaffolded into the features plugin (`blocks/src/<slug>/`, `scaffold-custom-block.sh --exclusion-approved`), because page content stores it and a theme swap must not unregister it. Project-side filters that adapt a monorepo block go in `<features-dir>/includes/<concern>.php`. |
| Site-config mu-plugins (redirects and the like) | `<features-dir>/includes/<feature>.php`. |
| Local-only shims (for example `jetpack_offline_mode`) | Untracked `mu-plugins/<file>.php`. Never commit them. |
| `templates/`, `parts/`, `patterns/`, fonts | Same paths. Patterns keep `Slug: <theme_slug>/…` and `Categories: <theme_slug>`. |
| A dynamic year or other theme-owned text | A block-bindings source in `includes/theme-dynamic-content.php`, following the template's own. |

## Build pipeline

The features-plugin block wiring below applies only to approved exclusions. Monorepo blocks build in the monorepo.

- **`package.json` edits:**
  - Quote the PostCSS glob as `'…/assets/css/build/**/*.css'`. The template's unquoted `*.css` misses the `blocks/` subdirectory, and npm's `sh` doesn't expand `**` recursively.
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
- **Rebuild after every source edit, before reloading the browser.** Use `npm run build:theme:css` (block CSS), `build:theme:style` and `build:theme:style-editor` (root Sass), `build:theme:scripts`, or `build:features:blocks`. `npm run build` does all of them.
- **Commit the build output.** CI rebuilds and fails on any byte difference ("Build integrity"), because the committed tree is the deploy artifact.

## Template example features

Detection lists what generation left behind.
- **`book-cpt`, `book-cover-reminder`, `woocommerce-cart`:** remove each with the recipe at the top of its own file. The recipe names the scripts, built files, tests and prose to delete.
- **The template's example theme content** (`parts/header.html`, `parts/footer.html`, `templates/index.html`, `templates/singular.html`, `patterns/footer-default.php`, `patterns/index-query.php`): the build's files replace it.
- **`<features-dir>/.disabled`:** generation creates it. Delete it once the features plugin carries real features, or its blocks and redirects never load.
- **Replacing the template's `current-year` binding** means updating `SiteBootTest` too.

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
  - compare `preg_match()` to `1`, and handle `preg_split()` returning `false`.
- **stylelint (`@wordpress/stylelint-config/scss`):**
  - `npm run format:styles` fixes most issues.
  - A `line-height` in `rem` is disallowed. Where the design fixes the line box, keep it with `// stylelint-disable-next-line declaration-property-unit-allowed-list -- <reason>`. The description is mandatory.
  - `clip` is deprecated; use `clip-path: inset(50%)`.
- **ESLint and Prettier:** `npm run format:scripts` fixes formatting. Use `catch {}` rather than an unused `catch ( error )`.
- **Auto-fixers rewrite code.** Take a parity baseline before running them (see Visual parity guard below).

## Checks (Phase 4 in template mode)

- **Standards audit:** `standards-audit.sh --theme-dir <theme-dir>` detects the template layout by itself. It checks one Sass source per block type, each built and enqueued, and counts the SCSS sources as the CSS footprint.
- **CI gates:** `template-checks.sh --repo <repo> [--tests] [--e2e]` runs CI's gates in order: build integrity, blocks allowlist, `composer lint:php`, `npm run lint`, then the wp-env suites.
  - **It works from a mirror.** The Studio site's `wp-content` also holds Studio's SQLite integration and loader. The lint scripts scan all of `mu-plugins/`, and wp-env mounts it, so checking in place reports hundreds of errors CI never sees. The mirror holds only tracked and unignored files, synced in place so wp-env's bind mounts survive.
  - **It refuses a port another wp-env instance already publishes**, because Playwright would silently test that other site.
  - **It waits for `afterStart` to activate the theme** before the end-to-end run.
- **Tests.** Replace the example tests with tests of the build's own promises: render filters (including filters that adapt monorepo blocks), approved-exclusion block output, block style and stylesheet registrations, bindings and redirects. The wp-env sites hold no page content, so these tests cover code, not the design.

## Visual parity guard

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/parity-check.sh" --repo <repo> --base-url <site-url> \
  --paths "/,/about/,/contact/" --mode baseline [--local-storage <popup-key>=1]
# … change code, rebuild …
bash "${CLAUDE_PLUGIN_ROOT}/scripts/parity-check.sh" --repo <repo> --base-url <site-url> \
  --paths "/,/about/,/contact/" --mode compare [--local-storage <popup-key>=1]
```

**When to take a baseline:** before porting a theme, before running any formatter or auto-fixer, and before refactoring Sass.
- **How it captures:** full-page shots at 1440 and 390, with reduced motion, CSS animations disabled, lazy images scrolled into loading, and popups suppressed through `localStorage`.
- **Why a zero tolerance is safe:** two captures of an unchanged site are pixel-identical, so `compare` fails on any difference.
- **What it runs on:** the repository's own `@playwright/test` with local Chrome, writing to the git-ignored `tests/.cache/h2bt-parity/`.
- **Where to run it:** against the Studio site, because wp-env has no content.

## Content and dependencies

- **Content isn't in the repository.** Page content, media and menus live in the Studio database. Deploying ships code only, and moving content to the host is the user's step. Never write to production; the repository's `AGENTS.md` treats production as read-only.
- **Renaming a block namespace** (for example when porting): update stored content directly, then validate the pages.
  - Replace `<!-- wp:old/` and `<!-- /wp:old/` with a `$wpdb` string replace across *all* posts, revisions included, in a sentinel-echoing `studio wp eval-file` script. Going through `wp_update_post` runs kses under WP-CLI.
  - Apply the same rewrite to `.h2bt/pages/*.html`.
  - Rename only block-comment names and prefixed identifiers. Image filenames and outbound URLs that happen to contain the old slug stay as they are.
- **Plugins the content depends on** (for example Jetpack Forms or a motion plugin) are installed on the host and listed in the README under "Site dependencies". Track one under `plugins/` only if the user decides to, following the template README's tracked-plugin recipe.
- **Monorepo block plugins** are site dependencies too: installed on the host from their release ZIPs, updated from opsoasis, and never tracked here. List each with its version. A block still awaiting its monorepo release blocks deploying the pages that use it; say so in the README and the report.

## Delivery

- **Commits:** conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), in the logical units a reviewer reads.
- **Pushing needs the user's permission.** Open a **draft** PR against `trunk` using the repository's PR template, with screenshots or the parity result for visual changes. Never push `trunk` or `develop`.
- **README:** keep it true. Document the site's dependencies (monorepo block plugins included), the Studio workflow and any allowlisted exclusions. Rewrite the prose that removed example features leave false.

## Porting an existing standalone build into the template

1. **Baseline** with `parity-check.sh --mode baseline`, while the standalone theme is still active.
2. **Set up the repository.** Convert the site with `clone-into-existing-site`, restore local-only mu-plugins, create a branch, set the PHP floor, and install dependencies.
3. **Clear out the template's examples** (§ Template example features).
4. **Move the build over.** Move each piece per § Where each piece goes, and rename identifiers per § Permanent identifiers.
5. **Build, activate and rewrite.** Run `npm run build`, activate the template theme, rewrite the block namespace in stored content, and validate the affected pages and parts.
6. **Verify and deliver.** Run `parity-check.sh --mode compare`, then `standards-audit.sh` and `template-checks.sh`, commit, and open a draft PR.
