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
    "fluid": true,
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
  }
}
```

- **`appearanceTools: true`** turns on border/spacing/typography UI in one switch — prefer it over enabling each support individually.
- **`layout.contentSize`/`wideSize`** replace CSS container `max-width`. Constrained groups read these.
- **Disable defaults you replace** (`defaultPalette: false`, `defaultFontSizes: false`) so the editor only offers the design's tokens.
- **Slugs are an API.** Once a block references `var:preset|color|primary`, renaming the slug breaks it. Choose semantic slugs (`primary`, `accent`, `surface`) up front.

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

## Unifying across the file set

Because every design file feeds one theme:

1. Merge each analyzer's detected tokens into one candidate set.
2. Deduplicate by value and intent; pick one slug per token.
3. Resolve conflicts (two files, slightly different "primary") by choosing the dominant value and noting the reconciliation in the blueprint.
4. Only after the unified set is settled do blocks start referencing it.

## What does not belong in theme.json

- One-off geometry for a single section (use the block instance's `style`).
- Behaviour/JS (custom block territory).
- Anything achievable by a block style variation (that goes in `/styles/*.json` — see `block-styles-guide.md`).
