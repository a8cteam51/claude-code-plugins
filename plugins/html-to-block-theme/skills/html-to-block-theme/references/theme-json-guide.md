# theme.json guide: design tokens as the single source of truth

`theme.json` is where the design system lives. Extract tokens from the design set's CSS **once**, unify near-duplicates across all files, and define them here as presets. Blocks then reference presets (`var:preset|color|primary`, `fontSize` slugs, preset spacing) so nothing is hardcoded twice.

Use schema version 3 and pin `$schema` so editors validate it:

```json
{
  "$schema": "https://schemas.wp.org/trunk/theme.json",
  "version": 3,
  "settings": { },
  "styles": { }
}
```

## Extracting tokens

Read the linked CSS (and CSS custom properties / `:root` variables — designers usually centralise tokens there). Map them:

- **CSS custom properties** (`--color-primary`, `--space-4`, `--font-body`) are the cleanest source — they *are* the token set. Mirror them into `theme.json` presets with stable slugs.
- **Repeated literal values** across rules (the same hex, the same `1.5rem`) → collapse to one preset. If two files use `#1a1a1a` and `#1b1b1b`, decide whether they are the same token (unify) or genuinely distinct.
- Round only where it does not shift the design perceptibly; otherwise preserve exact values.

## settings

```json
"settings": {
  "appearanceTools": true,
  "layout": { "contentSize": "768px", "wideSize": "1200px" },
  "color": {
    "palette": [
      { "slug": "primary",    "color": "#2563eb", "name": "Primary" },
      { "slug": "base",        "color": "#ffffff", "name": "Base" },
      { "slug": "contrast",    "color": "#111827", "name": "Contrast" }
    ],
    "custom": true,
    "defaultPalette": false
  },
  "typography": {
    "fluid": false,
    "fontFamilies": [
      {
        "slug": "body",
        "name": "Body",
        "fontFamily": "\"Inter\", sans-serif",
        "fontFace": [
          { "fontFamily": "Inter", "fontWeight": "400 700", "fontStyle": "normal", "src": ["file:./assets/fonts/Inter-Variable.woff2"] }
        ]
      }
    ],
    "fontSizes": [
      { "slug": "small",  "size": "0.875rem", "name": "Small" },
      { "slug": "medium", "size": "1rem",     "name": "Medium" },
      { "slug": "large",  "size": "1.5rem",   "name": "Large" },
      { "slug": "x-large","size": "2.5rem",   "name": "Extra large" }
    ]
  },
  "spacing": {
    "units": ["px", "rem", "%", "vw"],
    "spacingSizes": [
      { "slug": "20", "size": "0.5rem", "name": "Small" },
      { "slug": "40", "size": "1rem",   "name": "Medium" },
      { "slug": "60", "size": "2rem",   "name": "Large" },
      { "slug": "80", "size": "4rem",   "name": "Extra large" }
    ]
  },
  "viewport": { "mobile": "600px", "tablet": "960px" }
}
```

- **`appearanceTools: true`** turns on border/spacing/typography UI in one switch — prefer it over enabling each support individually.
- **Fluid typography is a per-design decision, not a default.** With `settings.typography.fluid` on, a fixed custom size renders as a `clamp()`. Decide from the design's CSS: `clamp()` or viewport units in its type scale mean fluid; fixed sizes inside media queries mean not, with the steps written as token overrides (below). A scaffold's value is not a given. With fluid off, a `clamp()` expression is still accepted as one block's own font size (`mapping-guide.md`).
- **`settings.viewport` sets the two breakpoints of per-viewport block attributes** (WordPress 7.1 and later; `mapping-guide.md` § Per-viewport values). `mobile` and `tablet` take px, em or rem and default to 480px and 782px. Set them to the design's two main breakpoints. Each bound is inclusive (`width <= value`): a design rule written `max-width: N` wants `N`, and one written `min-width: N` wants the last whole pixel below it (`N - 1`).
- **A value written in pixels is a whole number of pixels.** Never `767.98px` for a breakpoint, never a fraction of a pixel for a letter spacing: a finer value uses a relative unit, such as `-0.02em` (`mapping-guide.md` § Pixel values are whole pixels). The standards audit fails on one.
- **`layout.contentSize`/`wideSize`** replace CSS container `max-width`. Constrained groups read these. They are also what post content is laid out with in every template, and so the width of each new block an editor adds: set them to the design's text column and its wide column (`mapping-guide.md` § Post content sits at content width).
- **Disable defaults you replace** (`defaultPalette: false`, `defaultFontSizes: false`) so the editor only offers the design's tokens.
- **Slugs are an API.** Once a block references `var:preset|color|primary`, renaming the slug breaks it. Choose semantic slugs (`primary`, `accent`, `surface`) up front.
- **Four slugs are reserved, because their class is one core uses as a flag.** WordPress prints a class for every preset with `!important`: `.has-<slug>-color` for a palette entry and `.has-<slug>-font-size` for a font size. A palette entry named `border` therefore prints `.has-border-color { color: … !important }`, and `has-border-color` is also the class core adds to every block that has one border colour for all sides. Each such block's text takes the palette colour, and an inline text colour cannot beat it. By the same pattern `text` collides with `has-text-color`, `link` with `has-link-color`, and a font size named `custom` with `has-custom-font-size`. Name a preset by its role (`hairline`, `ink`, `accent`). The collision was observed for `border`; the other three follow from the class pattern in core. The standards audit fails on all four.
- **Slugs are kebab-cased when WordPress generates CSS.** A slug like `type-h1` expands to `--wp--preset--font-size--type-h-1` (and the class `has-type-h-1-font-size`) — WordPress inserts a dash at letter/digit boundaries. Hand-written CSS referencing the un-expanded name (`var(--wp--preset--font-size--type-h1)`) silently resolves to nothing. Choose slugs already in fully-expanded kebab form (`type-h-1`, `heading-1`) so `theme.json`, generated classes, and `var(--wp--preset--…)` references all match verbatim.
- **Variable-font condensed cuts need no CSS.** Register a second `fontFamilies` entry whose `fontFace` declares `"fontStretch": "75%"` (or the design's width) against the **same** woff2 — selecting that family renders the condensed cut at rung 1. This works for any variable font with a width (`wdth`) axis.
- **Fontsource filenames:** the multi-axis variable file is `<family>-latin-standard-normal.woff2` — a `-latin-full-normal.woff2` URL does not exist, even when a design handoff links it. Swap `full` → `standard` before downloading.

### Font faces: measure which file draws each weight

When one family is declared through several `@font-face` rules, including a variable face whose range covers the static ones, the file a weight is drawn from cannot be told from the order of the rules. An original can draw some weights from static files and others from the variable file, and the variable file's own instance at a static weight can be narrower than the static file. Neither "the static files" nor "the variable file for everything" then matches.

The measurement that settles it, in one call from the comparison harness (`visual-refinement.md`):

1. Load the candidate files as test families with the `FontFace` API.
2. Measure one long string at 100px at every weight the design uses, from four sources: the original's own declarations (a span in the original's pane), the build's, the variable file alone, and the static files alone.
3. Declare in `theme.json` the same split the original shows. A variable file can be declared for a sub-range (`"fontWeight": "601 799"`), which WordPress prints as it is.

