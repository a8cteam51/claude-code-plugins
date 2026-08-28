---
name: vibe
description: Build and edit landing pages on a WordPress site through the connected AI-Canvas MCP tools (create-canvas, read-file, write-file, rollback-file, upload-media, list-media, list-canvases). Use when the user asks to "build a landing page on my site", "add a page to my website", "make me a page for my event", "change the photo/text/colors on my page", "undo that change to my page", "vibe a page", "create a canvas", "update the hero on <canvas page>", or any request to create or change page content on a site where ai-canvas MCP tools are available. Not for block/Gutenberg editing — canvases are file-based pages the AI-Canvas plugin renders between the theme header and footer.
---

# Build pages with AI-Canvas

You are writing three files per page — `index.html`, `style.css`, `script.js` — that the AI-Canvas plugin renders between the site's theme header and footer. The MCP tools are the only way in; there is no other filesystem access, and that is by design.

## Ground rules for the files

**index.html is a fragment, not a document.** It is injected into an already-complete page. Never include `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`, `<title>`, meta tags, or `<link>`/`<script>` tags for the canvas's own CSS/JS — `style.css` and `script.js` are enqueued automatically with cache-busting. Inline `<style>`/`<script>` blocks work but belong in the dedicated files.

**Scope everything.** The theme's header, footer, and global styles surround your markup. Wrap the fragment in one root element with a distinctive class (e.g. `<main class="canvas-spring-launch">…`) and prefix every CSS selector with it. Never style `body`, `html`, `:root`, or bare element selectors — that bleeds into the theme's header/footer and reads as a broken site. If a design fights the theme's content-width constraints, style within the canvas root rather than overriding theme layout classes.

**JS runs same-origin and unsandboxed.** Keep it self-contained: DOM behavior, animation, small interactions. Do not call authenticated site endpoints, embed third-party scripts, or exfiltrate anything — the site owner accepted the trust model for page behavior, not for arbitrary reach.

**Limits:** 2 MB per file. Images do not belong inline as data URIs — put them in the Media Library.

## Keep pages fast

Vibe-coded pages become performance black holes through a handful of repeatable mistakes. Apply these on the first write, not as an afterthought:

- **Right-size every image.** `upload-media` and `list-media` return each image's pixel dimensions and its generated smaller sizes — reference the smallest size that covers the display area. A full-size photo rendered into a 600px column is the single most common way these pages balloon.
- **Every `<img>` gets explicit `width` and `height`** matching the referenced size, so the layout doesn't shift as images load.
- **Lazy-load below the fold only.** `loading="lazy" decoding="async"` on below-fold images; the hero/LCP image stays eager with `fetchpriority="high"`. Don't lazy-load anything that could be visible on first paint on a tall screen.
- **Video is opt-in.** `preload="none"` (with `muted playsinline` for ambient video), started and paused by an IntersectionObserver as it enters and leaves the viewport. Upload a modest encode sized ~1.5× its display area, never a camera original.
- **JS ships literal HTML.** No frameworks and no client-side templating — the markup in `index.html` is what the browser renders. Never read layout in a scroll handler; sticky bars and reveal effects use IntersectionObserver sentinels.
- **Interactive widgets are `<button>`-based** with the matching ARIA state (`aria-expanded` on accordions/tabs, one item open at a time), and you prove them working in the browser — a widget that renders can still be one that never toggles.

## Workflow

1. **Find or create the page.** `list-canvases` first; only `create-canvas` (title, optional slug, `post_type` page|post) when the user wants a new page. It returns `post_id` (needed by every file tool) and the live `url`.
2. **Read before you write.** `read-file` each file you are about to change — a human or another agent may have touched it since you last looked. `write-file` replaces the whole file; there are no partial edits, so always write complete contents.
3. **Undo is one tool call.** Every `write-file` retains the file's outgoing contents as its single previous version (an identical write doesn't consume the slot). `rollback-file` instantly swaps a file with that previous version, and calling it again swaps back. When the user wants the last change undone, roll back every file you changed in that step. The slot reaches back exactly one write per file — anything older you rebuild from the conversation, so before a multi-step redesign keep the starting `read-file` contents in hand.
4. **Images:** `list-media` to reuse existing assets; `upload-media` (URL or base64 + filename, plus `title`/`alt`) for new ones. Both return the image's dimensions and generated sizes — pick the appropriate size per "Keep pages fast" and reference its URL verbatim, never a guessed one. Set `alt` — it is the only accessibility the image will get.
5. **Verify like a user.** After writing, check the live URL — in the browser via Claude in Chrome when its tools are available (next section), otherwise `curl`. Do not declare success from a 200 on `write-file` alone.

