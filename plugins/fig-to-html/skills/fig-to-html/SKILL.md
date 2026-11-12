---
name: fig-to-html
description: This skill should be used when the user asks to "convert this .fig to HTML", "build HTML from this Figma file", "turn these Figma frames into a page", "read this .fig", "make the design directory from the Figma export", or otherwise supplies a Figma `.fig` export (or a folder it was unzipped into) and wants one or more of its frames as responsive vanilla HTML/CSS/JS. Works from the file alone, with no Figma app, account or API, and takes 1:1 PNG exports of the frames as the picture to match. Also use it to read a `.fig` for its designer notes, tokens or assets without converting anything. The result is a design directory that html-to-block-theme can build from.
argument-hint: "<file.fig | unzipped folder> [frame names] [--images <folder of 1:1 PNG exports>] [--out <dir>]"
---

# Convert frames of a Figma `.fig` export to HTML

Read a Figma `.fig` export directly, and write the frames the user names as responsive vanilla HTML, CSS and JavaScript. The file supplies structure, text, tokens, images, vectors and the designer's notes. It holds no picture of a frame, so the user supplies 1:1 PNG exports, and those are what the result is checked against.

The bundled reader, `${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs`, does all the reading. Do not parse the file by hand.

## Inputs

- **The Figma file** (required): a `.fig`, or a folder it was unzipped into.
- **Which frames to convert**: page or frame names, or a part of a page.
- **1:1 PNG exports** of those frames (required to convert, not to read): a folder the user fills by exporting each frame from Figma at 1x. A desktop export for every page; a mobile export wherever the design has a mobile frame.
- **What the file does not hold**: Figma comments, a brief, behaviour agreed with the designer or client.
- **Output directory**: default `./fig-to-html/<file name>/`.

Whatever the request leaves out of these is asked for, not guessed: steps 1 and 2.

Needs Node 22.15 or later, and `unzip` when given a `.fig` rather than a folder.

