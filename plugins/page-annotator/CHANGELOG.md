# Changelog

## [0.2.0] - 2026-07-24

### Changed

- **The overlay is now a Tampermonkey userscript, not an injected payload.**
  Claude no longer sends the overlay's source into the page; it sets one
  attribute (`<html data-claude-annotate="on">`) and reads the resulting DOM
  node back. The ~10.7 KB that used to be read and re-emitted on every first
  injection is gone from the conversation entirely.
  - New canonical script: `skills/annotate/assets/page-annotator.user.js`.
    The plugin owns its version; the script deliberately carries no
    `@updateURL`, so Tampermonkey never updates it behind the plugin's back.
  - The userscript stamps `<html data-claude-annotator="<version>">` at
    document-start. Claude probes that, compares it against the `@version` the
    plugin ships, and prompts for a reinstall when they diverge.
  - New `scripts/serve-userscript.js` serves the script over loopback so
    Tampermonkey's install page can pick it up, and fails loudly if the
    `@version` metadata and the `VERSION` constant drift apart.
  - Arming is now idempotent: re-arming an active overlay is a no-op instead
    of destroying saved annotations, and the post-fix refresh in Step 9 just
    re-arms rather than re-injecting.
  - Works on pages with a strict Content-Security-Policy, which injection
    could not: the userscript runs in Tampermonkey's sandbox, outside page
    CSP. The DOM-node channel already crossed JavaScript worlds, so the
    payload format is unchanged apart from the new `script` field.
- Payload schema is now `version: 2`, adding `script` (the installed
  userscript's version) so a stale browser copy is detectable from the data.
- `plugin.json` version corrected — it still read `0.1.0` after the 0.1.1
  release, while `marketplace.json` read `0.1.1`.

### Removed

- `skills/annotate/assets/overlay.js`, `overlay.min.js`, and
  `scripts/build-overlay.sh` — the minified build and its whitespace-collapsing
  pre-pass existed only to shrink the injection payload, and there is no
  injection path any more.
- The sessionStorage source cache, for the same reason.

### Requires

- [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey) in addition
  to the Claude in Chrome extension. The first run walks through installing
  the userscript; there is no injected fallback.

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
