# Visual refinement: compare original vs WordPress in the browser

After a section's block markup is written and validated, refine it against the original design in a real browser. Use the bundled **Playwright MCP** (confirm exact tool names in-session — the `@playwright/mcp` server exposes `browser_navigate`, `browser_resize`, `browser_take_screenshot`, `browser_snapshot`, and `browser_evaluate`). If Playwright is unavailable, fall back to the Studio MCP `take_screenshot` tool for the WordPress side.

## The two URLs

- **Original** — the design file served locally by `serve-html.sh`: `<base-url><file>.html`. (Serving, not `file://`, so relative CSS/JS/assets resolve.)
- **WordPress output** — the site's Local URL plus the path for this file's target: the front page, a template's representative URL, or the page slug for shared-wrapper content.

## Matched viewports

Read the design CSS media queries to learn its breakpoints; refine at each. A sensible default set if the design gives no signal: desktop `1440×900`, tablet `768×1024`, mobile `390×844`. Resize the browser to the **same** width on both sides before screenshotting — comparing different viewports is meaningless.

## The loop (per section, converge fast)

1. **Capture both.** Navigate to the original, resize, full-page screenshot; repeat for the WordPress output at the same size.
2. **Compare.** Look at the rendered pair side by side. For the section under work, check: overall layout and order, spacing rhythm, type scale, colour, alignment, and image sizing/cropping.
3. **Spot-check computed styles** where the eye is unsure. Use `browser_evaluate` to read `getComputedStyle` on matching elements (padding, font-size, color, gap) and compare numbers rather than guessing.
4. **Fix at the right ladder rung.** Adjust block supports/`theme.json` first; reach for a block style variation next; a custom block only for behaviour; documented custom CSS last. Re-validate any changed markup.
5. **Re-capture and reassess.** Stop when the section is within tolerance (no perceptible difference at normal zoom) **or** after ~3 rounds with diminishing returns. Do not loop indefinitely — record the residual difference and its reason in the drift list, then move on.

## Convergence policy

- **Tolerance:** minor sub-pixel/anti-aliasing differences are acceptable and expected — they are not drift. Drift is a visible difference in layout, spacing, colour, or type.
- **Ceiling:** ~3 refine rounds per section. If still off after that, the detail is probably blocked at a higher ladder rung than is worth paying for — record it (what differs, which rung would fix it, why it was not taken) rather than escalating endlessly.
- **Whole-file pass:** after all sections, do one full-page comparison per viewport to catch cumulative spacing drift between sections.

## What to record

For each file, the drift list captures: the section, the unresolved difference, the viewport(s) it appears at, the ladder rung that would close it, and why it was left (cost, JS dropped, unsupported layout). This feeds the final report so the user sees exactly where and why the output is not 1:1.

## JS-driven sections

For interactivity (menus, accordions, carousels), drive the state in the browser before comparing — click the toggle, open the panel — so you are comparing equivalent states, not the original's open menu against WordPress's closed one. Reproduce the behaviour per `custom-blocks-guide.md`; do not enqueue the original JS.
