# Visual refinement: compare original vs WordPress in the browser

After a section's block markup is written and validated, refine it against the original design in a real browser. Use the **Claude in Chrome** browser tools (`mcp__claude-in-chrome__*`, provided by the Claude in Chrome extension). If the tools are deferred in-session, load everything needed in **one** ToolSearch call — e.g. `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__browser_batch,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_close_mcp` — never one call per tool. There is no substitute for the extension: a screenshot of the WordPress side alone is not a comparison, and a view that was not compared in the harness is not finished.

## The comparison harness

Do not set a width by resizing the browser window. `resize_window` cannot go below 500px, cannot exceed the display, and can leave the window unchanged while reporting success. The plugin ships a harness page that loads the original and the WordPress page in iframes of an exact CSS width and height, and scales the stage to fit the window.

`serve-html.sh` serves it with the design files:

```bash
bash "<plugin-root>/scripts/serve-html.sh" --ensure --site-path "<site-path>" --dir "<design-dir>"
# H2BT_SERVE url=<base-url> pid=<pid> state=<site-path>/.h2bt/serve.json … reused=<yes|no>
# H2BT_HARNESS url=<base-url>_h2bt/viewport.html site_copy=<site-path>/_h2bt/viewport.html sink=<dir>
```

- **The server's address is in `<site-path>/.h2bt/serve.json`** (`url`, `harness`, `sink`), not in anyone's memory. `--ensure` reuses the server when it still answers and starts a new one, on a new port, when it has died: run it whenever the original stops loading, and read the file again. `--dir` is only needed before the run has a `run.json`: after a `--stop`, which removes `serve.json`, `--ensure` takes the directory from the run's `design_dir`. A start that cannot be made ends with `H2BT_SERVE_FAIL reason=<why>`.
- `--site-path` places a copy of the harness in the site, at `<site-path>/_h2bt/viewport.html`, which the site serves at `<site-url>/_h2bt/viewport.html`. A page on the other origin is reached through that copy, which relays requests to the page it frames. `--stop --site-path <site-path>` stops the server and removes the copy; it is outside `wp-content`, so never inside a project repository.
- **Everything is loopback-only.** The harness does nothing unless it is served from `localhost`, `127.0.0.1`, `[::1]` or a `*.localhost` name, frames only such addresses, and its relay answers only a loopback origin. Address the Studio site by its `localhost:<port>` URL.

Open one tab on the harness:

```
<base-url>_h2bt/viewport.html?a=<original-path>&b=<wordpress-url>&w=<width>&h=<height>
```

- `a` is the design file's path on the design server, as it is in the design directory (`about.html`, `about/index.html`), and `b` is the WordPress page's full address on the site's `localhost` URL. A path is read from the server's root, with or without a leading slash.

- `a` and `b` sit side by side as panes 0 and 1, at the same width. `&strip=<n>` shows each page as n consecutive screenfuls, so one capture covers a whole page. `&scale=<n>` sets the stage scale; `&y=<px>` the starting scroll.
- Drive it with `javascript_tool` through `window.h2bt`:

| Call | What it does |
|---|---|
| `await h2bt.ready()` | Resolves when every pane has loaded, with each document's size and the HTTP `status` of its address. A pane that says `404` has a wrong address, unless the view is the not-found page: it loads like any page, and comparing against it compares nothing. Rejects after 30 seconds (`&wait=<seconds>`) when a pane never finishes loading: reload, and if it repeats load each page on its own. |
| `await h2bt.prepare()` | Loads lazy images, switches transitions off, waits for fonts and images in every pane. Reports each pane's pending images and whether the browser prefers a dark scheme. Call it before measuring. |
| `await h2bt.scroll( y )` | Scrolls every pane together. |
| `await h2bt.run( index, source )` | Evaluates a function body with `( doc, win )` in one pane and resolves with its JSON-safe result. |
| `await h2bt.resize( width[, height] )` | Sets every pane to a new CSS width (and height) without a reload. |
| `await h2bt.pages()` | Each pane's width, document height and sideways overflow, with the elements that reach past the edge. |
| `await h2bt.compareText( options )` | Pairs the text of panes 0 and 1 and returns only the differences, text that only one pane has included (§ Compare text, not elements). |
| `await h2bt.sweep( widths, task[, height] )` | Resizes to each width in turn and runs a task (§ Sweep widths in one call). |
| `await h2bt.sink( name, data )` | Writes `data` to `<sink-dir>/<name>.json` on disk, also when the harness was loaded from the WordPress origin. Rejects when nothing stored it. |

