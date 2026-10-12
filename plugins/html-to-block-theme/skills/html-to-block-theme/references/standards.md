# Standards

Non-negotiable rules for the delivered theme. The standards audit (`scripts/standards-audit.sh`) enforces the comment and custom-CSS rules, the reserved preset slugs, the dropped-colour rule, whole-pixel values, the layout of post content, group names, settings written as classes and the areas of template parts; the rest are review criteria. Pass it `--content-dir <site-path>/.h2bt/pages` so the page content, which is not in the theme, is checked too. It also fails on a `theme.json` that does not parse (`theme_json`), which WordPress ignores, and on a directory that is not a theme. Its last line is `H2BT_AUDIT_OK` or `H2BT_AUDIT_FAIL`.

## Comments

- **Block markup** (templates, parts, patterns, page content) contains **only `<!-- wp ... -->` block delimiters.** No other HTML comments — no `<!-- hero section -->`, no `<!-- TODO -->` left in shipped markup. The Gutenberg delimiter is the single permitted comment form.
- **PHP files** (`functions.php`, `render.php`, `patterns/*.php`) follow WordPress coding standards: a file docblock and function docblocks where they add meaning are fine; avoid line-by-line inline narration. No commented-out code.
- **CSS / JS**: no explanatory inline comments beyond a short file header where one genuinely helps. Keep it clean, not annotated. A scaffold's explanatory comments go, also above a rule that is kept. In a standalone theme the audit fails on a comment in `style.css` or a block stylesheet after the file's header (`css_comments`); in a project repository stylelint is the gate, and its `stylelint-disable` comments stay.

If a section needs a note for the user, it goes in the **report**, not as a comment in the theme.

## Custom CSS is a last resort

- `theme.json` is the source of truth for design tokens and styling. Express styling through block supports first, block style variations second.
- **One CSS file per block type**, under `assets/css/blocks/<block-name>.css`, enqueued with `wp_enqueue_block_style()` (mechanics: `block-styles-guide.md`). Each of these is a violation: a monolithic stylesheet, `wp_enqueue_style()` for block CSS, a block CSS file not enqueued via `wp_enqueue_block_style()`, or block-style CSS declared in `/styles/*.json`.
- Hand-written CSS is rung 4 — only when rungs 1–3 cannot achieve the detail. Every rule must be: tightly scoped (to a block wrapper or `is-style-<slug>` class), minimal, and listed in the report with the reason a lower rung could not do it.
- Never reproduce a value in CSS that already exists as a token — reference `var(--wp--preset--…)`.
- Do not enqueue the design's original stylesheets or JS. They are intent to translate, not assets to ship.

## Block markup conventions

