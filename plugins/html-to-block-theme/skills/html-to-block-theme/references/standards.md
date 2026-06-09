# Standards

Non-negotiable rules for the delivered theme. The standards audit (`scripts/standards-audit.sh`) enforces the comment and custom-CSS rules; the rest are review criteria.

## Comments

- **Block markup** (templates, parts, patterns, page content) contains **only `<!-- wp ... -->` block delimiters.** No other HTML comments — no `<!-- hero section -->`, no `<!-- TODO -->` left in shipped markup. The Gutenberg delimiter is the single permitted comment form.
- **PHP files** (`functions.php`, `render.php`, `patterns/*.php`) follow WordPress coding standards: a file docblock and function docblocks where they add meaning are fine; avoid line-by-line inline narration. No commented-out code.
- **CSS / JS**: no explanatory inline comments beyond a short file header where one genuinely helps. Keep it clean, not annotated.

If a section needs a note for the user, it goes in the **report**, not as a comment in the theme.

## Custom CSS is a last resort

- `theme.json` is the source of truth for design tokens and styling. Express styling through block supports first, block style variations second.
- Hand-written CSS is rung 4 — only when rungs 1–3 cannot achieve the detail. Every rule must be: tightly scoped (to a block wrapper or `is-style-<slug>` class), minimal, and listed in the report with the reason a lower rung could not do it.
- Never reproduce a value in CSS that already exists as a token — reference `var(--wp--preset--…)`.
- Do not enqueue the design's original stylesheets or JS. They are intent to translate, not assets to ship.

## Block markup conventions

- Use documented attributes only (`className`, `anchor`, `style`, `backgroundColor`, `textColor`, `fontSize`, `fontFamily`, `align`, `layout`, plus per-block attributes). Never invent attribute names.
- Colour classes are `has-{slug}-background-color` / `has-{slug}-color`.
- Every block validates through `validate_html_blocks` — markup whose `save()` output differs from input is wrong; fix it or downgrade to `core/html`, never ship invalid blocks.

## Theme structure

A valid block theme has:

```
style.css            # theme header comment block (required)
theme.json           # source of truth
functions.php        # enqueue, block + block-style registration, font/asset wiring
templates/           # index.html (required) + others (single, archive, 404, page, front-page…)
parts/               # header.html, footer.html, shared chrome
patterns/            # *.php registered patterns
styles/              # block style variations + global style variations (*.json)
assets/              # fonts/, images/
blocks/              # build-less custom blocks (one dir each)
```

`style.css` must carry the theme header (Theme Name, Version, Text Domain, etc.). `templates/index.html` must exist for the theme to be valid.

## WordPress / PHP

- Escape output (`esc_html`, `esc_attr`, `esc_url`, `wp_kses_post`); use `get_block_wrapper_attributes()` in render callbacks.
- One text domain, matching the theme slug, used consistently in i18n calls.
- Bundle fonts locally (declared in `theme.json` `fontFace`); no CDN `@import`.

## Accessibility

- Preserve semantic landmarks: header/nav/main/footer map to the right blocks and template parts.
- Maintain heading order from the design (don't skip levels for styling — style with `theme.json`/supports instead).
- Images carry `alt`; decorative images use empty `alt`.
- Interactive custom blocks expose state via ARIA (`aria-expanded`, `hidden`) as shown in `custom-blocks-guide.md`.