## Check your own work with Claude in Chrome

When the `mcp__claude-in-chrome__*` tools are available, use them to review every meaningful change as a visitor would — a successful `write-file` proves the file saved, not that the page works.

- Invoke the `claude-in-chrome` skill before first use if it is listed. If the tools are deferred, load everything you need in **one** `ToolSearch` call: `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `computer`, `read_page`, `read_console_messages` (add `resize_window` for responsive checks).
- Call `tabs_context_mcp` once at the start of the browser session, open the canvas `url` in a new tab, and reuse that tab across iterations — reload after each `write-file` (the plugin cache-busts CSS/JS, so a reload always shows the latest write).
- Screenshot and actually look at it: the content sits between the theme header and footer, your styles are applied, and nothing from your CSS has restyled the theme's own header/footer — a changed site header means a scoping violation (see Ground rules), not a theme quirk.
- If `script.js` does anything, exercise the interaction in the browser instead of assuming it ran, and check `read_console_messages` for errors.
- On layout-heavy pages, resize to a phone-width viewport for at least one check: look for horizontal overflow and absolutely-positioned decorations overlapping content — pixel-positioned decoration should be percentage/edge-pinned so it scales, or stack below content on small screens.
- Fixes found this way go through the normal loop: `read-file` → `write-file` → reload → re-screenshot. Stop when the screenshot matches what the user asked for, and report what you verified.

Without browser tooling, fall back to `curl` on the live URL — that proves the markup is served, not that it renders correctly; say which level of verification you did when reporting.

## Working with a non-technical user

Assume the user is non-technical unless they show otherwise. That changes how you talk, not what you build.

- **Report the page, not the files.** A finished step is "The top section now shows your spring photo — take a look: <link>", with the screenshot when you have one. Never mention index.html, CSS scoping, fragments, cache-busting, or MCP in user-facing text.
- **Translate every error before showing it.** Say what happened and what happens next, in their terms. "Permission denied" becomes "the connection between me and your site doesn't have permission to edit pages — that's fixable in your WordPress settings; want me to walk you through it?" (and route them to the setup skill). The failure-mode table below is for your diagnosis, not for quoting.
- **Vague brief: one round of questions, then build.** Ask at most once — what the page is for, must-have sections, brand colors — and check `list-media` for logos and photos before asking the user to supply anything. A visible first draft beats a questionnaire.
- **Infer content; never lorem ipsum.** Write real copy derived from whatever you have — the brief, the site's existing pages, media library titles. Where you had to invent specifics (prices, dates, addresses, testimonials), flag them in your report as guesses for the user to correct.

## Semantics the user should be reminded of (once, not repeatedly)

- **Writes are live immediately.** There is no draft or preview — but every change to a file keeps its previous version, so tell the user early: changes appear on the live page right away, and saying "undo that" always brings the last version back (via `rollback-file`).
- Full-page/CDN caches are purged by the plugin where it knows how (Batcache, Pressable edge); if the user reports a stale page on another host, that host's cache is the suspect — logged-in viewers always bypass it.
- The wp-admin editor for a canvas page intentionally shows a locked "AI-controlled" card, not the content. Content changes go through these tools only; title/slug/status are still edited in wp-admin as normal.

## Failure modes

| Error | Meaning |
|---|---|
| "Post N is not an AI canvas" | Wrong `post_id` — `list-canvases` and re-check; regular pages can be converted only by assigning the "AI Canvas" template in wp-admin |
| "Permission denied" | The connected user lacks capability for that tool (Editor role covers every tool) |
| "File exceeds the … limit" | 2 MB cap — move assets to the Media Library |
| "No previous version of the … file exists" | Nothing has overwritten that file yet — the rollback slot only exists after a second write |
| Invalid input / enum error | `file` must be exactly `html`, `css`, or `js` |
