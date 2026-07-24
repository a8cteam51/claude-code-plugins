# Annotation payload schema & source-mapping strategies

## Payload schema

The state node `<script type="application/json" id="__claude_annotations__">`
contains one JSON object:

```json
{
  "version": 2,
  "script": "0.2.0",
  "status": "annotating | sent | cancelled",
  "page": {
    "url": "https://example.com/pricing",
    "title": "Pricing — Example",
    "viewport": { "width": 1512, "height": 823, "dpr": 2 },
    "capturedAt": "2026-07-21T14:03:22.000Z"
  },
  "annotations": [
    {
      "id": 1,
      "note": "This button wraps to two lines on desktop — it shouldn't",
      "action": "review",
      "selector": "#pricing > div.tier-card:nth-of-type(2) > a.btn-primary",
      "tag": "a",
      "classes": ["btn", "btn-primary"],
      "text": "Start free trial",
      "outerHTML": "<a class=\"btn btn-primary\" href=\"/signup\">Start free trial</a>",
      "styles": { "display": "inline-flex", "font-size": "16px", "width": "142px", "...": "..." },
      "rect": { "x": 640, "y": 1180, "width": 142, "height": 58 },
      "createdAt": "2026-07-21T14:04:10.000Z"
    }
  ]
}
```

Field notes:

- `version` — payload schema version. `2` adds `script`; `1` payloads (from
  the pre-userscript overlay) are otherwise identical.
- `script` — the version of the installed userscript that produced this
  payload. If it disagrees with the `@version` in the plugin's
  `assets/page-annotator.user.js`, the browser is running a stale copy and
  should be updated (SKILL.md Step 4a).
- `action` — `"review"` or `"fix"`, chosen per annotation in the overlay UI.
  Governs handling: fix applies immediately, review proposes and waits for
  approval. Default to `"review"` when the field is missing (older capture).
- `updatedAt` — present only when the note was edited after first save (via
  its pin). Ids are stable: an edited annotation keeps its number, and a
  deleted one leaves a gap.
- `selector` — verified unique at capture time. IDs are preferred; common
  generated class-name patterns (CSS modules, styled-components, hex hashes)
  are filtered out, though unusual schemes can slip through; falls back to a
  full `nth-of-type` path when nothing stable exists.
- `text` — whitespace-collapsed `textContent`, max 200 chars. Often the
  strongest grep key.
- `outerHTML` — truncated at 1,500 chars and sanitized at capture: `value`
  and `on*` attributes removed, URL query strings stripped, `data:` URIs and
  token-looking strings redacted to `…`, inline script/style contents
  emptied. `class` and `id` are kept verbatim. Treat as a structural
  fingerprint, not a complete copy.
- `page.url` — token-looking strings in the URL are redacted to `…`; short
  query params (e.g. `?page_id=2`) survive.
- `styles` — ~20 computed properties (box model, typography, color, flex).
  Computed values, not authored values: `margin: 16px` in the payload may be
  authored as `1rem`, a shorthand, or a utility class.
- `rect` — document coordinates (scroll offset already added), rounded.
- `classes` — the full class list (minus the overlay's own `__claude*`
  internals), including hashed/utility classes that the selector filtered
  out. Use these for grepping even when unstable-looking.

## Mapping strategies by stack

Identify the stack first (framework config files, `wp-content/`, `package.json`)
— it decides which key to grep with.

### Plain HTML / template-driven sites (including PHP themes)

Grep for the ID, a distinctive class, or the visible text:

```bash
grep -rn "btn-primary" --include="*.html" --include="*.php" --include="*.twig" .
grep -rn "Start free trial" .
```

Text matches beat class matches when a class is used in many places.

### Tailwind (utility classes)

Individual utilities (`flex`, `mt-4`) are useless as grep keys. Grep for an
unusual *combination* in source order, or the rarest single utility
(arbitrary values like `w-[142px]` or `max-w-[68ch]` are near-unique):

```bash
grep -rn "inline-flex items-center gap-2" src/
grep -rn "w-\[142px\]" src/
```

Fall back to visible text.

### CSS modules / styled-components / Emotion

Rendered class names (`Button_root__x7f2a`, `sc-bdVaJa`) don't exist verbatim
in source. Strategies, in order:

1. CSS modules keep a readable prefix: `Button_root__x7f2a` → grep for a
   `Button` component and a `root` class in its module.
2. Grep for the visible text to find the component that renders it.
3. Grep for stable attributes in `outerHTML`: `href`, `aria-label`,
   `data-testid`, `alt`.

### WordPress block themes / Gutenberg

Class names encode the source block: `wp-block-<namespace>-<name>` maps to a
block, `wp-block-group`/`wp-block-columns` etc. to core blocks in template or
pattern files:

```bash
grep -rn "acme/pricing-card" wp-content/themes/theme-name/
grep -rn "Start free trial" wp-content/themes/theme-name/patterns/
```

For content stored in the database rather than templates, say so — the fix may
belong in the editor, not the repo. `wp-block-*` styling usually lives in
`theme.json` or per-block stylesheets under `styles/blocks/`.

### Client-rendered SPAs (React/Vue/Svelte)

The DOM is output, not source. Map via visible text, `aria-*`/`data-*`
attributes, and the route in `page.url` (file-based routers turn
`/pricing` into `pages/pricing.*` or `app/pricing/page.*`).

## Verifying a mapping

Before editing, confirm the candidate source actually produces the annotated
element: attribute values and structure in the source should correspond to the
captured `outerHTML` (allowing for templating), and for styling complaints the
authored CSS should plausibly produce the captured computed `styles`. If two
candidates survive, present both rather than picking silently.

## Using the visual data

- `rect` vs `page.viewport` shows where the element sat: overflow bugs
  (`rect.x + rect.width > viewport.width`), things pushed below the fold,
  zero-size elements (`width: 0` → rendering/visibility bug).
- `styles` gives the *symptom* values. Comparing them against the authored CSS
  reveals the cascade problem when a rule is being overridden.
- `viewport.width` matters for responsive complaints — a note made at 1512px
  is about desktop CSS, not the mobile breakpoint.