- A design that uses weights between the static ones (650, 750) depends on the variable file. Without it the browser draws them with the next heavier static file.
- A width difference of a few hundredths of a percent is invisible in any box and still moves a line break at some width.
- If the page forces `font-family` with `!important`, apply the test face with `!important` too.
- Read a font file's character map before relying on a glyph it may not have.

## styles

Global element and block defaults so individual blocks stay clean:

```json
"styles": {
  "color": { "background": "var:preset|color|base", "text": "var:preset|color|contrast" },
  "typography": { "fontFamily": "var:preset|font-family|body", "lineHeight": "1.6" },
  "spacing": { "blockGap": "var:preset|spacing|40" },
  "elements": {
    "link":    { "color": { "text": "var:preset|color|primary" } },
    "heading": { "typography": { "fontFamily": "var:preset|font-family|heading", "fontWeight": "700" } },
    "button":  {
      "color": { "background": "var:preset|color|primary", "text": "var:preset|color|base" },
      "spacing": { "padding": { "top": "var:preset|spacing|20", "bottom": "var:preset|spacing|20", "left": "var:preset|spacing|40", "right": "var:preset|spacing|40" } },
      "border": { "radius": "6px" }
    }
  },
  "blocks": {
    "core/heading": { "typography": { "lineHeight": "1.2" } }
  }
}
```

Put a styling rule at the **most global level that is still correct**: element styles (`styles.elements.button`) over per-block, per-block (`styles.blocks.core/heading`) over per-instance. Only push values onto an individual block instance when that instance genuinely differs.

## Responsive token overrides

`theme.json` has no media queries for its tokens. When the design's tokens change per breakpoint (a tighter spacing or type scale on mobile), override the generated custom properties in the theme's root `style.css`. (A value on **one block** that changes per breakpoint is not a token: on WordPress 7.1 and later it is a per-viewport block attribute, `mapping-guide.md` § Per-viewport values.)

```css
@media (max-width: 781px) {
	:root:root {
		--wp--preset--spacing--80: 2.5rem;
	}
}
```

- Scope as **`:root:root`** — the doubled selector beats the global-styles `:root` block regardless of stylesheet print order; a bare `:root` override loses unpredictably.
- Root `style.css` is the home for these overrides — it is exempt from the one-file-per-block-type audit rule, while a separate `assets/css/tokens.css` is flagged STRAY. Note `style.css` must be explicitly enqueued on block themes (`standards.md`).

### Reset rules the design relies on

A design built on a reset (normalize, a utility framework's base layer) gets behaviour from it that neither blocks nor `theme.json` provide: `sub` and `sup` kept out of the line's height, for example, without which a paragraph with one superscript is a few pixels taller. When the design loads a reset, list which of its rules the content actually exercises and carry those, and only those, into the root stylesheet.

## Unifying across the file set

Because every design file feeds one theme:

1. Start from `analysis/tokens.json`: the design's tokens, read once from its stylesheets, each with the custom property or the selectors it comes from and the number of times it is used. Add what each view's report lists under `local_tokens`.
2. Deduplicate by value and intent; pick one slug per token.
3. Resolve conflicts (two files, slightly different "primary") by choosing the dominant value and noting the reconciliation in the blueprint.
4. Only after the unified set is settled do blocks start referencing it.

## What does not belong in theme.json

- One-off geometry for a single section (use the block instance's `style`).
- Behaviour/JS (see `custom-blocks-guide.md`).
- Anything achievable by a block style variation (registered in `functions.php` with `register_block_style()`, CSS in one file per block type under `assets/css/blocks/` — see `block-styles-guide.md`).
