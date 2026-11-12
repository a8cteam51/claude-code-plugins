# Changelog

## [0.4.0] - 2026-11-12

The designer's annotations, logged by the reader as a file of the package. Until now they reached the build only as the section of `decisions.md` the converting agent wrote, so the build had no record to check that section against. Tried on a file with twelve extracted frames: 17 annotations on 28 layers, every one found in the log by the package check. For the eleven of those frames also extracted with 0.3.1, `notes.md`, `layers.txt` and `node.json` came out the same.

### Added
- **`annotations.md`** in the handoff package: every annotation in the frames that were extracted, each once and exactly as written, with its category and pinned properties, and every frame and layer it is on; then note layers, component and style descriptions, and a table of the frames read with how many annotations each has. A frame with none is still listed, so "no notes" can be told from "not read".
- **`fig.mjs annotations <folder of extracts> --out <file>`** writes it. It stops, naming the folders, when one was extracted before `notes.json` existed, so that the log is never silently short.
- **`notes.json`** beside each extract's `notes.md`: the same notes as data, with the id of the layer each annotation is on.
- `check-package.mjs` fails a package with no `annotations.md`, or one whose log lacks a frame or an annotation that is in `extract/`.

### Changed
- `decisions.md` § The designer's notes is unchanged: it still groups the notes by view and says what was done with each. The log is the complete record beside it.
- html-to-block-theme 0.11.1 reads the log when a package has one.

## [0.3.1] - 2026-11-12

Two places where 0.3.0 disagreed with html-to-block-theme's own standards.

### Fixed
- **The type-rendering baseline writes `text-wrap-style: pretty`**, not the `text-wrap` shorthand, with `balance` on headings where a browser has no `pretty`. The shorthand also sets `text-wrap-mode` and undid an inherited `nowrap` in one html-to-block-theme build. `check-package.mjs` fails a stylesheet that uses the shorthand.
- **No palette slug is `border`, `text` or `link`**: core already uses `has-border-color`, `has-text-color` and `has-link-color` as classes on blocks. `check-package.mjs` fails a `DESIGN.md` that has one.

## [0.3.0] - 2026-11-12

The team's standards, taken from `sp-site-design-harness` and cut down to what applies to converting a designer's file. Tried on the homepage converted for 0.1.0: the new checks found a focus outline that could not be seen on the footer, two rows that moved with no way to stop them, five kinds of target under 44px, a missing type-rendering baseline and a name that wrapped at 320px, all now fixed; and an open-menu frame and a 404 in the file that had been reported as missing. An independent reviewer then found three more differences from the exports, also fixed. The page is now 1px from its desktop export in height and 4px from its mobile one, and has no sideways scroll at ten widths from 320 to 1920.

### Added
- `references/standards.md`: what wins when the file and a standard disagree; the criteria the HTML must meet; the criteria the design is checked against, with what to fix unseen and what to report; the hand-off checklist the file is audited against; named team defaults for what the file leaves open; the type-rendering baseline; palette slot names; the widths to check; an independent look by a reviewer that did not build the page.
- `scripts/check-package.mjs`: checks a package's files, links, fonts, shared header and footer, documents, colours and contrast, baseline and page structure, and exits non-zero on a failure.
- `scripts/page-audit.js`: run in the page, returns sideways scroll, small and crowded targets, small text, tight lines, unlabelled fields and what moves.
- `decisions.md` § Standards: what was met, what was fixed without changing the look, what the design fails, what the file lacks, and which team defaults were used.

### Changed
- **Palette names.** A palette colour is `--color-<slug>`, with the team's `canvas`, `surface`, `ink` and `accent` for the colours that play those roles and a slug from the Figma name for the rest. `DESIGN.md` keys its colours by slug, records the Figma variables beside each, and lists the colour pairings the pages use so their contrast is computed.
- **A state or overlay the file draws is built from its frame.** Step 2 searches the whole file against the hand-off checklist before anything is called missing.
- **Adding pages to a package** re-measures the pages already in it.

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
