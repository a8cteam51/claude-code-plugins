---
name: fig-to-html
description: This skill should be used when the user asks to "convert this .fig to HTML", "build HTML from this Figma file", "turn these Figma frames into a page", "read this .fig", "make the handoff from the Figma export", or otherwise supplies a Figma `.fig` export (or a folder it was unzipped into) and wants one or more of its frames as responsive vanilla HTML/CSS/JS. Works from the file alone, with no Figma app, account or API, and takes 1:1 PNG exports of the frames as the picture to match. Also use it to read a `.fig` for its designer notes, tokens or assets without converting anything. The result is a handoff package (DESIGN.md, decisions.md, views.md and a source/ folder), the same one sp-site-design-harness writes, which html-to-block-theme builds from.
argument-hint: "<file.fig | unzipped folder> [frame names] [--images <folder of 1:1 PNG exports>] [--out <dir>]"
---

# Convert frames of a Figma `.fig` export to HTML

Read a Figma `.fig` export directly, and write the frames the user names as responsive vanilla HTML, CSS and JavaScript. The file supplies structure, text, tokens, images, vectors and the designer's notes. It holds no picture of a frame, so the user supplies 1:1 PNG exports, and those are what the result is checked against.

What comes out is a handoff package: the pages in `source/`, and beside them `DESIGN.md`, `decisions.md` and `views.md`. It is the same package `sp-site-design-harness` writes, so html-to-block-theme builds from either. One file is this plugin's own: `annotations.md`, the reader's log of every annotation in the frames it read, for the build to refer to. `references/handoff-package.md` is the specification of every file in it: read it before step 6.

Matching the designer's picture is half the job. The page must also meet the team's standards, and the file must be checked for what a hand-off should hold. `references/standards.md` has both, with what wins when the file and a standard disagree: read it before step 2.

The bundled reader, `${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs`, does all the reading. Do not parse the file by hand.

## Inputs

- **The Figma file** (required): a `.fig`, or a folder it was unzipped into.
- **Which frames to convert**: page or frame names, or a part of a page.
- **1:1 PNG exports** of those frames (required to convert, not to read): a folder the user fills by exporting each frame from Figma at 1x. A desktop export for every page; a mobile export wherever the design has a mobile frame.
- **What the file does not hold**: Figma comments, a brief, behaviour agreed with the designer or client.
- **Output directory**: default `./fig-to-html/<file name>/`. The package goes in its `handoff/` folder and the reader output in `extract/`. When `handoff/` already holds a package from an earlier run, this run adds to it.

Whatever the request leaves out of these is asked for, not guessed: steps 1 and 2.

Needs Node 22.15 or later, and `unzip` when given a `.fig` rather than a folder.

