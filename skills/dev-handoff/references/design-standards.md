# Design Standards & Defaults
Sources: WP Special Projects Designer Handbook — "Designer Role Overview" and "QA
Checklist and Performance Guidelines" (wpspecialprojectsp2.wordpress.com), and
theme.json — a8cteam51/beautyinbloom (used as the default token fallback).

Most of this file is fallback values: a project's own DESIGN.md (from brand guidelines,
brief, or client assets) always wins, and this file fills in only where the project
source is silent on a given token or convention.

**The Process Rules section below and the Type-Rendering Baseline are the exception.**
Both apply to every build, unconditionally — not because no brand source overrode them,
but because no brand source is a source of opinion on them in the first place. A brand
guide has a view on colors and type choices; it does not have a view on whether
`-moz-osx-font-smoothing` is set. Treating that absence as "silence to fall back into"
is how half of it went unshipped on a real build. There is nothing to defer to and
nothing to gap-check — apply it, and log a deviation only as a deliberate,
project-specific exception (see the Type-Rendering Baseline section for when that's
legitimate).

## Process Rules (non-negotiable, from the handbook)

- Every theme must support **standard Gutenberg blocks** — nothing that isn't
  editor-optimized will be accepted or launched.
- All fonts, icons, and imagery must be **open source or free-to-use commercially**,
  unless there is an explicit, confirmed budget/paying party for a licensed asset.
  Default to Google Fonts or other free/open-source libraries. Avoid Adobe Fonts
  (Typekit) due to licensing changes, unless the client has their own account.
- **Typography restraint**: limit to 1–2 typefaces per site, with a maximum of 3–4 fonts
  (weight/style variants) within a single typeface (e.g. regular, italic, bold,
  bold-italic).
- theme.json should always define an **explicit, closed set** for palette, font sizes,
  and spacing sizes — disable the WordPress core defaults rather than inherit them:
  `defaultPalette: false`, `defaultFontSizes: false`, `defaultSpacingSizes: false`,
  `defaultGradients: false`. This forces every value on the site to be an intentional,
  named token — never a WordPress core default leaking through.
- Set `appearanceTools: true` and `useRootPaddingAwareAlignments: true`.
- Standard WordPress views must be designed for (not just the homepage): homepage, blog
  index, single post, static page, archive/taxonomy pages, comments (if applicable),
  search results, and 404.
- Mobile mockups are required, not optional. Include at minimum a mobile homepage, menu,
  and any layout that doesn't obviously scale down.
- All interactive states must be designed, not improvised at build time: hover, focus,
  active, and disabled (where applicable) for text links, buttons, and form fields —
  forms specifically need hover/focus states that don't cause layout jump.
- Footer must include a "Proudly powered by WordPress" credit link back to WordPress.com
  (via the Colophon plugin convention) by default. (A Pressable-hosting variant of this
  credit may be added as a configurable toggle later — not yet implemented; default to
  the WordPress.com credit for now.)
- Use the "squint test" as a visual-hierarchy check: squinting at a page should make it
  immediately clear what's most important. If everything reads the same, hierarchy is
  insufficient.
- Required responsive breakpoints to test/design against: 320px, 375px, 414px, 768px,
  1024px, 1366px, 1440px, and 1600px+.
- **Apply the Type-Rendering Baseline (below) on every build, unconditionally.** Not
  brand-overridable — see the note at the top of this file. Verified at Step 11 Final
  QA by grepping the shipped `style.css`; see that section for the exact command.

## theme.json Skeleton (default token shape)

```
{
  "$schema": "https://schemas.wp.org/wp/7.0/theme.json",
  "version": 3,
  "settings": {
    "appearanceTools": true,
    "useRootPaddingAwareAlignments": true,
    "color": { "defaultGradients": false, "defaultPalette": false, "palette": [] },
    "layout": { "contentSize": "700px", "wideSize": "1512px" },
    "spacing": { "defaultSpacingSizes": false, "spacingSizes": [], "units": ["%","px","em","rem","vh","vw"] },
    "typography": { "defaultFontSizes": false, "fontFamilies": [], "fontSizes": [] }
  },
  "styles": { }
}
```

## Block-Specific Styling: theme.json First

This section covers *how to implement* a customization to a core WordPress block —
buttons, navigation, quotes, separators, the details/FAQ block, and so on. Default to
this order; don't reach for plain CSS in `style.css` first.

