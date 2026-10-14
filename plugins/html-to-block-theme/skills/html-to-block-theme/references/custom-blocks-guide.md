# Custom blocks guide: core first, then the blocks monorepo

Custom behaviour is rung 3 of the escalation ladder: behaviour or markup that core blocks and their supports cannot produce. Keep new blocks to a minimum. Every block is maintenance someone carries forever, so work through these steps in order and stop at the first one that works:

1. **Core, with no new block.** Patterns, Block Bindings, the Interactivity API on existing blocks, block variations, and filters that extend core blocks.
2. **Reuse a block from the [A8C Special Projects blocks monorepo](https://github.com/a8cteam51/special-projects-blocks-monorepo).** Install its release, style it from the theme, and adapt its behaviour from the project.
3. **Build a new block in the monorepo.** It is project-agnostic, uses the `a8csp` namespace, and ships wireframe styling; the project styles it.

Never create a block inside a theme, in any mode. A block may stay in the project only as an **approved exclusion** (§ Approved exclusions), and only when the user says an engineering lead has approved it.

Record every behaviour in the blueprint: the step it resolved at, why each earlier step failed, and its source (a core route, `<plugin>@<version>` from the monorepo, a new monorepo block, or an approved exclusion). The report repeats this.

## Step 1: rule out core

A custom block is justified only when none of these produce the behaviour:

- **A core block already does it.** `core/navigation` has a mobile menu, `core/accordion` and `core/details` make accordions (an accordion's `autoclose`, or details siblings sharing a `name`, open one at a time), `core/tabs` makes tabs, `core/query` lists content, and `core/cover` handles media backgrounds. The accordion and tabs blocks are in WordPress 7.1: check an older core for them.
- **A pattern** of existing blocks, for a reusable arrangement.
- **Block Bindings**, for dynamic values in core blocks (below).
- **The Interactivity API on an existing block**, for state and interaction. Add the directives to a core block's output with a `render_block_<block>` filter and `WP_HTML_Tag_Processor`, and register the store as a script module.
- **A block variation, block style or filter** that extends a core block: `register_block_variation`, `render_block_<block>`, `register_block_type_args`, and editor filters such as `blocks.registerBlockType` and `editor.BlockEdit`.

### Dynamic content from meta: bindings before blocks

- **Block Bindings** connect a core block's attribute to post meta with no custom block at all. For *formatted* meta, such as a composed "year • publisher" line or a bespoke date form, register a custom source with `register_block_bindings_source()` and format the value in its callback.
- A paragraph bound to empty meta still renders an empty `<p>`. Pair each bound optional field with a scoped `:empty { display: none; }` rule in the relevant block CSS file.
- Sitewide date formatting belongs in a `render_block_core/post-date` filter, not in per-instance markup.

### The dynamic pieces of a post type's templates, without a custom block

A post type's templates usually need a handful of things that follow the entry or the archive in view. Each stays a core block, fed from one include:

- **Text and links that depend on the post or one of its terms:** one Block Bindings source with a `key` argument. A `format` argument in which `%s` stands for the value keeps a sentence such as "Back to %s" in the template markup, not in PHP.
- **The current tab:** the path-matching `render_block_core/navigation-link` filter (`mapping-guide.md` § core/navigation notes), because core marks a link current by post or term id, which differs per environment.
- **Wording around a date** (a tooltip, a link's accessible name): a `render_block_core/post-date` filter.
- **A list core cannot query:** a registered block style on a core block as the opt-in, and a render filter that prints the list for that style while keeping core's wrapper and its classes. Bending the block's own query through its argument filters is costlier and more brittle than replacing its inner markup.

Presentation that feeds templates lives with the theme. Routing, and anything stored content depends on, lives where it survives a theme swap: the features plugin in template mode.

### What a block can know

- **Block context cannot tell "inside a query loop" from "top level of an archive template".** `render_block()` gives top-level blocks, including those in template parts, the first post of the main query as `postId` and `postType`. `core/post-template` renders each post from a new block with those same two keys and nothing that identifies the loop. A bindings source or render filter that must follow the view outside a loop needs `in_the_loop()`, which covers inherited queries only, or an explicit argument. The symptom is a wrong rendered value, such as a link in an archive's header that points at the first entry's term.
- **Core block markup moves between versions.** On WordPress 7.1 `core/post-date` prints the link around the `time` element, not inside it. A render filter that walks tags must not assume their order.
- **A template's whole output is texturised.** Write a hyphen or quote that a filter prints as a character reference (`mapping-guide.md` § Query loops, archives and pagination).
- **A post type whose permalink embeds a term answers under any term.** Core finds a single post by its slug alone, so with a structure such as `/<type>/<term>/<slug>/` the same post answers with status 200 under every term. If the original site redirects such an address, that is routing the build has to add. One wrong-term request against the original and one against the build shows it. Write the decision as a function that returns the address or null, so that it can be tested without the `exit` that follows a redirect.

### Test groundwork through a rendered template

The orchestrator often writes these pieces before the builder that uses them starts. Two rules follow from a defect that a block-by-block smoke test missed:

- **Test groundwork through a rendered template**, on an archive and on a single view, before a builder depends on it. Rendering blocks one at a time hides whatever depends on the surrounding template: context, loops, the main query.
- **Tell the builder the groundwork may be wrong**, and how to report a change to it.

Testing traps:

- A binding source's `uses_context` reaches a block only while its bindings are processed. Test a binding by rendering a block that carries it, with the context passed in.
- A state the sample data lacks (an entry without its term, an empty field) can be rendered without touching the database: a loose file in `mu-plugins` that applies a filter only when a query parameter is present, one request, then the file is removed. Record the file under `temporary` in `run.json` when it is made, so that a run that is interrupted still removes it.
- WordPress schedules a post dated in the future instead of publishing it. A fixture meant to be "the newest" needs another way to stand out: compare only the ids the test created.

## Step 2: check the monorepo

List the catalog before planning any block:

```bash
bash "<plugin-root>/scripts/monorepo-blocks.sh" catalog
```

It refreshes a cached clone and prints one tab-separated line per plugin:

- the plugin directory;
- the block names it registers, or `-` for a plugin that extends core blocks without registering its own, such as a Query Loop variation or a cover-block style;
- its latest release, or `unreleased`. `unknown` in every row means the release lookup failed (no network, or GitHub's limit for callers who are not signed in), and the sentinel then says `releases=unavailable`: sign in with `gh` or try again, and do not read it as unreleased;
- whether it has a `screenshot.png`;
- its descriptions.

The last line is the `H2BT_MONOREPO_CATALOG` sentinel.

- **Judge fit by behaviour, not by name.** Namespaces vary across the catalog (`a8csp`, `wpcomsp`, `wpsp`). When a description is unclear, open the plugin's source, `readme.txt` or screenshot in the cached clone.
- **A close match beats a new block.** Project styling and hooks can bridge most gaps (§ Reusing a monorepo block). Build new only when the behaviour itself is missing.
- **Never modify a reused block in place.** A fix or improvement that would help every site is a separate monorepo pull request, raised with an engineering lead; the run adapts the block from the project in the meantime.

## Reusing a monorepo block

1. **Install it from its release**, the way production does:

   ```bash
   bash "<plugin-root>/scripts/monorepo-blocks.sh" install --site-path <site-path> <plugin-dir> [<plugin-dir>...]
   ```

   It installs and activates each plugin's latest release ZIP and prints `H2BT_MONOREPO_INSTALL plugin=<dir> version=<version>` once the site reports that version installed. It refuses a plugin that is also built in a monorepo clone on the same site, because the block would register twice. Validate markup that uses the block only after it is installed.
2. **Style it from the theme**, as for any block type: one stylesheet per block type, named from the block name, and enqueued with `wp_enqueue_block_style()` (`block-styles-guide.md`). For example, `a8csp/modal` becomes `assets/css/blocks/a8csp-modal.css`, or `assets/sass/blocks/a8csp-modal.scss`, built to `assets/css/blocks/a8csp-modal.css`, in template mode. Register style variations for the monorepo block with `register_block_style()` like any other.
3. **Adapt its behaviour from the project**, never in the block. Use the block's own PHP filters, `render_block_<block>`, `register_block_type_args`, block variations, and editor filters. The code lives in the theme's includes (standalone), or in the features plugin's `includes/<concern>.php` (template mode), because it serves content that must survive a theme swap.
4. **Record it as a site dependency.** The plugin is installed on the host and updates itself from opsoasis. It is never tracked in the project repository. List the plugin and version in the report and, in template mode, in the README's "Site dependencies".

## Building a new block in the monorepo

Only after steps 1 and 2 have failed. The run builds the block locally; pushing it, opening its pull request and filing its proposal all wait for the user's approval, and an engineering lead signs off there.

1. **Clone the monorepo into the site** and branch:

   ```bash
   bash "<plugin-root>/scripts/monorepo-blocks.sh" clone --site-path <site-path>
   git -C <site-path>/wp-content/plugins/special-projects-blocks-monorepo switch -c add/<slug> origin/trunk
   ```

   The clone lives in `wp-content/plugins/special-projects-blocks-monorepo`, and its autoloader loads every plugin there that has a `build/` directory. Never build a plugin in the clone that is also installed from a release ZIP.
2. **Scaffold** from the clone's root:

   ```bash
   npm run new-block -- <slug> "<Title>" [--dynamic] --description "<what the block does, verbosely>"
   ```

   This runs `@wordpress/create-block` with the `a8csp` namespace and applies the monorepo's conventions:
   - the `<slug>/<slug>.php` entry file and plugin header, with its `Update URI`;
   - the self-update class and its wiring;
   - `readme.txt` and `CHANGELOG.md`.

   It installs dependencies and builds, so the autoloader picks the block up straight away. Use `--dynamic` for a server-rendered block (`render.php`).
3. **Write the block generically.** The monorepo's rules:
   - **Project-agnostic.** No project names, data, copy or styling. It's `a8csp/<slug>`, whatever project surfaced it.
   - **Wireframe styling.** Keep only the structural CSS the block needs to work, and replace create-block's boilerplate, which sets a background colour, white text and padding. Block-support style controls, such as colour, are fine.
   - **One block per plugin.** The exception is a tightly coupled family, such as a tabs container with its child tab.
   - **Extensible output.** A dynamic block builds its wrapper with `get_block_wrapper_attributes()`, escapes everything, and adds `apply_filters()` hooks generously for the next project to adapt it.
   - **Accessible state.** Interactive blocks expose state through ARIA (`aria-expanded`, `aria-pressed`, `hidden`). Prefer the Interactivity API for state-driven UI (below).
   - **Usable in the editor.** The block's `edit` shows what the block shows: its own wrapper (`useBlockProps`), every part of it present and editable in place (`InnerBlocks`, `RichText`), and a complete, static state where the front end depends on the view script, which does not run in the canvas: every slide, every panel, a modal's content. It need not look like the front end. It must not look broken, and it must not hide what an editor has to edit.
   - **Verbose descriptions.** Tooling reuses the plugin and `block.json` descriptions, so write them fully. Fill in the `readme.txt` description and FAQ, and add the plugin's row to the README inventory.
4. **Build and lint the way the monorepo's CI does:**
   - In the block's directory: `npm run build`, then `npm run lint:js` and `npm run lint:css`.
   - PHPCS from the clone's root: `composer run-script packages-install` once, then `vendor/bin/phpcs --standard=.phpcs.xml --ignore='*/build/*' <slug>`. CI checks out no `build/`, so skip it locally too.
   - create-block's boilerplate doesn't pass PHPCS as generated. `vendor/bin/phpcbf` fixes some of it. Fix the rest by hand: `render.php` echoes `get_block_wrapper_attributes()` unescaped (wrap it in `wp_kses_data()`), and the entry file's function lacks an `@return` tag.
5. **Style it for the project from the theme**, exactly as for a reused block (§ Reusing a monorepo block, step 2).
6. **Check it in the newest Twenty-* theme** on a throwaway Studio site. A fresh Studio site runs core's default theme, which is the newest Twenty-* theme; confirm with `studio wp theme list --status=active`. Record the site's path under `temporary` in `run.json` as soon as it is created: it is deleted by path, and that path must not come from memory.

   ```bash
   studio site create --path <tmp-site> --name "<slug> check" --skip-browser --skip-log-details
   rsync -a --exclude node_modules <clone>/<slug>/ <tmp-site>/wp-content/plugins/<slug>/
   studio wp plugin activate <slug> --path=<tmp-site>
   studio wp post create --post_type=page --post_status=publish --post_title="<Title> check" \
     --post_content='<!-- wp:a8csp/<slug> /-->' --porcelain --path=<tmp-site>
   ```

   Open the page in Chrome at desktop and mobile widths. The block must render unbroken: visible, not overflowing, with working interactions and no console errors. Open the same page in the block editor as well: the block draws with no error notice, shows every part of itself and can be selected. Then delete the site with `studio site delete --path <tmp-site>`.
7. **Add the screenshot.** `<clone>/<slug>/screenshot.png` must be a 1200×800 PNG of the block **as it looks in the project**. Capture it from the project site in Chrome at full scale, then size it (on macOS):

   ```bash
   sips -s format png --resampleWidth 1200 <capture> --out <resized.png>
   sips --cropToHeightWidth 800 1200 <resized.png> --out <clone>/<slug>/screenshot.png
   ```

8. **Commit and draft the proposal.**
   - Commit the plugin on `add/<slug>` in the clone, with a conventional commit message.
   - Write the New block proposal to `<site-path>/.h2bt/proposals/<slug>.md`, following the monorepo's issue template:
     - the four alternatives ruled out (pattern, Block Bindings, Interactivity API on an existing block, extending or restyling a core block), each with its reason;
     - the existing-block check: which catalog plugins were considered, and why they don't fit;
     - the proposed name `a8csp/<slug>`;
     - a verbose description;
     - acceptance criteria;
     - the design reference and screenshot;
     - the project context.
9. **Deploy only after release.** The project can't ship pages that use the block until its pull request merges and the release exists, so the report and README list it as a pending site dependency. After the release, switch the Studio site to the release ZIP: remove the block's `build/` from the clone, then run `monorepo-blocks.sh install`.

### Interactivity (the front-end behaviour)

Prefer the **Interactivity API** for state-driven UI. Add the directives in `render.php`:

```php
<div
	<?php echo wp_kses_data( get_block_wrapper_attributes() ); ?>
	data-wp-interactive="a8csp/<slug>"
	data-wp-context='{ "open": false }'
>
	<button type="button" data-wp-on--click="actions.toggle" data-wp-bind--aria-expanded="context.open"><?php esc_html_e( 'Toggle', '<slug>' ); ?></button>
	<div data-wp-bind--hidden="!context.open"><?php echo $content; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped ?></div>
</div>
```

The store is an ES module, loaded with `viewScriptModule` in `block.json`. `wp-scripts` builds script modules only with `--experimental-modules` in the plugin's `build` and `start` scripts.

```js
import { store, getContext } from '@wordpress/interactivity';

store( 'a8csp/<slug>', {
	actions: {
		toggle() {
			const context = getContext();
			context.open = ! context.open;
		},
	},
} );
```

For trivial behaviour with no shared state, a plain `view.js` (`viewScript`) is fine. Never enqueue the design's original JavaScript wholesale: reproduce the behaviour.

## Approved exclusions (template mode only)

The monorepo allows a block to stay in a project repository when it is so bespoke that no other project could reuse it, but only with an engineering lead's approval. Take this path **only when the user states that approval**. Otherwise the block goes to the monorepo. Standalone runs have no exclusion path.

```bash
bash "<plugin-root>/scripts/scaffold-custom-block.sh" --exclusion-approved \
  --features-dir "<features-dir>" --namespace "<theme_slug>" --slug "<slug>" --title "<Title>"
```

The block goes in the **features mu-plugin**, not the theme, because page content stores it and it must survive a theme swap. In a repository as generated that plugin is disabled, and enabling it also enables the template's example features: remove those by their recipes first, then delete `.disabled` (`project-template-guide.md` § Template example features). The scaffold:
- writes `blocks/src/<slug>/`, with ES modules and JSX in `index.js` and a strict-types `render.php` whose variables carry the repository's prefix;
- adds `includes/blocks.php`, which registers everything in the wp-scripts `blocks-manifest.php` via `wp_register_block_types_from_metadata_collection()`;
- adds the `build:features:blocks`/`start:features:blocks` scripts and the lint paths to `package.json`;
- lists the block's source and build `block.json` in `.github/blocks-allowlist`, under a comment marking it an approved exclusion. CI's blocks policy fails any unlisted `block.json`.

The scaffold ends `H2BT_BLOCK_OK`. `H2BT_BLOCK_PARTIAL` means the block's files are written but it could not add the scripts to `package.json`: add the `ADD MANUALLY` lines it printed before building. A scaffold that fails part-way removes the block directory it made, so it can be run again.

Build with `npm run build:features:blocks`. Styles and view scripts follow the wp-scripts conventions in `project-template-guide.md` § Build pipeline.

## Discipline

- Never create a block in a theme.
- One block per genuine behaviour; never a block for styling.
- Never edit a reused monorepo block in place; adapt it from the project.
- A new block is project-agnostic and wireframe-styled; the project styles it from the theme.
- Every block's source and justification is in the blueprint and the report.