## What the reader writes

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" pages   <fig>
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" frames  <fig> --page "<part of a page name>"
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" find    <fig> "<part of a frame name>"
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" extract <fig> --node <id> --out <folder>
```

`extract` writes, for one node:

| File | Holds |
| --- | --- |
| `outline.txt` | The node's tree, one line per layer: names, sizes and text. Read this first. |
| `layers.txt` | The same tree with each layer's values on its line: position, layout, sizing, fills, strokes, radius, shadows, type. This is what a page is built from. |
| `node.json` | Everything in `layers.txt` in full, plus layer ids and the variable bound to each value. Every component instance is replaced by its contents with overrides applied, and hidden layers are left out. A large tree is split into `sections/NN-<name>.json`, listed in `node.json`. Open it for a detail `layers.txt` does not carry. |
| `tokens.json` | The variables and styles this node uses, with values, and each variable's value per mode when it has several. A text style whose size is a variable lists that size per mode under `modes`. |
| `assets/`, `assets.json` | The images this node draws, named and given their extension, and vector artwork as SVG. `assets.json` says where each is drawn and at what size. |
| `notes.md` | The designer's annotations, component descriptions and the text around the design. |

Fields of a node, in `node.json` and on its line in `layers.txt`:

- `x`, `y`, `w`, `h`: its box, relative to its parent, in the frame's pixels. `flip` (`horizontal`, `vertical`) and `rotation` say the layer is drawn mirrored or turned inside that box.
- `layout`: auto layout. `direction` (`row`, `column`, `grid`), `gap`, `padding` as `[top, right, bottom, left]`, `justify` (main axis), `align` (cross axis), `wrap`.
- `sizing`: `fixed`, `hug` (its content sets it) or `fill` (its parent sets it), per axis. Absent means fixed on both. This is the best evidence of how a layer should respond.
- `absolute`: taken out of its parent's auto layout. `constraints`: how it is pinned in a parent with no auto layout.
- `fills`, `stroke`, `radius`, `effects`, `opacity`, `blend`, `clip`, `mask`.
- `text`: `characters`, `font`, `size`, `lineHeight`, `letterSpacing`, `align`, `style` (the text style's name), `link`, and `runs` where part of the text is styled differently. `size` is the size the frame draws the text at, which in a frame set to a mobile mode is the mobile size. `lines` is how many lines it takes in the frame. `lineHeight` is a multiple of the size, a pixel value, or `auto` (the font's own). A newline in `characters` (`⏎` in `layers.txt`) is a line the designer broke by hand.
- `token` on a fill and `tokens` on a node: the variable bound to that value.
- `svg`: this layer and everything in it was written as one SVG file. `svgBox` is that drawing's box relative to the layer when it overflows it.
- `component`: the component an instance came from. The same name in several places is one thing used several times.
- `designerNote`: the layer is a note to the developer. Do not build it.

Two of these are read from the data rather than documented by Figma, so trust the PNG where they disagree: `sizing` on a layer with no explicit setting, and `justify: space-between`.

Figma rounds a line of text to whole pixels and a browser does not, so a tall page drifts from its export by a few pixels. That is not a fault to chase.

## Workflow

### 1. Ask what to convert

Start here, before reading the file. Take each answer below from the request where it gives one, and ask for all the rest together, in one message. Ask nothing the request already answers, and do not fill a gap with a guess.

1. **Which file?** The path of the `.fig`, or of the folder it was unzipped into.
2. **What is to be converted?** Whole pages or one part of a page (a header, a hero, a card), and their names as the user knows them. Everything on the file's hand-off page is a fine answer, and so is "I don't know what it's called": step 2 finds the hand-off page and lists what it holds.
3. **Where are the 1:1 PNG exports?** A folder path. If nothing is exported yet, say that step 2 will name the exact frames to export and their sizes, and carry on to it.
4. **What has the designer or client said that is not in the file?** A `.fig` holds annotations but not Figma's comment threads, and nothing agreed in a call or a brief. Ask the user to paste it or point at a file. "Nothing" is a fine answer.
5. **What is the HTML for?** A block theme built with html-to-block-theme, or pages used as they are. This settles where the output goes and what the report hands over.

### 2. Find the frames and confirm them

Run `pages`. A designer's file is mostly working pages: explorations, old versions, presentations. What is to be built is normally gathered on one hand-off page, named something like "Ready for dev", "Dev handoff" or "Dev hand off", often with a status emoji. Look for that page first and work from it. With no such page, or more than one, which page to use is the first question of this round.

Run `frames` on the hand-off page and sort what it holds:

- **Designs**: frames or components as tall as a page, at a desktop width (about 1280 to 1920) or a mobile one (about 360 to 430). A design drawn at two widths is two nodes with the same or nearly the same name. A design is sometimes a component shown inside another frame: `frames` prints `shows component <id>` under that frame, and the component is what to extract.
- **Style guides**: frames named for what they document, such as Style Guide, Typography, Color, Spacing, Components. These are not pages to build. They are the reference the pages are inferred from (step 4), and need no PNG export.
- **Theme assets**: a site icon, a social share image, a theme thumbnail. Not built here; named in `designer-notes.md` for the builder.
- **Components**: buttons, links, cards and headers drawn once with their variants, often inside a dashed purple outline. The designs use them, and the variants hold what a page frame cannot show: hover and pressed states, the mobile form. Extract the ones the designs use (step 4). A layer's `component` in the design names its component; `find` locates it.
- **Everything else**: presentation slides, covers, loose groups. Leave it out.

A mobile frame often carries a phone status bar as its first layer. Leave it out of the build, and allow for its height when comparing with the export.

`find` searches every page by name, for something the user named that is not on the hand-off page.

Then put the second round of questions, together, and with `AskUserQuestion` where the answer is a choice among candidates. Show each candidate with its id, page and size.

1. **Which of these nodes?** One question per thing the user named in step 1, listing the nodes that match it. Skip it where exactly one node matches. Where the user asked for everything on the hand-off page, show the sorted list and have it confirmed.
2. **Which mobile frame pairs with which desktop frame?** Propose the pairs by name and have them confirmed. Skip it where each desktop frame has exactly one node of the same name at a narrow width.
3. **For a page with no mobile frame:** design the narrow layout from the desktop frame, or leave that page desktop only?
4. **Exports still to make.** For every confirmed node with no PNG yet, give its name, page and exact pixel size, and ask the user to export it at 1x into the folder and say when it is there.

End the round by stating the plan in a few lines: the nodes, the export each is checked against, the style guides that will be read, and the output directory. Go on without asking for a go-ahead unless one of the questions above is still open.

### 3. Match the PNG exports

List the image folder. Pair each PNG with a node by file name, and confirm by size: a 1:1 export has the node's width and height in pixels (`sips -g pixelWidth -g pixelHeight <file>` on macOS). An export at another scale, or one with no node, is a question for the user. A page with no desktop export cannot be converted: say so and stop for that page.

### 4. Extract

Extract the style guides first, each into `<out>/extract/style-guide-<name>/`, and read them before any page: `outline.txt` for what the designer wrote down (type scale, content widths, spacing steps), `tokens.json` for the values, `notes.md` for annotations. A style guide is often generated documentation, so most of what it says is in its text, and its annotations often carry the brief for hover and motion.

Then extract each design into `<out>/extract/<page>-<width>/`. Read `outline.txt`, then `notes.md`, then `tokens.json`, then `layers.txt`, which for a long page is the bulk of the reading. Read the mobile frame's files as fully as the desktop frame's: its sizes, spacing and order are the other half of the brief.

Then extract each component the designs use that has variants, into `<out>/extract/component-<name>/`, for its hover state and its notes.

Look at each PNG export beside its outline before writing anything. A long export is easier to see cut into screen-sized pieces.

Check `instancesUnresolved` and `missingImages` in the summary `extract` prints. Either being non-zero means part of the design could not be read: tell the user which part.

### 5. Decide which assets are real

`assets/` holds only what the node draws, but a designer's file still carries filler. Look at every image in `assets.json` before using it:

- A flat colour, a plain gradient or a simple texture is CSS, not an image.
- A screenshot or stock picture standing in for content the client will supply is a placeholder: use it, and list it as a placeholder in `designer-notes.md`.
- Photographs, illustrations, logos and icons are content. Use the SVG for artwork that has one.
- An image far larger than it is drawn (compare `natural` with `drawn`) should be resized or flagged, not shipped as is.

Copy what is used into `<out>/source/assets/`. Leave the rest in `extract/`.

### 6. Write the page

One HTML file per page in `<out>/source/`, with shared CSS and JavaScript files beside it. Vanilla only: no framework, no build step, no CDN script.

- **The desktop frame is the source of truth.** Reproduce it exactly at its own width.
- **The mobile frame, when there is one, is the narrow end.** Reproduce it at its width. Between the two, and above the desktop width, make the decisions a careful front-end developer would: where columns stack, how type and spacing step down, what a row of cards does when it runs out of room. Variables and text styles with a desktop and a mobile mode in `tokens.json` give the two ends of a value, and the two frames give the rest: where a size, a gap, a padding or a radius differs between the frames, run it evenly from one to the other across the widths between (`clamp()`), and change layout at chosen widths.
- **With no mobile frame**, design the narrow layout from the desktop frame's structure, and say in the report that it was inferred.
- **The style guide settles what the frames leave open**: the widest the content gets, how type and spacing step down, hover, focus and pressed states, anything drawn at one width only. Where a style guide and a frame disagree, build the frame as drawn and record the disagreement in `designer-notes.md`.
- Shared layers are shared code: a header, footer, button or card that is one component in the file is one set of classes.
- Tokens become CSS custom properties on `:root`, named after the Figma variable. A value with no variable stays a literal.
- Use semantic HTML. The file gives a layer's look, not its role: decide headings, navigation, lists, buttons and links from what the layer is for.
- Text is the file's text, character for character. A line broken by hand in both frames is a `<br>`. One broken in a single frame is usually a fix for that width: get the same break from a width or from balanced wrapping where that is cheap, leave it out where it is not, and say which in `designer-notes.md`.
- A layer with a `component` that has a hover variant gets that hover. A link or button with no hover drawn gets a plain one, listed as inferred.
- Fonts are named in the file but not included. Load a font that is freely available; for one that is not, use the closest available fallback and list it in the report.
- **Use the designer's notes.** An annotation that describes behaviour (a marquee that loops, a slider that drags, a hover effect) is part of the brief: build it, in plain JavaScript where it needs script. An annotation that cannot be acted on from the file alone goes into `designer-notes.md` as an open item.

### 7. Check against the exports

Serve `<out>/source/` and open each page in a browser at the width of each PNG, with reduced motion set so that anything that loops is at rest. Two checks, both needed:

- **Measure.** Read each section's top and height from the page (`getBoundingClientRect`) and set them beside the same layers' `y` and `h` in `layers.txt`. A section more than a few pixels out has a wrong gap, padding or line count inside it: find it before looking at pictures.
- **Look.** Screenshot the full page and put it beside the export, a screen-sized piece at a time: position, size, colour, type, wrapping, artwork. A cloud, wave or other divider that looks wrong is often mirrored (`flip`) or a different piece of artwork from the one it resembles.

A headless browser may not lay out narrower than about 500px. For a mobile width, load the page in an iframe of that width and screenshot the iframe.

Fix what differs and check again. Then check the widths between the two frames, and one wider than the desktop frame: the document must be no wider than the window at any of them, nothing may overlap, and every menu item must fit beside the logo wherever the full menu shows. Exercise what was built from a note: click it, and confirm the state changed.

A difference that cannot or should not be removed goes in the report with its size and its reason: a font that is not available, a font set slightly wider or narrower than in Figma, a line break left out, a marquee caught at another point in its travel.

### 8. Write the notes for the builder

Write `<out>/designer-notes.md`: one file for the whole set of pages, for whoever builds the WordPress theme. Take it from each extract's `notes.md`, in the designer's own words, grouped by page and section, with duplicates merged. Then add, under separate headings:

- what was built from a note, and how;
- open items: notes that need a decision, content the client must supply, placeholders, fonts that were substituted;
- what was inferred with no frame to go on, and what was taken from a style guide;
- the theme assets on the hand-off page (site icon, share image, thumbnail), each with its node id.

State once that Figma comment threads are not in a `.fig` export.

## Output

```text
<out>/
├── source/                 the design directory: *.html, css, js, assets/
├── designer-notes.md       for the WordPress builder
└── extract/                what the reader wrote, per frame
```

`<out>/source/` is a design directory for the html-to-block-theme skill. That skill reads `DESIGN.md`, `decisions.md` and `views.md` beside the design directory; it does not yet read `designer-notes.md`, so name that file when handing the directory over.

## Report

Tell the user which pages were converted and where they are, how each compares with its export, what was inferred, which fonts were substituted, and the open items from the notes.