**This is about core WordPress blocks specifically.** A bespoke, single-purpose piece of
page markup — a hero section, a schedule row, a card grid built from a theme-specific
class like `.project-hero` — is not a block in this sense. Plain CSS is the right and
only tool for that; don't force this decision tree onto markup that was never a block to
begin with.

### The order to try

1. **Native `theme.json` style properties first.** `color`, `typography`, `spacing`,
   `border`, `shadow`, `dimensions` under `styles.blocks.<blockName>` (or
   `styles.elements.<name>` for the shared elements — `link`, `heading`, `caption`,
   `button`). If the customization is expressible this way, it needs no CSS at all.

2. **Per-block custom CSS when native properties can't reach it, and the treatment
   applies to every instance of the block.** `styles.blocks.<blockName>.css` is a raw
   CSS string, automatically scoped to that block's selector — available since **WP
   6.2**, not a newer or hypothetical feature. Use `&` for nested elements and
   pseudo-selectors:

   ```json
   "core/navigation": {
     "css": "& .current-menu-item > .wp-block-navigation-item__content { font-weight: 600; text-decoration: underline; }"
   }
   ```

   This is the right tier for layout properties native theme.json doesn't expose
   (`display`, `align-items`), pseudo-elements (a custom disclosure chevron on
   `core/details`), and structural-state selectors like `.current-menu-item` that have
   no native "current page" property.

3. **A registered block style variation when the treatment is optional — some
   instances, not all — and needs to be toggled per-instance from the block's Styles
   panel.** This tier has a hard requirement that's easy to get wrong: **a new,
   non-core variation must be registered in PHP or JS before theme.json can style
   it.** `styles.blocks.<name>.variations.<name>` only *styles* a variation that
   already exists — it cannot create the toggle by itself. Two required steps, in
   order:

   ```php
   // functions.php — Step 1: register the toggle
   register_block_style( 'core/button', [
     'name'  => 'secondary',
     'label' => __( 'Secondary', 'theme-slug' ),
   ] );
   ```

   ```json
   // theme.json — Step 2: style it
   "core/button": {
     "variations": {
       "secondary": {
         "color": { "background": "transparent", "text": "var(--wp--preset--color--accent)" },
         "border": { "color": "var(--wp--preset--color--accent)", "width": "2px" }
       }
     }
   }
   ```

   Skip Step 1 for a **core-provided** variation (buttons' built-in `is-style-outline`
   and `is-style-fill`, quote's `is-style-plain`) — those are already registered by
   WordPress itself, so `styles.blocks.<name>.variations.<name>` alone is enough.

   **Get this wrong and the treatment becomes invisible in the editor.** A styled-but-
   unregistered variation — a bespoke wrapper class with matching CSS but no
   `register_block_style()` call — looks identical in a code review to a working one,
   but an editor has no way to apply it through the block UI; it's only reachable by
   hand-editing markup. This is not a style-location preference at that point, it's a
   design decision nobody but the person who wrote the CSS can actually use.

### Worked examples

| Customization | Tier | Why |
|---|---|---|
| Every button needs a 44px minimum tap target | 2 — `.css` | `min-height`/`display`/`align-items` have no native theme.json property |
| The nav's current-page item needs an underline + weight change | 2 — `.css` | No native "current page" property; needs `&.current-menu-item` |
| A wider separator variant, using core's own `is-style-wide` | 3 — variation, no PHP needed | Core already registers `is-style-wide`; theme.json just needs to style it |
| An alternate "outline" button look meant for some CTAs, not all | 3 — variation, **PHP registration required** if not using core's built-in `is-style-outline` | Optional per-instance; needs an editor-facing toggle, which only PHP/JS registration provides |
| A custom disclosure chevron on the FAQ (`core/details`) block | 2 — `.css` | Pseudo-element marker (`::before`) with no native equivalent |

### At Final QA

Step 11 audits for exactly this — see `SKILL.md` Step 11 for the grep commands. Every
block-selector CSS rule found in `style.css` needs to be either migrated to one of the
tiers above, or logged as a deliberate exception with the reason it couldn't move (a
genuine theme.json gap, confirmed, not just unexplored). Every `is-style-*` selector or
custom variant class needs a matching `register_block_style()` call — that specific
check has no exception path, because an unregistered toggle isn't a design decision with
a reason, it's a broken feature.

## Color Palette — default shape

