# WPBakery → Gutenberg Shortcode Mappings

Reference table and conversion plan for every `vc_*` shortcode this plugin handles. The conversion skill consumes this doc; humans read it to understand coverage and edge cases.

## Scope and target

- **Target blocks:** core/* only. No dependency on third-party block libraries (Kadence, Greenshift, GenerateBlocks). If a shortcode has no core equivalent, the fallback is `core/html` containing semantic markup the theme can style.
- **Fidelity policy:** preserve content and structure. Drop animation, parallax, and visual-effect attributes silently — they have no faithful core counterpart and shouldn't be reinvented in inline CSS.
- **Attribute coverage:** common attributes (alignment, color, css, id, class) are documented per shortcode. Long-tail attributes (z-index, parallax_speed, css_animation_delay) are dropped — the conversion log should record the drop, not the doc.

## Confidence legend

Each shortcode row carries a confidence tag for the mapping:

- **High** — direct core block equivalent, well-tested community pattern.
- **Medium** — core block exists but loses one or more meaningful WPBakery features; convertible with documented compromises.
- **Low** — no clean core equivalent; conversion produces `core/html` or a structural approximation. Human review recommended.

---

## 1. Quick reference table

| Shortcode | Target block(s) | Confidence | Notes |
|---|---|---|---|
| `vc_row` | `core/columns`, or `core/group` for single-column, or `core/cover` when a background-image is set | High | See section 2 for branch logic |
| `vc_section` | `core/group` with `align=full`, or `core/cover` when a background-image is set | High | Background-image branch same as `vc_row` |
| `vc_row_inner` | `core/columns` | High | Nested row → nested columns |
| `vc_column` | `core/column` | High | `width` → `width` attr (`1/2` → `50%`) |
| `vc_column_inner` | `core/column` | High | Same as `vc_column` |
| `vc_column_text` | `core/paragraph` (one per `<p>`) | High | Split HTML into paragraph blocks |
| `vc_custom_heading` | `core/heading` | High | `font_size`, `text_align` → block attrs |
| `vc_btn` | `core/buttons` + `core/button` | High | Single button wraps in `core/buttons` |
| `vc_separator` | `core/separator` | High | `color` → `customColor` attr |
| `vc_empty_space` | `core/spacer` | High | `height="32px"` → `height: 32px` |
| `vc_single_image` | `core/image` | High | `image` is attachment ID; resolve src |
| `vc_gallery` | `core/gallery` | High | `images="1,2,3"` → ids array |
| `vc_images_carousel` | `core/gallery` (+ note) | Medium | Carousel UX lost; gallery preserves images |
| `vc_video` | `core/embed` or `core/video` | High | YouTube/Vimeo → embed; mp4 → video |
| `vc_raw_html` | `core/html` | High | Decode base64 payload, wrap in html block |
| `vc_raw_js` | `core/html` | Medium | Editor-blocked — leave with a TODO comment |
| `vc_icon` | `core/html` | Low | No core icon block; emit `<i>` markup |
| `vc_message` | `core/group` + `core/paragraph` | Medium | Style via group class; preserve `message_box_color` as class |
| `vc_cta` | `core/group` + heading + paragraph + button | Medium | Composite; structure preserved |
| `vc_tta_tabs` / `vc_tta_section` | `core/html` (semantic `<details>` or markup) | Low | No core tabs block |
| `vc_tta_accordion` / `vc_tta_section` | `core/details` (one per section) | Medium | `core/details` is the closest core block |
| `vc_tta_tour` | `core/html` | Low | Vertical tabs; no core equivalent |
| `vc_tta_pageable` | `core/html` | Low | Pagination UX lost |
| `vc_progress_bar` | `core/html` | Low | No core progress block; emit `<progress>` |
| `vc_pie` / `vc_round_chart` / `vc_line_chart` | `core/html` | Low | Charts require JS — leave a TODO |
| `vc_basic_grid` / `vc_masonry_grid` / `vc_media_grid` | `core/query` + `core/post-template` | Medium | Grid type lost (masonry CSS optional) |
| `vc_posts_slider` | `core/query` (+ TODO) | Low | Slider UX lost |
| `vc_facebook` / `vc_tweetmeme` / `vc_googleplus` / `vc_pinterest` | drop or `core/html` | Low | Most are dead social widgets — default to drop with log |
| `vc_widget_sidebar` | `core/html` placeholder | Low | Widget areas don't map cleanly into post content |
| `vc_gmaps` | `core/html` with iframe | Medium | Preserve the embed URL |
| `contact-form-7` / `gravityforms` (inside vc_) | passthrough | High | Leave nested non-vc shortcodes intact |

---

## 2. Layout shortcodes

### `vc_section`

Top-level full-width container, typically wrapping `vc_row` children.

**Target:** `core/group` with `align="full"`.

```html
<!-- wp:group {"align":"full"} -->
<div class="wp-block-group alignfull">…children…</div>
<!-- /wp:group -->
```

Attributes:
- `el_class` → append to `className`
- `el_id` → `anchor`
- `css` (Visual Composer custom CSS) → parse the encoded CSS, lift `padding`/`margin`/`background-color`/`background-image` per section 13. A `background-image` switches the target block from `core/group` to `core/cover` (same branch logic as `vc_row` section 2).
- `full_width="stretch_row"` is already implied by `align=full`.

### `vc_row` / `vc_row_inner`

A row of columns. WPBakery renders `vc_row` in **four width modes** controlled by the `full_width=` attribute (and reflected in the rendered HTML via `data-vc-full-width`, `data-vc-stretch-content`, and the `vc_row-no-padding` class). Each maps to a different Gutenberg shape:

| `full_width=` value | Rendered HTML signature | Target block | Notes |
|---|---|---|---|
| *(unset)* | `<div class="vc_row wpb_row vc_row-fluid">` | `core/columns` (or `core/group` for single column) | Default content-width row. No `align` attr. |
| `stretch_row` | `data-vc-full-width="true"`, no `data-vc-stretch-content` | `core/group` with `align: "full"` containing a `core/columns` inside | Row background spans viewport, but inner content stays at content width. The inner `core/columns` gets no `align` so it constrains itself; the outer `core/group` is what stretches. |
| `stretch_row_content` | `data-vc-full-width="true" data-vc-stretch-content="true"` | `core/columns` with `align: "full"` | Both row and content stretch edge-to-edge. Columns keep default WP gap. |
| `stretch_row_content_no_spaces` | `data-vc-full-width="true" data-vc-stretch-content="true"` plus `vc_row-no-padding` class on the wrapper | `core/columns` with `align: "full"` **and** `style.spacing.blockGap: "0"` | Edge-to-edge with zero gap between columns. Used for image grids / full-bleed mosaics. |

**Then branch on `css=` and column count, independent of the width mode above:**

1. **`background-image` present in `css=`** → swap the target to `core/cover`. The cover block is the only core block that combines a container with a background image. Inner columns become children of the cover. Apply the `align: "full"` from the width-mode table to the cover. Map:
   - `background-image: url(…)` → `core/cover` `url` attr; if the URL resolves to an attachment, also set `id`.
   - `background-color` co-present → `core/cover` `overlayColor` (named) or `customOverlayColor` (hex). WPBakery treats this as a solid overlay; preserve that semantic.
   - Default `dimRatio` to `0` when only a background-image is set (WPBakery doesn't apply a dim by default). Set `dimRatio: 50` only when both color and image are present, so the color reads as an overlay.
2. **No background-image, one direct `vc_column` child** → if the width-mode is unset, emit `core/group` (avoids an empty `core/columns` wrapper). For `stretch_row` mode, the outer `core/group` already exists; skip the inner `core/columns` and put the single column's children directly in the group.
3. **No background-image, multiple columns** → use the target from the width-mode table as-is.

```html
<!-- Unset / default: contained columns -->
<!-- wp:columns -->
<div class="wp-block-columns">…columns…</div>
<!-- /wp:columns -->

<!-- full_width="stretch_row": full-bleed background, contained content -->
<!-- wp:group {"align":"full"} -->
<div class="wp-block-group alignfull">
  <!-- wp:columns -->
  <div class="wp-block-columns">…columns…</div>
  <!-- /wp:columns -->
</div>
<!-- /wp:group -->

<!-- full_width="stretch_row_content": full-bleed row and content -->
<!-- wp:columns {"align":"full"} -->
<div class="wp-block-columns alignfull">…columns…</div>
<!-- /wp:columns -->

<!-- full_width="stretch_row_content_no_spaces": full-bleed, zero gap -->
<!-- wp:columns {"align":"full","style":{"spacing":{"blockGap":"0"}}} -->
<div class="wp-block-columns alignfull">…columns…</div>
<!-- /wp:columns -->

<!-- background-image branch (any width mode) -->
<!-- wp:cover {"url":"…","dimRatio":0,"align":"full"} -->
<div class="wp-block-cover alignfull">…columns or content…</div>
<!-- /wp:cover -->
```

Attribute mappings (apply on top of the width-mode target above):

| WPBakery attr | Gutenberg |
|---|---|
| `el_class` | append to `className` |
| `el_id` | `anchor` |
| `equal_height="yes"` | `core/columns` `verticalAlignment: "center"` (see note below) |
| `content_placement="middle"` | `core/columns` `verticalAlignment: "center"` |
| `content_placement="top"` | `verticalAlignment: "top"` |
| `content_placement="bottom"` | `verticalAlignment: "bottom"` |
| `css` | see section 13 decoder |
| `full_width=` | handled by the width-mode table above — do not also emit a separate `align: "full"` |

**Note on `equal_height` → `verticalAlignment: "center"`:** the mapping isn't exact. WPBakery's `equal_height="yes"` stretches all columns to the height of the tallest, then aligns content per `content_placement` (default top). Gutenberg's `verticalAlignment` positions content within columns without forcing equal heights — columns are already equal-height by default in flex layout. For most real-world layouts this difference is invisible, but two cases diverge:

- A row using `equal_height="yes"` with `content_placement` unset (WPBakery default = top) is best mapped to `verticalAlignment: "top"`, **not** `"center"`. Only map `equal_height` to `"center"` when no `content_placement` contradicts it, and prefer `content_placement` when both are set.
- A row that relied on `equal_height` to give a colored column background the full row height will work in Gutenberg without any mapping — flex columns are already equal-height.

Skip the mapping (don't emit `verticalAlignment`) when there's only one column. [Confidence: Medium — the mapping is a common-case approximation, not a semantic equivalent]

### `vc_column` / `vc_column_inner`

**Target:** `core/column`. Convert WPBakery width tokens:

| WPBakery `width` | Gutenberg `width` |
|---|---|
| `1/1` | `100%` |
| `1/2` | `50%` |
| `1/3` | `33.33%` |
| `2/3` | `66.66%` |
| `1/4` | `25%` |
| `3/4` | `75%` |
| `1/6` | `16.66%` |
| `5/6` | `83.33%` |

Drop responsive overrides (`offset`, `css="vc_col-sm-…"`). They produce churn for low value; flag in conversion log.

---

## 3. Text content

### `vc_column_text`

Free HTML content. WPBakery wraps the inner HTML in a single shortcode; Gutenberg expects each `<p>`, `<h*>`, `<ul>`, `<img>`, etc. as its own block.

**Algorithm:**
1. Strip the `vc_column_text` wrapper.
2. Parse inner HTML with a DOM parser.
3. Walk top-level children, emitting one block per element:
   - `<p>` → `core/paragraph`
   - `<h1>`–`<h6>` → `core/heading` (level matches)
   - `<ul>` / `<ol>` → `core/list`
   - `<blockquote>` → `core/quote`
   - `<img>` standalone → `core/image`
   - `<a>` wrapping `<img>` → `core/image` with `linkDestination`
   - Anything else → `core/html` with the element verbatim

Inline formatting (`<strong>`, `<em>`, `<a>`) stays inside paragraph/heading content; do not split.

### `vc_custom_heading`

**Target:** `core/heading`.

| WPBakery attr | Gutenberg |
|---|---|
| `text` | inner HTML |
| `font_container="tag:h2|text_align:center|color:%23333"` | parse the pipe-separated bag: `tag:h2` → `level`, `text_align:center` → `textAlign`, `color:%23333` → `style.color.text` |
| `link` | wrap inner text in `<a>` |
| `google_fonts` | drop (theme should govern fonts) |

---

## 4. Buttons & calls to action

### `vc_btn`

**Target:** `core/button` wrapped in `core/buttons`.

```html
<!-- wp:buttons -->
<div class="wp-block-buttons">
  <!-- wp:button -->
  <div class="wp-block-button"><a class="wp-block-button__link">Label</a></div>
  <!-- /wp:button -->
</div>
<!-- /wp:buttons -->
```

| WPBakery | Gutenberg |
|---|---|
| `title` | inner anchor text |
| `link="url:https%3A%2F%2F…|title:Click|target:_blank"` | decode and split: href, title, target |
| `style="flat|outline|3d"` | `flat` → default; `outline` → `className: is-style-outline`; others drop |
| `color` | named palette color when matchable, else custom hex |
| `size` | `small`/`medium`/`large` → `fontSize` slug |
| `align="center"` | `core/buttons` `layout.justifyContent=center` |

### `vc_cta`

Composite block (heading + paragraph + button in a styled container).

**Target:** `core/group` containing `core/heading`, `core/paragraph`, `core/buttons`. Preserve the WPBakery `style` and `color` as a className (e.g. `is-style-vc-cta-classic`) so themes can re-style without losing semantics.

---

## 5. Media

### `vc_single_image`

**Target:** `core/image`.

| WPBakery | Gutenberg |
|---|---|
| `image="123"` (attachment ID) | `id: 123`, resolve `src` from media library |
| `img_size="medium"` / `large` / `WxH` | map to `sizeSlug` or use closest registered size |
| `alignment="center"` | `align: center` |
| `onclick="link_image"` | `linkDestination: media` |
| `onclick="custom_link"` + `link="…"` | `linkDestination: custom`, set href |
| `alt`/`title` | image attrs; do not drop |
| `style="vc_box_shadow|vc_box_rounded"` | append matching className |


### `vc_gallery`

**Target:** `core/gallery` with nested `core/image` blocks.

`images="11,12,13"` → split to integer ids. Each id becomes a nested `core/image` block. `type="image_grid"` is the only mode that maps cleanly; `flexslider_*` and `nivo` collapse to gallery (carousel UX lost — log it).

### `vc_images_carousel`

**Target:** `core/gallery` with a note in the conversion log. There is no core carousel block; preserving images is the priority.

### `vc_video`

**Target:** depends on `link`:

- YouTube / Vimeo / SoundCloud / Spotify → `core/embed` with `providerNameSlug` and `url`.
- Self-hosted `.mp4`/`.webm` → `core/video`.

`el_width` and `el_aspect` map to `core/embed` `align` and aspect ratio class names where possible.

---

## 6. Spacing & dividers

### `vc_separator`

**Target:** `core/separator`.

| WPBakery | Gutenberg |
|---|---|
| `color="custom"` + `accent_color="#abc"` | `style.color.background` |
| `style="dashed"` / `dotted` | `className: is-style-dashed` (custom style) |
| `border_width` | `style.border.width` |
| `el_width="50"` | `style.width` (px); core supports a width attribute via inline style |

### `vc_empty_space`

**Target:** `core/spacer`. `height="32px"` → `height: 32px`. Drop responsive overrides.

---

## 7. Code & raw markup

### `vc_raw_html`

Inner content is base64-encoded.

**Algorithm:**
1. Base64-decode the inner content.
2. Emit `core/html` containing the decoded markup verbatim.

### `vc_raw_js`

**Target:** `core/html`. Gutenberg blocks the script tag in the editor (KSES), so the conversion should:

1. Base64-decode.
2. Emit `core/html` with the script tag.
3. Add a conversion-log warning that the post author may need to use a code-injection plugin or move the script to the theme.

---

## 8. Tabs, accordions, tours

These are the hardest cases — no core block matches the tab/accordion UX.

### `vc_tta_accordion` + `vc_tta_section`

**Target:** one `core/details` per section, wrapped in a `core/group`.

```html
<!-- wp:group -->
<div class="wp-block-group">
  <!-- wp:details -->
  <details class="wp-block-details"><summary>Section title</summary>…content…</details>
  <!-- /wp:details -->
  …more details…
</div>
<!-- /wp:group -->
```

This loses the "one open at a time" behavior but preserves content semantics and is keyboard-accessible. Recursively convert each `vc_tta_section`'s inner shortcodes.

### `vc_tta_tabs` / `vc_tta_tour` / `vc_tta_pageable`

**Target:** `core/html` containing a semantic `<div role="tablist">` skeleton, OR fall back to a `core/group` of `core/details` (same as accordion) for accessibility without JS.

Default: fall back to details — content stays accessible, JS-free. Document this lossy conversion in the log.

### `vc_tta_section`

Only meaningful inside a parent `vc_tta_*`. The conversion walker should not encounter this at the top level. If it does, treat the content as a `core/group` and emit a warning.

---

## 9. Data widgets (charts, progress, icons)

### `vc_progress_bar`

**Target:** `core/html` with `<progress>` element.

```html
<progress value="75" max="100">75%</progress>
```

Preserve `values="Skill A|75,Skill B|50"` by emitting one `<progress>` per pair, each preceded by a label.

### `vc_pie` / `vc_round_chart` / `vc_line_chart`

**Target:** `core/html` placeholder with a comment marker, e.g.:

```html
<!-- TODO(wpbakery-migration): pie chart "Sales 75%" — implement with Chart.js or a chart block -->
```

These shortcodes rely on Chart.js bundled by WPBakery. There is no faithful core conversion; preserving the data in a TODO is the honest outcome.

### `vc_icon`

**Target:** `core/html` emitting the icon library markup (`<i class="fa fa-star"></i>` or the dashicon equivalent). If the original used `icon_fontawesome="fas fa-star"`, preserve the classes verbatim — the theme already enqueues the icon font in most WPBakery sites. Verify on a per-project basis.

---

## 10. Posts grids and queries

### `vc_basic_grid` / `vc_masonry_grid` / `vc_media_grid`

**Target:** `core/query` + `core/post-template` + chosen child blocks.

| WPBakery | Gutenberg query attr |
|---|---|
| `post_type="post"` | `query.postType` |
| `posts_per_page="6"` | `query.perPage` |
| `taxonomies="3,5"` (term ids) | `query.taxQuery` |
| `orderby="date"` / `orderby="title"` | `query.orderBy` |
| `order="DESC"` | `query.order` |
| `grid_id` / `item` (which grid template) | drop; emit a default post template |

Masonry CSS layout is lost unless the theme implements it. Log this and let the project decide whether to add CSS post-conversion.

### `vc_posts_slider`

Same query mapping; slider behavior is lost. Emit a TODO and a `core/query`.

---

## 11. Social & legacy widgets

Most legacy social shortcodes target dead products:

- `vc_facebook` (Like button) — Facebook deprecated the Like Button SDK in 2024; default to **drop with log**.
- `vc_googleplus` — Google+ is shut down; **drop with log**.
- `vc_tweetmeme` — Tweet-Meme service is dead; **drop with log**.
- `vc_pinterest` — emit `core/html` with the current Pinterest "Save" button snippet, since that one still works.

---

## 12. Maps, sidebars, misc

### `vc_gmaps`

`link` contains a base64-encoded Google Maps iframe embed. Decode and emit `core/html` containing the iframe.

### `vc_widget_sidebar`

Widget areas don't belong in post content. Emit a `core/html` placeholder with a TODO referencing the sidebar id, so the editor surfaces it for manual replacement (likely a `core/template-part`).

### `vc_message`

**Target:** `core/group` with a className (`is-style-vc-message-info` / `…-warning` / `…-success`) so the theme can style. Inner content converts recursively. Map `message_box_color` to a className suffix.

---

## 13. Attribute decoding helpers

WPBakery encodes structured attributes in a pipe-and-URL-encoded format. The conversion skill needs these helpers:

### `link` attribute

```
link="url:https%3A%2F%2Fexample.com%2Fpath|title:Click%20me|target:_blank|rel:nofollow"
```

Decoding: split on `|`, then split each part on the first `:`, then URL-decode the value. Produces `{url, title, target, rel}`.

### `font_container` attribute

```
font_container="tag:h2|font_size:32|color:%23ff0000|text_align:center|line_height:1.2"
```

Same split rules. Produces the bag used for heading attribute mapping.

### `css` attribute

```
css=".vc_custom_1234567890{padding-top: 20px !important; background-image: url(https://…/hero.jpg) !important; background-color: #fff !important;}"
```

This is a single CSS rule for a generated class. Parse the declaration block, strip `!important`, and lift the following declarations into Gutenberg attrs:

| CSS declaration | Lift to |
|---|---|
| `padding-*` | block `style.spacing.padding.{top|right|bottom|left}` |
| `margin-*` | block `style.spacing.margin.{top|right|bottom|left}` |
| `background-color` | block `style.color.background` (or `backgroundColor` named slug if it matches the palette) |
| `background-image: url(…)` | **see block-swap rule below** |

Everything else (border, opacity, transform, box-shadow, transition, custom font-size) is discarded — visual polish the theme should govern.

**Block-swap rule for `background-image`:**

On `vc_row`, `vc_row_inner`, `vc_column`, `vc_column_inner`, and `vc_section`, a `background-image` declaration changes the *target block* (not just an attr):

- `vc_row` / `vc_row_inner` / `vc_section` → `core/cover` instead of `core/columns` / `core/group`. Inner columns become children of the cover. See section 2 for the cover-attr mapping.
- `vc_column` / `vc_column_inner` → still `core/column`, but wrap the column's content in a `core/cover` child. Core columns don't support a background image directly.

The image URL goes into the cover block's `url` attribute. If the URL resolves to a known attachment (e.g. ends in a path matching a media-library file), also set `id` so the editor can re-link the attachment.

If a `background-color` is co-present with `background-image`, treat the color as the cover's overlay (`overlayColor` / `customOverlayColor`) with `dimRatio: 50`. If only an image is set, use `dimRatio: 0` — WPBakery doesn't dim by default.

---

## 14. Unhandled / unknown `vc_*` shortcodes

For any `vc_*` shortcode not listed above, the conversion skill should:

1. Emit `core/shortcode` containing the original shortcode source.
2. Log it to the conversion report so the user can decide whether to map it or accept the raw passthrough.

This keeps conversions lossless-by-default for the long tail and surfaces gaps without blocking the run.
