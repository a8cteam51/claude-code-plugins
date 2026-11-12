# Changelog

## [0.1.0] - 2026-11-12

### Added
- Initial release.
- `scripts/fig.mjs`: a zero-dependency reader for Figma `.fig` exports (Node
  22.15+). Lists pages and frames, and extracts one node as a JSON tree with
  component instances expanded and overrides applied (component properties in
  both stored forms, and slots), the images it draws, vector artwork as SVG,
  the variables and styles it uses with their value per mode, and the
  designer's annotations and notes. Text is reported at the size the frame
  draws it, so a frame set to a mobile mode reads with its mobile sizes.
- `fig-to-html` skill: converts named frames to responsive vanilla
  HTML/CSS/JS, with the desktop frame as the source of truth and the mobile
  frame as the narrow end, checked against 1:1 PNG exports, and writes
  `designer-notes.md` for the WordPress builder. Starts by asking what the
  request leaves out, works from the file's hand-off page, and reads its style
  guides as reference for the pages.
