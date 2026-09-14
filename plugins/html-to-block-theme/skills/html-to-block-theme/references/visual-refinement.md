# Visual refinement: compare original vs WordPress in the browser

After a section's block markup is written and validated, refine it against the original design in a real browser. Use the **Claude in Chrome** browser tools (`mcp__claude-in-chrome__*`, provided by the Claude in Chrome extension). If the tools are deferred in-session, load everything needed in **one** ToolSearch call — e.g. `select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__resize_window,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__read_page,mcp__claude-in-chrome__tabs_close_mcp` — never one call per tool. If the extension is unavailable, fall back to the Studio MCP `take_screenshot` tool for the WordPress side.

## Session setup

1. Call `tabs_context_mcp` once before any other browser tool — it returns the tab group and valid tab ids. Never reuse tab ids from an earlier session.
2. Create **two dedicated tabs** with `tabs_create_mcp`: one for the original, one for the WordPress output. Both tabs live in the same Chrome window, so a single `resize_window` call sets the viewport for both sides — matched widths for free.
3. Load each side with `navigate`, passing that tab's explicit `tabId`. Switch sides by addressing the other tab id — no re-navigation needed.
4. This drives the user's **real Chrome** — tabs are visible on their screen, and the extension needs site permission for `127.0.0.1`/`localhost` (both the served designs and the Studio site are local). Close both tabs with `tabs_close_mcp` when the file's refinement is done; don't leave strays behind.

## The two URLs

- **Original** — the design file served locally by `serve-html.sh`: `<base-url><file>.html`. (Serving, not `file://`, so relative CSS/JS/assets resolve.)
- **WordPress output** — the site's Local URL plus the path for this file's target: the front page, a template's representative URL, or the page slug for shared-wrapper content.

## Matched viewports

Read the design CSS media queries to learn its breakpoints; refine at each. A sensible default set if the design gives no signal: desktop `1440×900`, tablet `768×1024`, mobile `390×844`. Resize with `resize_window` before screenshotting; because both tabs share one window, both sides always render at the same width — which is the property that matters. (`resize_window` sets the window's outer size, so the page viewport is slightly smaller than the requested height — identical on both sides, so comparisons stay valid.)

**Wide-desktop sanity check:** every design also gets one pass at `1900px` browser width (e.g. `1900×1000`), regardless of the breakpoints it declares. Designs are usually authored narrower, so this is where unconstrained containers, stretched images, and full-bleed backgrounds that should stop at a max-width break. This is a sanity pass, not a pixel-match target — fix anything that visibly breaks; don't chase 1:1 fidelity at a width the design never specified. The window cannot be resized beyond the physical display: if `1900px` doesn't fit, go as wide as the display allows and spot-check the max-width behaviour of full-width sections with `getComputedStyle` via `javascript_tool` instead.

## The loop (per section, converge fast)

1. **Capture both.** Screenshots (`computer` with `action: "screenshot"`) capture the **visible viewport only** — there is no full-page capture. Scroll each tab so the section under work is in view (`computer` `scroll`, or `scroll_to` with an element ref from `read_page`) and screenshot both tabs with the section at the same position. Matching scroll position matters as much as matching width. Two capture gotchas: `loading="lazy"` images race the screenshot (large files render as empty boxes) — scrolling the section into view starts the load, so wait for `[...document.images].every(i => i.complete)` via `javascript_tool` before capturing; and re-assert the window size after any navigation before capturing — a silently reset viewport compares mismatched widths.
2. **Compare.** Look at the rendered pair side by side. For the section under work, check: overall layout and order, spacing rhythm, type scale, colour, alignment, and image sizing/cropping.
3. **Spot-check computed styles** where the eye is unsure. Use `javascript_tool` to read `getComputedStyle` on matching elements (padding, font-size, color, gap) and compare numbers rather than guessing. It has REPL semantics — the last expression is the result, e.g. `getComputedStyle(document.querySelector('.hero h1')).fontSize`.
4. **Fix at the right ladder rung.** Adjust block supports/`theme.json` first; reach for a block style variation next; a custom block only for behaviour; documented custom CSS last. Re-validate any changed markup.
5. **Re-capture and reassess.** Reload the WordPress tab (`navigate` to the same URL) after changes so you're not comparing against a stale render. Stop when the section is within tolerance (no perceptible difference at normal zoom) **or** after ~3 rounds with diminishing returns. Do not loop indefinitely — record the residual difference and its reason in the drift list, then move on.

## Convergence policy

- **Tolerance:** minor sub-pixel/anti-aliasing differences are acceptable and expected — they are not drift. Drift is a visible difference in layout, spacing, colour, or type.
- **Ceiling:** ~3 refine rounds per section. If still off after that, the detail is probably blocked at a higher ladder rung than is worth paying for — record it (what differs, which rung would fix it, why it was not taken) rather than escalating endlessly.
- **Whole-file pass:** after all sections, walk each page top to bottom per viewport — captures are viewport-sized, so step down a screenful at a time on both tabs in lockstep — to catch cumulative spacing drift between sections, plus the `1900px` wide-desktop sanity check on the WordPress output.

## What to record

For each file, the drift list captures: the section, the unresolved difference, the viewport(s) it appears at, the ladder rung that would close it, and why it was left (cost, JS dropped, unsupported layout). This feeds the final report so the user sees exactly where and why the output is not 1:1.

## JS-driven sections

For interactivity (menus, accordions, carousels), drive the state in the browser before comparing — click the toggle with `computer` `left_click` (screenshot first to find the coordinates, or click by `ref` from `read_page`), open the panel — so you are comparing equivalent states, not the original's open menu against WordPress's closed one. Avoid clicking anything that opens a JS `alert`/`confirm` dialog — it blocks the extension. If a custom block's `view.js` doesn't behave, check `read_console_messages` for script errors before guessing. Reproduce the behaviour per `custom-blocks-guide.md`.