## What the reader writes

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" pages   <fig>
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" frames  <fig> --page "<part of a page name>"
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" find    <fig> "<part of a frame name>"
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" extract <fig> --node <id> --out <folder>
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" annotations <folder of extracts> --out <file>
```

`extract` writes, for one node:

| File | Holds |
| --- | --- |
| `outline.txt` | The node's tree, one line per layer: names, sizes and text. Read this first. |
| `layers.txt` | The same tree with each layer's values on its line: position, layout, sizing, fills, strokes, radius, shadows, type. This is what a page is built from. |
| `node.json` | Everything in `layers.txt` in full, plus layer ids and the variable bound to each value. Every component instance is replaced by its contents with overrides applied, and hidden layers are left out. A large tree is split into `sections/NN-<name>.json`, listed in `node.json`. Open it for a detail `layers.txt` does not carry. |
| `tokens.json` | The variables and styles this node uses, with values, and each variable's value per mode when it has several. A text style whose size is a variable lists that size per mode under `modes`. |
| `assets/`, `assets.json` | The images this node draws, named and given their extension, and vector artwork as SVG. `assets.json` says where each is drawn and at what size. |
| `notes.md`, `notes.json` | The designer's annotations, component descriptions and the text around the design: to read, and the same as data. |

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
5. **Is there a package from an earlier run to add to?** Its folder, when there is one. Look in the default output directory before asking.

### 2. Find the frames and confirm them

Run `pages`. A designer's file is mostly working pages: explorations, old versions, presentations. What is to be built is normally gathered on one hand-off page, named something like "Ready for dev", "Dev handoff" or "Dev hand off", often with a status emoji. Look for that page first and work from it. With no such page, or more than one, which page to use is the first question of this round.

Run `frames` on the hand-off page and sort what it holds:

- **Designs**: frames or components as tall as a page, at a desktop width (about 1280 to 1920) or a mobile one (about 360 to 430). A design drawn at two widths is two nodes with the same or nearly the same name. A design is sometimes a component shown inside another frame: `frames` prints `shows component <id>` under that frame, and the component is what to extract.
- **Style guides**: frames named for what they document, such as Style Guide, Typography, Color, Spacing, Components. These are not pages to build. They are the reference the pages are inferred from (step 4), and need no PNG export.
- **Theme assets**: a site icon, a social share image, a theme thumbnail. Not built here; named in `views.md` for the builder.
- **Components**: buttons, links, cards and headers drawn once with their variants, often inside a dashed purple outline. The designs use them, and the variants hold what a page frame cannot show: hover and pressed states, the mobile form. Extract the ones the designs use (step 4). A layer's `component` in the design names its component; `find` locates it.
- **States and overlays**: an open menu, a hover or focus state, an error message, a mini cart, drawn as a frame or as a component variant. They are designs of something a page frame shows only at rest. Extract the ones that belong to what is being converted (step 4).
- **Everything else**: presentation slides, covers, loose groups. Leave it out.

A mobile frame often carries a phone status bar as its first layer. Leave it out of the build, and allow for its height when comparing with the export.

`find` searches every page by name, for something the user named that is not on the hand-off page.

**Check the design is complete.** Go through `references/standards.md` § Is the design complete?, with `find` for each name it lists, over the whole file. Print the whole list of the hand-off page, not its first screen: a file was once reported as having no open-menu frame and no 404 when it had both further down. What the file holds is built from; what it lacks is reported in `decisions.md` § Standards and filled with a named team default, never with taste.

Then put the second round of questions, together, and with `AskUserQuestion` where the answer is a choice among candidates. Show each candidate with its id, page and size.

1. **Which of these nodes?** One question per thing the user named in step 1, listing the nodes that match it. Skip it where exactly one node matches. Where the user asked for everything on the hand-off page, show the sorted list and have it confirmed.
2. **Which mobile frame pairs with which desktop frame?** Propose the pairs by name and have them confirmed. Skip it where each desktop frame has exactly one node of the same name at a narrow width.
3. **For a page with no mobile frame:** design the narrow layout from the desktop frame, or leave that page desktop only?
4. **Exports still to make.** For every confirmed node with no PNG yet, give its name, page and exact pixel size, and ask the user to export it at 1x into the folder and say when it is there.

End the round by stating the plan in a few lines: the nodes, the file each becomes (`references/handoff-package.md` § File names), the export each is checked against, the style guides that will be read, and the output directory. Go on without asking for a go-ahead unless one of the questions above is still open.

### 3. Match the PNG exports

List the image folder. Pair each PNG with a node by file name, and confirm by size: a 1:1 export has the node's width and height in pixels (`sips -g pixelWidth -g pixelHeight <file>` on macOS). An export at another scale, or one with no node, is a question for the user. A page with no desktop export cannot be converted: say so and stop for that page.

### 4. Extract

Extract the style guides first, each into `<out>/extract/style-guide-<name>/`, and read them before any page: `outline.txt` for what the designer wrote down (type scale, content widths, spacing steps), `tokens.json` for the values, `notes.md` for annotations. A style guide is often generated documentation, so most of what it says is in its text, and its annotations often carry the brief for hover and motion.

Then extract each design into `<out>/extract/<page>-<width>/`. Read `outline.txt`, then `notes.md`, then `tokens.json`, then `layers.txt`, which for a long page is the bulk of the reading. Read the mobile frame's files as fully as the desktop frame's: its sizes, spacing and order are the other half of the brief.

Then extract each component the designs use that has variants, into `<out>/extract/component-<name>/`, for its hover state and its notes, and each state or overlay frame that belongs to the pages (the open menu, a focus state), into `<out>/extract/<name>/`.

Look at each PNG export beside its outline before writing anything. A long export is easier to see cut into screen-sized pieces.

Check `instancesUnresolved` and `missingImages` in the summary `extract` prints. Either being non-zero means part of the design could not be read: tell the user which part.

### 5. Decide which assets are real

`assets/` holds only what the node draws, but a designer's file still carries filler. Look at every image in `assets.json` before using it:

- A flat colour, a plain gradient or a simple texture is CSS, not an image.
- A screenshot or stock picture standing in for content the client will supply is a placeholder: use it, and list it in the content status (`views.md`). Never label it on the page.
- Photographs, illustrations, logos and icons are content. Use the SVG for artwork that has one.
- An image far larger than it is drawn (compare `natural` with `drawn`) should be resized or flagged, not shipped as is.

Copy what is used into `<out>/handoff/source/assets/`, under names that say what each is (`logo-salesforce.svg`, not `container-365f10f1.svg`): look at an image before naming it or writing its alt text, because layer names lie. Leave the rest in `extract/`.

### 6. Write the pages

Read `references/handoff-package.md` § `source/` first. It fixes the file names, the one stylesheet and one script, local fonts, the shared header and footer, and how links and placeholders are written. In short: one HTML file per view in `<out>/handoff/source/`, named for what it builds as (`home.html` for the homepage, `<slug>.html` for a page, `<view>--<state>.html` for a second state), all linking `assets/site.css`. Vanilla only: no framework, no build step, nothing loaded from another host.

When `<out>/handoff/source/` already holds pages, read its `site.css`, header and footer before writing: the new page uses them, and adds its own rules at the end of `site.css`.

- **The desktop frame is the source of truth.** Reproduce it exactly at its own width.
- **The mobile frame, when there is one, is the narrow end.** Reproduce it at its width. Between the two, and above the desktop width, make the decisions a careful front-end developer would: where columns stack, how type and spacing step down, what a row of cards does when it runs out of room. Variables and text styles with a desktop and a mobile mode in `tokens.json` give the two ends of a value, and the two frames give the rest: where a size, a gap, a padding or a radius differs between the frames, run it evenly from one to the other across the widths between (`clamp()`), and change layout at chosen widths.
- **With no mobile frame**, design the narrow layout from the desktop frame's structure, and say in the report that it was inferred.
- **The style guide settles what the frames leave open**: the widest the content gets, how type and spacing step down, hover, focus and pressed states, anything drawn at one width only. Where a style guide and a frame disagree, build the frame as drawn and record the disagreement in `decisions.md`.
- Shared layers are shared code: a header, footer, button or card that is one component in the file is one set of classes.
- Tokens become CSS custom properties on `:root`. A palette colour is `--color-<slug>`: the team's four slots (`canvas`, `surface`, `ink`, `accent`) for the colours that play those roles, and a slug from the Figma name for the rest, with the Figma variable in a comment beside each (`references/standards.md` § Token names). Every other token keeps its Figma name. A value with no variable stays a literal.
- **Meet the standards as the page is written**, not afterwards (`references/standards.md`): the Development criteria in the markup, the type-rendering baseline in `site.css`, a focus indicator on every background, a pause control beside anything that moves without end, targets of 44px.
- **Where the file breaks a Design criterion**, fix it if the fix cannot be seen, and otherwise build what was drawn and record the measured value for the designer. Never change a designer's colour, size or spacing silently.
- **Where the file is silent**, use the named team default and say that it is one. A state or overlay the file does draw is built from its frame.
- Use semantic HTML. The file gives a layer's look, not its role: decide headings, navigation, lists, buttons and links from what the layer is for.
- Text is the file's text, character for character. A line broken by hand in both frames is a `<br>`. One broken in a single frame is usually a fix for that width: get the same break from a width on the element, or from a `<br>` shown only at that frame's widths, and leave it out where it sits in content an editor will replace. Say which in `decisions.md`. Do not reach for balanced wrapping to get one break: it moves the others.
- A layer with a `component` that has a hover variant gets that hover. A link or button with no hover drawn gets a plain one, listed as inferred.
- Fonts are named in the file but not included. Put the font files in `assets/fonts/` with their licences and load them from there (`references/handoff-package.md` § Local fonts). A family that is not freely licensed needs the user's confirmation before it goes in.
- **Use the designer's notes.** An annotation that describes behaviour (a marquee that loops, a slider that drags, a hover effect) is part of the brief: build it, in plain JavaScript where it needs script. An annotation that cannot be acted on from the file alone goes into `decisions.md` as a deferral.

### 7. Check against the exports

Serve `<out>/handoff/source/` and open each page in a browser at the width of each PNG, with reduced motion set so that anything that loops is at rest. Four checks, all needed:

- **Measure.** Read each section's top and height from the page (`getBoundingClientRect`) and set them beside the same layers' `y` and `h` in `layers.txt`. A section more than a few pixels out has a wrong gap, padding or line count inside it: find it before looking at pictures.
- **Look.** Screenshot the full page and put it beside the export, a screen-sized piece at a time: position, size, colour, type, wrapping, artwork. A cloud, wave or other divider that looks wrong is often mirrored (`flip`) or a different piece of artwork from the one it resembles.
- **Audit.** Run `${CLAUDE_PLUGIN_ROOT}/scripts/page-audit.js` in the page, at the narrowest width, each frame width and the widest: give its text to the browser tool as the script to evaluate. It returns sideways scroll, small and crowded targets, small text, tight lines, unlabelled fields and what moves. Each item is fixed, or is a Design criterion the file fails and goes in `decisions.md` § Standards with its measured value.
- **Every width.** At each width in `references/standards.md` § Widths to check, the document is no wider than the window, nothing overlaps, and the header's controls stay on one line. Look at the narrowest one: a name or a button row that fits at the mobile frame's width can wrap below it.

A headless browser may not lay out narrower than about 500px. For a mobile width, load the page in an iframe of that width and screenshot the iframe.

Fix what differs and check again. Wherever the full menu shows, every item must fit beside the logo. Exercise what was built from a note or a state frame: click it, open it, and confirm the state changed.

**When the package already held pages**, measure each of them before changing `site.css` and again after: its height at each frame width must not have moved. A rule added for a new view that shifts an old one is a regression, not a refinement.

**Then have it looked at by someone who did not build it** (`references/standards.md` § An independent look): one subagent, given the exports and the screenshots side by side and the list of settled differences, asked only for what differs and what looks broken. Two rounds at most.

A difference that cannot or should not be removed goes in the report with its size and its reason: a font that is not available, a font set slightly wider or narrower than in Figma, a line break left out, a marquee caught at another point in its travel.

### 8. Write the documents

Write `DESIGN.md`, `views.md` and `decisions.md` in `<out>/handoff/`, each with the sections `references/handoff-package.md` gives it, in that order. Write `views.md` before `decisions.md`, which copies its content status in full.

- **`DESIGN.md`** is the rules: the tokens from `tokens.json` and the style guide in its frontmatter, per mode, under the Figma names `site.css` uses; then what each is for, in the designer's words where the file has them.
- **`views.md`** is the map: every destination the design links to, which have a file, what each file builds as, and the content status, which lists every placeholder and every `#` link.
- **`decisions.md`** is what the HTML cannot show: the designer's notes as written, each behaviour and how it was built, what the file designs that is not converted yet, and what is left for someone to decide.