- Use documented attributes only (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `fontFamily`, `align`, `layout`, plus per-block attributes). Never invent attribute names.
- Colour classes are `has-{slug}-background-color` / `has-{slug}-color`.
- Every block validates through the Studio validator (`validate_blocks`) — markup whose `save()` output differs from input is wrong; fix it, never ship invalid blocks.
- **`core/html` is restricted** (enforced by the validator's static policy check): allowed only within the core/html policy in `mapping-guide.md`; everything else must be editable blocks.
- Custom CSS hooks are always registered block styles: every class a stylesheet targets is either a block's own wrapper/structural class or an `is-style-*` class backed by `register_block_style()`. Structural rung-4 CSS targets block selectors directly (wrapper classes, contextual combinators). An unregistered bespoke className used as a CSS hook is a violation (`block-styles-guide.md`, decision rule).
- **A setting is an attribute, never a class.** What the editor has a control for (font family, font size, colour, alignment) is written as the block's attribute, so that the control shows it. The same value as a class in `className`, or as a preset class in the markup with no attribute behind it, validates and shows only under Additional CSS class(es). The audit fails on both, and on a `className` the theme's stylesheets select that is not a registered style (`class_hooks`).
- **No colour function in an element, state or viewport style** (`style.elements.*`, `style[":hover"]`, `style["@mobile"]`): WordPress drops the declaration. Write eight-digit hex (`mapping-guide.md` § CSS → block supports). The audit fails on it (`dropped_colors`).
- **No preset slug that is one of core's flag classes:** a palette entry named `text`, `link` or `border`, or a font size named `custom` (`theme-json-guide.md`). The audit fails on it (`reserved_slugs`).
- **A value written in pixels is a whole number of pixels,** in `theme.json`, in block attributes and in stylesheets. A breakpoint is the last whole pixel of its range (`767px`, never `767.98px`), the other side of a `min-width: N` rule is the range query `(width < N)`, and a finer value uses a relative unit, such as a letter spacing in `em` (`mapping-guide.md` § Pixel values are whole pixels). The audit fails on a fraction of a pixel (`subpixel_values`).
- **Every template gives `core/post-content` a constrained layout,** landing-page templates included. A block is then as wide as the content column unless it is aligned wide or full, in the editor as on the page, and a page's full-bleed sections are `alignfull` blocks in its content (`mapping-guide.md` § Post content sits at content width). The audit fails on post content without one (`post_content_layout`).
- **Every `core/group` has a name** (`"metadata":{"name":"Hero"}`), in templates, parts and page content, rows, stacks and grids included. A person reads the markup tree and the editor's List View by those names (`mapping-guide.md` § Name every group). The audit fails on a group without one (`unnamed_groups`).

## Content and images

- **Nothing a visitor reads is held in a PHP pattern,** unless the blueprint records that the project needs translatable template text or the user asked for starter patterns (`mapping-guide.md` § Where content lives). Parts and templates are plain block markup; page content is in the page.
- **Design images are media-library items;** only an image a template, part or stylesheet itself needs is a theme file (`mapping-guide.md` § Asset routing).
- **Every theme-file image in a template or part reserves its space:** both dimensions or an `aspectRatio` on the block. The audit lists the ones that do not (`image_review`); each is fixed or explained in the report (an image out of the flow, sized by its block style).
- **The largest image of each view's first screen is not lazy-loaded.** WordPress lazy-loads every content image after the third, small icons included. Read the `loading` attribute of that image on every view and report it; whether the theme raises `wp_omit_loading_attr_threshold` is a per-project decision.

## Theme structure

A valid block theme has:

```
style.css            # theme header comment block (required)
theme.json           # source of truth; declares every part in templateParts, with its area
functions.php        # register_block_style() + wp_enqueue_block_style() per block, font/asset wiring
templates/           # index.html (required) + others (single, archive, 404, page, custom page templates…) — never front-page.html
parts/               # header.html, footer.html, shared chrome, as plain block markup
patterns/            # only when the blueprint calls for them (translatable chrome, starter patterns); never the home of page content
styles/              # global (full-theme) style variations only (*.json); block styles are PHP-registered
assets/css/blocks/   # one CSS file per block type (core-button.css, core-group.css…), enqueued via wp_enqueue_block_style()
assets/              # fonts/, and only the images a template, part or stylesheet itself references
```

Page content and design images are not in this tree: they live in the site's database and media library, and reach another environment by a content migration.

A theme never contains a block (`block.json`). Blocks come from the A8C Special Projects blocks monorepo, installed as plugins, per `custom-blocks-guide.md`; the standards audit fails a theme that ships one (`theme_blocks`).

`style.css` must carry the theme header (Theme Name, Version, Text Domain, etc.). `templates/index.html` must exist for the theme to be valid.

**Template mode** (an a8csp-project-template repository) uses that template's structure instead. `project-template-guide.md` § Where each piece goes has the full mapping; in short:
- Sass sources build `style.css`.
- Block CSS goes in `assets/css/src/blocks/*.scss`, built to `assets/css/build/blocks/`.
- PHP goes in `includes/*.php`, loaded by the template's `functions.php`.
- Theme JS is ES modules under `assets/js/src/`, built to `assets/js/build/`.
- Blocks come from the blocks monorepo. Only an approved exclusion goes in the features mu-plugin.

The template's own gates (PHPCS, PHPStan, stylelint, ESLint, build integrity, blocks allowlist, tests) apply on top of these standards. Run them with `scripts/template-checks.sh`. The conversion writes no tests: under the repository's `tests/` directory it only deletes what a template example's removal recipe names (`project-template-guide.md` § Checks).

**`style.css` is not auto-enqueued on block themes** (observed on WP 7.0.1/Studio): `functions.php` must enqueue it explicitly — `wp_enqueue_style( '<theme-slug>-style', get_stylesheet_uri(), … )` plus `add_editor_style( 'style.css' )` so the editor matches. Root `style.css` is exempt from the one-file-per-block-type rule and is where responsive token overrides and the reset rules the design relies on live (`theme-json-guide.md`); a separate `assets/css/tokens.css` is flagged STRAY by the audit.

The theme must **not** ship `templates/front-page.html` — the standards audit fails a theme containing it. The homepage is a WordPress page set as the static front page; see the homepage rule in `mapping-guide.md`.

## WordPress / PHP

- Escape output (`esc_html`, `esc_attr`, `esc_url`, `wp_kses_post`); use `get_block_wrapper_attributes()` in render callbacks.
- One text domain, matching the theme slug, used consistently in i18n calls. (Template mode: the theme uses the theme slug and the features mu-plugin its own text domain; each component sticks to its own.) Plain `.html` parts and templates carry no translation functions; strings in PHP, such as block style labels, still do.
- Bundle fonts locally (declared in `theme.json` `fontFace`); no CDN `@import`.

## Accessibility

- Preserve semantic landmarks: header/nav/main/footer map to the right blocks and template parts. A part is a `<header>` or a `<footer>` only when `theme.json` declares its area (`theme-json-guide.md` § Template parts; the audit fails on an undeclared part, `template_parts`), and each template wraps its content in a group with `"tagName":"main"`.
- **No skip link in the theme.** Core prints one before every block template that has a `main` element. A design's own skip link is not rebuilt: the page would have two.
- Maintain heading order from the design (don't skip levels for styling — style with `theme.json`/supports instead).
- Images carry `alt`; decorative images use empty `alt` (the image block's `isDecorative` also prints `role="none"`).
- A control's accessible name survives the rebuild. Where the original names a link differently from its visible text, the blueprint says how that is kept (`mapping-guide.md` § Buttons).
- Interactive blocks expose state via ARIA (`aria-expanded`, `aria-pressed`, `hidden`) as shown in `custom-blocks-guide.md`.