A brand palette should map to this 6–7 slot structural pattern unless the brand source
specifies otherwise:

| Slug        | Role                                      |
|-------------|--------------------------------------------|
| `contrast`  | Darkest neutral — primary text/headlines   |
| `contrast-2`| Mid neutral — borders, captions, metadata  |
| `base`      | Light neutral background (not pure white)  |
| `base-2`    | Secondary light/white background           |
| `accent`    | Primary accent — the sole interaction driver |
| `accent-2`  | Secondary/darker accent — hover states, emphasis |
| `inherit`   | `currentColor` passthrough for flexible contexts |

Fallback hex values are never assumed — the brand source must supply actual colors.
This is the *slot structure* to fill in, not a color choice.

## Status & Semantic Colors (error / success / warning / info)

**This is a scoped exception to the rule immediately above, and the scope matters.**
Brand identity colors stay unassumable: which blue a brand uses is an identity decision
that only the brand source can make. Status colors are different in kind — they are a
*functional accessibility requirement*, because both this file's Design QA checklist and
`accessibility-standards.md` require designed error and success states on forms. So the
build cannot decline to have them. Leaving them unspecified doesn't produce a careful
question; it produces an invented red at build time, which is the exact silent default
this system exists to prevent.

Ask about status colors at Gap-Check (the extraction schema now has fields for them).
Where the user has no preference, the fallback below applies.

### Default fallback: compose from existing palette tokens, not a new hue

The default status treatment introduces **no new colors at all**. Build the state from
tokens the project already has, plus a non-color signal:

- **Error** — `contrast` border (thickened), bold label text, and a warning glyph.
- **Success** — `contrast` border, bold label text, and a check glyph.
- **Warning / Info** — same structure, distinguished by glyph and wording.

This is the recommended default for three reasons. It satisfies "never signalled by
color alone" more strongly than a colored border does, since the glyph and weight carry
the meaning independently. It composes with any brand palette without clashing. And it
needs no contrast verification of its own, because every value in it is already a
verified token in the project's palette.

This is not theoretical — it is what `omfest` arrived at when it hit this gap, and its
error state passed the accessibility gate and Final QA unchanged.

### Opt-in: a conventional hued set

Some projects will want recognizable status hues, and that's a legitimate choice. If so,
it is an **explicit, logged decision**, and the hues must be:

- verified at AA against the project's *actual* `base` and `base-2` backgrounds, not
  against white in the abstract;
- paired with a non-color signal regardless, per `accessibility-standards.md` — the hue
  is added redundancy, never the sole carrier of meaning;
- recorded in DESIGN.md with the same Explicit / Inferred / Gap tagging as any other
  token.

No specific hex set is named here on purpose. A named red would get copied into projects
whose palettes it clashes with, and would be reached for ahead of the composed default
above simply because it is concrete.

## Typography — default scale & roles

Default role structure (fill in with brand-specified typefaces, respecting the 1–2
typeface / 3–4 font-variant limit above):

- **Body font** — variable-weight sans, used for all body copy and default typography.
- **Heading font** — variable-weight serif or distinctive display face, used for h1–h6
  and `.heading` elements only, not body copy.
- **Display/wordmark font** — a single bold weight, reserved for the site title/logotype.

Default font-size scale (fallback slugs and values, from theme.json):

| Slug         | Size                          |
|--------------|-------------------------------|
| `xx-small`   | 12px                          |
| `x-small`    | 14px                          |
| `small`      | clamp(15px, 1.8vw, 16px)      |
| `medium`     | clamp(16px, 1.8vw, 18px)      |
| `large`      | clamp(21px, 2.2vw, 22px)      |
| `x-large`    | clamp(24px, 2.8vw, 28px)      |
| `heading-6`  | clamp(18px, 3vw, 22px)        |
| `heading-5`  | clamp(21px, 3.5vw, 26px)      |
| `heading-4`  | clamp(24px, 4.5vw, 32px)      |
| `heading-3`  | clamp(30px, 6vw, 40px)        |
| `heading-2`  | clamp(36px, 8vw, 48px)        |
| `heading-1`  | clamp(64px, 9vw, 128px)       |

Default line-height convention: h1/h2 → 1; h3/h4 → 1.16; h5/h6 → 1.2; body → 1.6 (must
still satisfy the accessibility-standards.md minimum of 1.5 for body copy).
Default heading letter-spacing: -0.025em (tightened, not default browser tracking).