The designer's notes come from each extract's `notes.md`, with what the user supplied in step 1. They are quoted, never paraphrased.

**Then write the log of annotations.** It is the one document the reader writes, not you:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/fig.mjs" annotations <out>/extract --out <out>/handoff/annotations.md
```

`annotations` reads every folder in `<out>/extract/` and lists each annotation once, exactly as the designer wrote it, with every frame and layer it is on, then the frames that were read. `decisions.md` groups the same notes by view and says what was done with each; `annotations.md` is the complete record the build checks that against. Never edit it by hand, and run the command again whenever a frame is extracted, so a later run's notes are added. A folder in `extract/` from before `notes.json` existed stops the command: extract that frame again.

When the package already has these documents, add to them: new rows in the Sitemap and Views, new entries in the content status, new notes under their view. Change an existing line only when this run made it untrue.

### 9. Check the package

Run the checker, and read every line it prints:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/check-package.mjs" <out>/handoff
```

It checks the files, links, fonts, shared header and footer, the three documents, the log of annotations against what was extracted, the colours and their contrast, the type-rendering baseline, and each page's structure. It exits non-zero on any failure. Then do the checks it cannot (`references/handoff-package.md` § Check the package). Fix what fails and run it again: a package with a failing check is not handed over.

## Output

```text
<out>/
├── handoff/
│   ├── DESIGN.md      rules, tokens, reasoning
│   ├── decisions.md   what the build must do that the HTML does not show, and the designer's notes
│   ├── annotations.md every annotation in the frames read, as the reader found it
│   ├── views.md       sitemap, each view, what it builds as, content status
│   └── source/        home.html, <slug>.html …, assets/site.css, assets/fonts/, assets/…
└── extract/           what the reader wrote, per frame
```

The next step is html-to-block-theme 0.10.0 or later, run on `<out>/handoff/source/`. It reads the three documents from `<out>/handoff/`, the folder above `source/`.

## Report

Tell the user which pages were converted and the file each became, how each compares with its export, what was inferred, which fonts were substituted, what the package still lacks, the open items, what the design fails that is the designer's to fix, what the file lacks against the hand-off checklist, and the result of the package check.
