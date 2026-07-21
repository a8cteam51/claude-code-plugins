# Changelog

## [0.1.0] - 2026-07-21

### Added

- Initial release.
- `annotate` skill: injects an annotation overlay into the current Chrome tab
  via the Claude in Chrome extension, polls for user annotations, and acts on
  them in `review` (default), `fix`, or `report` mode.
- Bundled dependency-free `overlay.js` (element picker, note panel, numbered
  pins, DOM-node state channel).
- Capture-time scrubbing of form values, URL query strings, and token-like
  strings, plus a scoped-read fallback for when the extension bridge's safety
  filter blocks the full-payload read.
- Overlay persists after Send for follow-up batches; cleanup is user-driven
  (refresh, close tab, or ✕) — the agent never removes it.
- Automatic post-fix refresh: after applying changes, Claude reloads the tab
  and re-injects the overlay so the annotation tool persists across rounds.
- `references/source-mapping.md`: annotation payload schema and DOM-to-source
  mapping strategies for common stacks (Tailwind, CSS modules, WordPress block
  themes, SPAs).