**Keep results small, and send large ones to the sink.** `javascript_tool` cuts a result at about 1,000 characters, and withholds one that looks like `key=value` pairs or holds markup or addresses. Return short JSON: counts, keys that differ, a summed difference. Send anything longer with `h2bt.sink()` and read the file with a script that prints only the differences.

What the harness cannot show:

- An iframe does not emulate touch or `hover: none`.
- The extension's hover does not reach a cross-origin pane. To test `:hover` on the WordPress page, load the harness from the WordPress origin (`<site-url>/_h2bt/viewport.html?a=<wordpress-path>&b=<original-url>`), so that page is the same-origin pane.
- A tab that reports `visibilityState: hidden` stalls scroll timelines, smooth scrolling and transitions, loads no lazy image, and moves no focus on a key press. `prepare()` and `resize()` work around the first three; a screenshot forces a frame.

## Session setup

1. Call `tabs_context_mcp` once before any other browser tool — it returns the tab group and valid tab ids. Never reuse tab ids from an earlier session.
2. Create **one tab** for the harness with `tabs_create_mcp` and `navigate` it to the harness URL. Open a second tab on a page directly only when something needs real interaction with it.
3. Run `await h2bt.ready()` and `await h2bt.prepare()` before the first measurement, and `prepare()` again after any reload.
4. This drives the user's **real Chrome** — tabs are visible on their screen, and the extension needs site permission for `127.0.0.1`/`localhost`. Close the tabs with `tabs_close_mcp` when the view's refinement is done; don't leave strays behind.

## The two URLs

- **Original** — the design file served locally by `serve-html.sh`: `<base-url>` followed by the file's path in the design directory (`about.html`, `about/index.html`). (Serving, not `file://`, so relative CSS/JS/assets resolve.)
- **WordPress output** — the site's `localhost` address (`site.url` in `run.json`) plus the path for this view's target: the front page, a template's representative URL, or the page slug for shared-wrapper content.

## Widths and heights to check

The run's widths are in `<site-path>/.h2bt/run.json` (`widths`, `narrowest`): the orchestrator settles them once, from the design's media queries, so that every view is swept at the same ones. They follow these rules. A sensible default set if the design gives no signal: desktop `1440×900`, tablet `768×1024`, mobile `390×844`.

- **One pixel either side of every breakpoint.** Where a `max-width` rule and a `min-width` rule overlap at exactly one width, a measurement taken at that width describes that width only.
- **The narrowest width the design must hold** (320px unless the design says otherwise), for sideways overflow. A closed hover card or menu that is still laid out widens a narrow page.
- **`1900px`, on every view, whatever breakpoints the design declares.** Designs are usually authored narrower, so this is where unconstrained containers, stretched images, and full-bleed backgrounds that should stop at a max-width break. It is a sanity pass, not a pixel-match target: fix anything that visibly breaks; don't chase 1:1 fidelity at a width the design never specified.
- **More than one height** for a view whose first block is at least a screen tall, including one shorter than its content.

### Sweep widths in one call

```js
// The same function body in every pane: only the widths where the panes disagree come back.
await h2bt.sweep( [ 1440, 1024, 1023, 768, 767, 390, 320 ], 'return doc.documentElement.scrollHeight;' );

// Or any task per width.
await h2bt.sweep( [ 1440, 390 ], async () => ( { pages: await h2bt.pages(), text: ( await h2bt.compareText() ).diffs.length } ) );
```

Thirty widths fit in a call or two. `resize()` uses no timer and no animation frame, which a hidden tab throttles: it reads a box to force layout.

## The loop (per section, converge fast)

1. **Capture both.** A screenshot of the harness tab (`computer` with `action: "screenshot"`) shows both panes at the same width and scroll. Captures are viewport-sized: use `h2bt.scroll( y )` to bring the section into both panes, or `&strip=<n>` to see a whole page at once.
2. **Compare.** Look at the rendered pair side by side. For the section under work, check: overall layout and order, spacing rhythm, type scale, colour, alignment, and image sizing/cropping.
   - **Look closer before calling it a match.** The stage is scaled to fit the window, and the bar above it shows the scale: two desktop panes come out at a little over half size, a strip at less. A capture at that size hides a font weight, a letter spacing, a corner radius, and an icon a pixel or two off its line. Capture the same region of each pane with `computer` `action: "zoom"`; its `region` is in the screenshot's coordinates.
   - Where the zoomed capture is no sharper (a display with one device pixel per CSS pixel), set `&scale=1` and scroll the harness page sideways to the second pane.
