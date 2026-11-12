# fig-to-html

Convert frames of a Figma `.fig` export into responsive vanilla HTML, CSS and
JavaScript, working from the file alone: no Figma app, account or API.

Say to Claude:

> Convert the homepage in `~/Downloads/Client.fig` to HTML. The 1:1 exports are in `~/Downloads/client-exports`.

## What you supply

The skill starts by asking for whatever the request leaves out of these:

- The `.fig` file (Figma → File → Save local copy), or a folder it was unzipped into.
- What to convert. It looks first for the file's hand-off page ("Ready for
  dev", "Dev handoff" and the like), sorts that page into designs, style
  guides and theme assets, and has you confirm the list. Style guides are read
  as reference for the pages, not built.
- A folder of 1:1 PNG exports of the designs. The `.fig` holds no picture of a
  frame, so the exports are what the result is checked against. If none exist
  yet, it lists the frames to export and their pixel sizes.
- Anything the designer or client said outside the file, such as Figma comments.

## What you get

```text
<out>/
├── source/                 *.html, css, js, assets/
├── designer-notes.md       the designer's annotations and notes, for the WordPress builder
└── extract/                what was read from the file, per frame
```

`source/` is a design directory for the `html-to-block-theme` plugin.

The desktop frame is treated as the source of truth and the mobile frame, when
the design has one, as the narrow end. The widths between are decided by the
model.

## The reader on its own

`scripts/fig.mjs` has no dependencies and can be used without the skill:

```bash
node scripts/fig.mjs pages   Client.fig
node scripts/fig.mjs frames  Client.fig --page "Mockups"
node scripts/fig.mjs find    Client.fig "homepage"
node scripts/fig.mjs extract Client.fig --node 7311:4776 --out ./home-desktop
```

`extract` writes `node.json` (the tree as drawn, with component instances
expanded), `outline.txt`, `layers.txt` (the tree as text, one line per layer
with its values), `tokens.json`, `notes.md`, `assets.json` and `assets/`. Only
the images the node draws are copied out of the file.

## Limits

- The `.fig` format is undocumented and can change. The reader was written
  against format version 106 and tested on one production file, from which one
  page has been converted and checked against its exports at two widths.
- A component instance can read as complete while showing its component's
  default content. The check against the PNG export is what catches that.
- An image fill with a custom crop is reported as cropped, without the crop.
- Figma comment threads are stored on Figma's servers, not in the file.
- Fonts are named in the file but not included.
- Radial, angular and diamond gradients inside SVG artwork fall back to their
  first colour. Masks are reported on the layer, not applied.

## Requirements

Node.js 22.15 or later. `unzip` on `PATH` when reading a `.fig` directly.
