# Changelog

## [0.1.1] - 2026-07-23

### Changed

- Smaller injection payload: `overlay.min.js` shrunk from 12,180 to 10,746
  bytes (-12%) with no functional change.
  - `build-overlay.sh` now collapses insignificant whitespace inside the
    overlay's HTML/CSS template literal before minifying — esbuild never
    touches string contents, so the template previously shipped with all its
    indentation (a third of the payload).
  - Deduplicated repeated logic in `overlay.js` into shared helpers
    (timestamps, rects, sibling filtering, save/delete commit path) and
    switched the UI lookup map to id-keyed iteration.
  - Dropped the `CSS.escape` fallback and legacy font stack — the overlay
    only ever runs in Chrome via the Claude in Chrome extension.

## [0.1.0] - 2026-07-21

### Added

- Initial release.
- `annotate` skill: injects an annotation overlay into the current Chrome tab
  via the Claude in Chrome extension, polls for user annotations, and acts on
  each one per its action — **Review** (propose, ask first) or **Fix** (apply
  immediately) — chosen directly in the overlay's note panel.
- Bundled dependency-free `overlay.js` (element picker, note panel, numbered
  pins, DOM-node state channel).
- Capture-time scrubbing of form values, URL query strings, and token-like
  strings, plus a scoped-read fallback for when the extension bridge's safety
  filter blocks the full-payload read.
- Overlay persists after Send for follow-up batches; cleanup is user-driven
  (refresh, close tab, or ✕) — the agent never removes it.
- Automatic post-fix refresh: after applying changes, Claude reloads the tab
  and re-injects the overlay so the annotation tool persists across rounds.
- Clickable pins: re-open a saved note to edit its text or Review/Fix action,
  or delete it; edited annotations carry `updatedAt` and re-arm the Send
  button as a new batch.
- Faster injection: a committed minified build (`overlay.min.js`, generated
  by `scripts/build-overlay.sh`) shrinks the first inject, and the overlay
  caches its own source in sessionStorage so re-injections are a tiny
  snippet.
- `references/source-mapping.md`: annotation payload schema and DOM-to-source
  mapping strategies for common stacks (Tailwind, CSS modules, WordPress block
  themes, SPAs).