3. **Measure where the eye is unsure,** and at every width the eye will not see: `h2bt.pages()` for document height and overflow, `h2bt.compareText()` for text position and type, `h2bt.run()` for a computed style or a box.
4. **Fix at the right ladder rung.** Adjust block supports/`theme.json` first; reach for a block style variation next; custom behaviour (`custom-blocks-guide.md`) only for behaviour; documented custom CSS last.
5. **Reload and reassess.** Reload the harness tab after a change so you're not comparing against a stale render. Stop when the section is within tolerance (no perceptible difference at normal zoom) **or** after ~3 rounds with diminishing returns. Do not loop indefinitely — record the residual difference and its reason in the drift list, then move on.

## Measuring

### Compare text, not elements

Two pages that share no markup still share their text. `h2bt.compareText()` walks the text nodes of each pane in order, groups them by their nearest ancestor that is not inline, and pairs the groups one to one whatever the wrappers are. For each pair it compares the text, the type (size, weight, colour, line height, underline), a list item's marker, and where the ink starts and ends (`y`, the top of the first line; `x`, the right edge of the last, which moves when a line breaks differently).

```js
const result = await h2bt.compareText( { a: 'main', b: 'main', tolerance: 0.5 } );
await h2bt.sink( 'about-1440-text', result );
( { groups: result.groups, differing: result.diffs.length } );
```

- `a` and `b` (or `root` for both) are selectors of the region to compare. `boxes: true` also compares each group's block box; `types: false` skips the type.
- **Text that only one page has is a difference.** When the panes have different numbers of groups, `unpaired` gives the side and the count, and the first five such groups are in `diffs` with `only: "a"` or `"b"`. A page that ends early, or carries an extra block, therefore never compares as equal. Pairing is by order, so one missing group early on also shifts every pair after it: fix the first difference and compare again.
- **Text that one page splits into two blocks shifts every later pair as well.** A heading that the original breaks with a `display: block` span is two groups there and one group, with a line break, in the build. Compare such a page section by section, with `a` and `b` set to each section's selector, and compare the split element by the box of its text.
- Typographic quotes and dashes are treated as their plain forms, because WordPress texturises content.
- An emoji is compared by the `alt` of WordPress's replacement image. A mirror with its scripts removed shows the character where the live page and the build show the image, so the live page is the reference for that character.
- The ink matters for small labels. A block with a small font on a taller line centres its text; the same text as an inline element in a parent with a larger font hangs from the parent's baseline. The offset is under a pixel, which a box comparison never sees.

### Other measurements that paid off

- **Undo the intended differences for the test.** Inject the original's rules into the build's pane as a style sheet and expect the build to equal the original everywhere. What is left is real drift, and switching one injected rule at a time gives the size of each intended difference.
- **Reduce inside the page.** Collect every block's tag, top, height, left and width in both panes, then return a count and a summed height difference per tag.
- **Pair elements by order when both pages render the same stored HTML,** and count positions from an anchor (inside the content from its first element, below it from its end). One height difference is then reported once, not in every row after it.
- **A single template that repeats an archive's row** is diffed against it: cut the shared stretch out of both files and expect the known lines only.
- **A long pagination can be checked without the data.** Put the original's run of page links into the build's numbers container, in the markup core prints, and sweep.
- **A state the sample data lacks** is rendered with a temporary filter (`custom-blocks-guide.md` § Test groundwork).
- **Which font file draws which weight** is measured here too (`theme-json-guide.md` § Font faces).

## Traps that are not drift

