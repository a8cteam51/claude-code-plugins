---
name: vibe
description: Build and edit landing pages on a WordPress site through the connected AI-Canvas MCP tools (create-canvas, read-file, write-file, upload-media, list-media, list-canvases). Use when the user asks to "build a landing page on my site", "vibe a page", "create a canvas", "update the hero on <canvas page>", "make me a splash page for <thing>", or any request to create or change page content on a site where ai-canvas MCP tools are available. Not for block/Gutenberg editing — canvases are file-based pages the AI-Canvas plugin renders between the theme header and footer.
---

# Build pages with AI-Canvas

You are writing three files per page — `index.html`, `style.css`, `script.js` — that the AI-Canvas plugin renders between the site's theme header and footer. The MCP tools are the only way in; there is no other filesystem access, and that is by design.

## Ground rules for the files

**index.html is a fragment, not a document.** It is injected into an already-complete page. Never include `<!DOCTYPE>`, `<html>`, `<head>`, `<body>`, `<title>`, meta tags, or `<link>`/`<script>` tags for the canvas's own CSS/JS — `style.css` and `script.js` are enqueued automatically with cache-busting. Inline `<style>`/`<script>` blocks work but belong in the dedicated files.

**Scope everything.** The theme's header, footer, and global styles surround your markup. Wrap the fragment in one root element with a distinctive class (e.g. `<main class="canvas-spring-launch">…`) and prefix every CSS selector with it. Never style `body`, `html`, `:root`, or bare element selectors — that bleeds into the theme's header/footer and reads as a broken site. If a design fights the theme's content-width constraints, style within the canvas root rather than overriding theme layout classes.

**JS runs same-origin and unsandboxed.** Keep it self-contained: DOM behavior, animation, small interactions. Do not call authenticated site endpoints, embed third-party scripts, or exfiltrate anything — the site owner accepted the trust model for page behavior, not for arbitrary reach.

**Limits:** 2 MB per file. Images do not belong inline as data URIs — put them in the Media Library.

## Workflow

1. **Find or create the page.** `list-canvases` first; only `create-canvas` (title, optional slug, `post_type` page|post) when the user wants a new page. It returns `post_id` (needed by every file tool) and the live `url`.
2. **Read before you write.** `read-file` each file you are about to change — a human or another agent may have touched it since you last looked. `write-file` replaces the whole file; there are no partial edits, so always write complete contents.
3. **Images:** `list-media` to reuse existing assets; `upload-media` (URL or base64 + filename, plus `title`/`alt`) for new ones. Reference the returned attachment URL verbatim in the HTML/CSS. Set `alt` — it is the only accessibility the image will get.
4. **Verify like a user.** After writing, fetch the live URL (curl the page, or screenshot it if browser tooling is available) and confirm the content actually renders between the theme header and footer with styles applied. Do not declare success from a 200 on `write-file` alone.

## Semantics the user should be reminded of (once, not repeatedly)

- **Writes are live immediately.** There is no draft, preview, or undo — the recovery path is writing the file again. Before large rewrites of a page the user cares about, `read-file` the current version and keep it in the conversation so you can restore it.
- Full-page/CDN caches are purged by the plugin where it knows how (Batcache, Pressable edge); if the user reports a stale page on another host, that host's cache is the suspect — logged-in viewers always bypass it.
- The wp-admin editor for a canvas page intentionally shows a locked "AI-controlled" card, not the content. Content changes go through these tools only; title/slug/status are still edited in wp-admin as normal.

## Failure modes

| Error | Meaning |
|---|---|
| "Post N is not an AI canvas" | Wrong `post_id` — `list-canvases` and re-check; regular pages can be converted only by assigning the "AI Canvas" template in wp-admin |
| "Permission denied" | The connected user lacks capability for that tool (Editor role covers all six) |
| "File exceeds the … limit" | 2 MB cap — move assets to the Media Library |
| Invalid input / enum error | `file` must be exactly `html`, `css`, or `js` |