## Type-Rendering Baseline (non-negotiable — apply on every build)

**This is the canonical location for these rules, and they are a Process Rule, not a
fallback.** They previously lived only in `accessibility-standards.md`, which was the
wrong home twice over: they are typographic rendering conventions, not accessibility
success criteria, and filing them under "fallback conventions" implied a brand source
could pre-empt them by specifying its own — which no brand source has ever done, or
would. A build looking for type conventions in the obvious place found nothing and
reinvented them, and shipped only half the smoothing pair as a result. That's the
failure this section exists to close, not just document.

```css
body {
	font-synthesis: none;
	text-rendering: geometricPrecision;
	-webkit-font-smoothing: antialiased;
	-moz-osx-font-smoothing: grayscale;
}

html {
	scroll-behavior: smooth;
}

h1, h2, h3, h4, h5, h6, p, blockquote, caption, figcaption, li {
	text-wrap: pretty;
}

/* Prevent unintentional extra-bold nested headings */
.wp-block-heading strong,
.wp-block-heading b {
	font-weight: inherit;
}
```

**Verify it actually shipped — don't rely on remembering to have written it.** At Step
11 Final QA, run this against the built theme's `style.css`:

```
grep -c "font-synthesis: none" theme/style.css
grep -c "text-rendering: geometricPrecision" theme/style.css
grep -c "\-webkit-font-smoothing: antialiased" theme/style.css
grep -c "\-moz-osx-font-smoothing: grayscale" theme/style.css
grep -c "scroll-behavior: smooth" theme/style.css
```

Every command must return a nonzero count. If any returns 0, the baseline is
incomplete — fix it before presenting the theme as finished, the same way a failing
`npx @google/design.md lint` blocks Step 8. This is the check that would have caught
the missing `-moz-osx-font-smoothing` half on `omfest` mechanically, instead of by
someone happening to ask about it directly. A deliberate exception (e.g. dropping the
smoothing pair for a heavy design, per the note below) is fine — but log it as a named
exception in DESIGN.md rather than letting the grep silently fail with no explanation
on record.

Notes on the individual rules:

- **`font-synthesis: none`** — required, not optional, and the one addition to the
  previously-documented set. It is the enforcement mechanism for the Design QA checklist
  item "no faux-bold/faux-italic": it converts a missing weight from an invisible problem
  (the browser fakes it, badly) into a visible one (the hierarchy collapses and you
  notice). Especially load-bearing under a light weight ladder, where a synthesized bold
  is both ugly and easy to miss.
- **`text-rendering: geometricPrecision`** — this is the team value. Do not substitute
  `optimizeLegibility` without logging it as a deliberate, project-specific decision;
  `optimizeLegibility` has a real layout-performance cost on long pages, and one
  engagement has already swapped it in by improvisation rather than by choice.
- **The smoothing pair — set both halves or neither.** `-webkit-font-smoothing` and
  `-moz-osx-font-smoothing` cover different engines on macOS. Shipping only the
  `-webkit-` half is a silent inconsistency, and it has happened on a real build. Note
  that these thin strokes on macOS, which suits a light type ladder and works against a
  heavy one — so dropping them for a heavy design is legitimate, but state it either way.
- **`scroll-behavior: smooth`** — pair it with a `prefers-reduced-motion` block that
  resets it to `auto`, per the Media & Motion rules in `accessibility-standards.md`.
- **`text-wrap: pretty`** — improves rag and prevents orphans. If a design depends on
  deliberate manual line breaks in headings, narrow the selector and say why.
- **`font-optical-sizing`** — leave at the browser default (`auto`). Only set it
  explicitly when the family has a real `opsz` axis *and* the design wants to override
  its automatic behavior. Setting it on a family without that axis does nothing and
  misleads the next reader into thinking it does.

**Inline `<strong>` / `<b>` needs an explicit weight when body copy is lighter than
400.** The UA stylesheet uses `font-weight: bolder`, which is *relative* — it steps up
from the inherited weight rather than naming an absolute one. Against a 300 body that
computes to roughly 400, making inline emphasis nearly invisible; combined with
`font-synthesis: none` it can end up with no emphasis at all. Pin it to a real instance
of the family's weight axis (e.g. 700). This is a legitimate exception to a design's
stated weight ceiling, because the weight is carrying semantic emphasis rather than
presentation. Note this is a different scope from the heading rule above: that one
prevents `<strong>` *inside a heading* from going extra-bold; this one makes `<strong>`
*inside body copy* visible at all.