- **A page too short to scroll has no scrollbar,** so centred content sits half a scrollbar width away from the same content on a page that scrolls.
- **Scroll-driven animations** make a first-screen capture depend on scroll state. Compare with reduced motion first, then check the motion on its own.
- **Transitions do not advance in a hidden tab.** After a resize across a media-query boundary, any property under a transition (`transition: all` is enough) still reads its old value. `resize()` and `prepare()` switch transitions off. An original whose transition is declared `!important` beats that: add a rule with the original's own selector plus one class, then read.
- **Lazy loading is decided per page.** The same part's image can be lazy on one view and eager on another. In a hidden tab the lazy copy never loads and takes its box from rounded attributes, which reads as a 1px drift of a shared part on one view only. `prepare()` sets lazy images to eager in both panes.
- **An image inside a closed card** (`visibility: hidden`) reports a `naturalWidth` of 0 in a hidden tab until it is painted, although it has loaded: wait on `complete`. `img.decode()` on such an image may never settle; do not await it.
- **The measuring browser's colour scheme changes what an original shows** when its CSS has `prefers-color-scheme` rules, even a force-light guard with slightly different colours. `prepare()` reports the scheme. To read the other one, delete the matching media rules through CSSOM in the same-origin pane.
- **A container that is a flow root** (`core/post-content`) holds its last child's margin where a plain block lets it collapse out, so container heights differ while nothing visible does. Compare what follows a box before trusting its height.
- **Equal bounding boxes do not prove a rotation:** plus and minus the same angle give the same box. Compare the computed `rotate` too.
- **In-page links.** A scripted check selects links whose `href` starts with `#`. Selecting on "contains #" also clicks external links that carry fragments, and the pane navigates away.
- **Every value an analyzer reports is derived from stylesheets, not measured.** Measure on the rendered page before a value goes into the blueprint or the theme.
- **Loading an editor stores a post.** Opening the Site Editor, or the block editor that the validator loads, can leave an empty `wp_global_styles` post for the active theme though nothing was saved. A builder looks at the front end only. The orchestrator lists such posts and removes the ones the run made (`SKILL.md`, Phase 1 step 7).

## Checks to run before the final validation

Each of these can require a markup change, so they belong before the last validator call, not after it:

- **Sideways overflow at the narrowest width:** `h2bt.pages()` lists the elements whose right edge passes the viewport, not just a number. Fixing overflow has two follow-ons to report: with site-wide scrollbar styling every scrolling block grows by the scrollbar's height, and once a wide block is contained an unbreakable word may still widen a phone page.
- **Seams:** look at every join between two dark full-width blocks over a light page at a fractional stage scale (`&scale=0.83`). A light hairline means the 1px overlap is missing (`mapping-guide.md` § Layout traps).
- **Loading state:** an image that points at a theme file reserves no space. To measure what moves while one loads, point a clone of the image at a loopback port that accepts connections and never answers.
- **The first screen's largest image:** read its `loading` attribute (`standards.md`).
- **Focus:** key presses do not move focus in a hidden tab, so `:focus-visible` cannot be observed there. What can be checked statically: list every rule whose selector contains `:focus`, strip the pseudo-class and test the element with `matches()`. No match means the browser's default ring, which follows the element's corner radius.

## Convergence policy

- **Tolerance:** minor sub-pixel/anti-aliasing differences are acceptable and expected — they are not drift. Drift is a visible difference in layout, spacing, colour, or type.
- **Ceiling:** ~3 refine rounds per section. If still off after that, the detail is probably blocked at a higher ladder rung than is worth paying for — record it (what differs, which rung would fix it, why it was not taken) rather than escalating endlessly.
- **Whole-file pass:** after all sections, sweep the view's widths for document height, overflow and text, then walk each page top to bottom at desktop and phone width (`&strip=<n>`, or `h2bt.scroll()` a screenful at a time) to catch what numbers do not show.

## What to record

For each file, the drift list captures: the section, the unresolved difference, the viewport(s) it appears at, the ladder rung that would close it, and why it was left (cost, JS dropped, unsupported layout). This feeds the final report so the user sees exactly where and why the output is not 1:1.

## JS-driven sections

For interactivity (menus, accordions, carousels), drive the state before comparing, so you are comparing equivalent states, not the original's open menu against WordPress's closed one. In the harness, drive it in each pane with `h2bt.run( index, … )` (a `click()` on the toggle). For real pointer interaction, open the page in its own tab and use `computer` `left_click` (screenshot first to find the coordinates, or click by `ref` from `read_page`). Avoid clicking anything that opens a JS `alert`/`confirm` dialog — it blocks the extension. If a block's view script doesn't behave, check `read_console_messages` for script errors before guessing. Reproduce the behaviour per `custom-blocks-guide.md`.
