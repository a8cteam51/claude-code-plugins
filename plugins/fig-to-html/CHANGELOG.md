# Changelog

## [0.2.0] - 2026-11-12

The output is now the handoff package `sp-site-design-harness` writes, so that `html-to-block-theme` builds from either. The homepage converted for 0.1.0 was moved into the new layout and re-measured at both widths with no change, and it passes the package checks. `html-to-block-theme`'s `group-designs.py` reads it. No theme has been built from it.

### Changed
- **Output layout.** `<out>/handoff/` holds `DESIGN.md`, `decisions.md`, `views.md` and `source/`; `<out>/extract/` holds the reader's output. `designer-notes.md` is gone: the designer's notes are a section of `decisions.md`, quoted as before.
- **`source/`** follows the harness's rules: `home.html` for the homepage and `<slug>.html` per page, `<view>--<state>.html` for a second state, one `assets/site.css` and one `assets/site.js`, font files and their licences in `assets/fonts/` with nothing loaded from another host, the header and footer identical in every file, a `#` for any link with no file or address, and nothing labelled as placeholder on the page.
- **A run can add to a package** an earlier run made.

### Added
- `references/handoff-package.md`: the specification of every file in the package, and the checks it must pass before it is handed over.
- `DESIGN.md` in the harness's schema, with tokens under their Figma names and a value per mode; `views.md` with a sitemap that says which pages are not converted yet, and a content status listing every placeholder and `#` link.

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