## Spacing — default scale (fallback values, from theme.json)

| Slug   | Value                          |
|--------|--------------------------------|
| 10     | 4px                            |
| 20     | 8px                            |
| 30     | 12px                           |
| 40     | 16px                           |
| 50     | clamp(20px, 2.4vw, 24px)       |
| 60     | clamp(24px, 3.2vw, 32px)       |
| 70     | clamp(40px, 4.8vw, 48px)       |
| 80     | clamp(48px, 6.4vw, 64px)       |
| 90     | clamp(64px, 9.6vw, 96px)       |
| 100    | clamp(72px, 12.8vw, 128px)     |
| 110    | clamp(96px, 19.2vw, 192px)     |
| body-margin | clamp(24px, 4vw, 48px) — root left/right padding |
| grid-gutter | clamp(16px, 4.8vw, 48px) — used between grid/column items |

Notice the pattern: spacing scales up using `clamp()` from the 50-slot onward, so large
spacing shrinks responsively on small viewports rather than needing separate breakpoint
overrides.

## Layout

- Default content width: 700px. Default wide width: 1512px.
- Root block gap: 0px — spacing between blocks should be deliberate (via block-level
  margin/padding), not an ambient global gap.
- Root padding: left/right use the `body-margin` spacing token; top/bottom 0px.
- Site must be fully responsive across phone, tablet, and desktop, with fluid
  interactions on touch devices, at minimum across the required breakpoints listed above.

## Component Defaults

**Buttons**
- Define an explicit hover state with a color swap (background + text), not just an
  opacity change.
- Uppercase button label text with letter-spacing ~0.05em is an accepted default
  treatment — override per brand.
- Padding should use `em` units so it scales with the button's own font-size, not fixed px.
- Border-radius is brand-specific — do not assume rounded or sharp; confirm from source.

**Navigation**
- Uppercase, letter-spacing ~0.05em, no underline by default, underline on hover is a
  common accepted pattern — override per brand voice.
- Nav item gap uses a spacing token (not an arbitrary px value).
- Include a current-location indicator style (per accessibility-standards.md).

**Links (body copy)**
- Inverse of nav convention by default: underlined by default, no underline on hover,
  color inherits from surrounding text rather than a separate "link blue."

**Headings**
- Use the dedicated heading font/weight/letter-spacing, distinct from body typography —
  never let headings silently inherit body font styling.

**Footer**
- Include the "Proudly powered by WordPress" Colophon credit link by default (see
  Process Rules above).

## Design QA Checklist (pre-handoff and pre-launch)

- [ ] Typography samples, color samples, 1–2 button treatments, image treatment, and
      header/logo/nav treatment were defined before full-page mockups began — this is
      the style tile from `SKILL.md` Step 5, approved in Step 6, before Development
      begins
- [ ] All standard WordPress views designed (homepage, blog index, single post, static
      page, archive/taxonomy, comments if applicable, search results, 404)
- [ ] Mobile mockups provided
- [ ] Font licensing confirmed (Google/open-source, or budget owner identified)
- [ ] Correct font weights/styles load (no faux-bold/faux-italic — verified with
      font-synthesis disabled)
- [ ] Favicon exists (512x512px)
- [ ] Default social sharecard image exists (1200x675px) — verify via metatags.io or
      linkpreview.xyz
- [ ] Theme preview thumbnail exists (1200x900px), if applicable
- [ ] Pagination designed
- [ ] Search results page designed (if not using Jetpack Search)
- [ ] Taxonomy/archive pages designed
- [ ] 404 page designed
- [ ] Forms: hover & focus states designed without causing layout jump; success/error
      message states shown
- [ ] Loading-state indicators designed (e.g. infinite scroll)
- [ ] Content tested against Gutenberg unit-test data for common block rendering
- [ ] Navigation is identifiable, labels consistent
- [ ] Site search (if present) is easy to find
- [ ] Styles and colors consistent across all designed views
- [ ] URLs meaningful and user-friendly
- [ ] Images have appropriate alt text and are high-resolution at all viewport sizes
- [ ] "Proudly powered by WordPress" footer credit present
- [ ] Design resizes gracefully across all required breakpoints, including
      untested-for sizes like tablet
- [ ] All placeholder content removed
- [ ] Legacy imported content (if applicable) reviewed for styling/layout fit