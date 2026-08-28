# ai-canvas

Set up and drive the [AI-Canvas](https://github.com/a8cteam51/ai-canvas) WordPress plugin from Claude Code: connect a site's `ai-canvas` MCP endpoint once, then build vibe-coded landing pages through per-page HTML/CSS/JS file tools — live-verified in the browser, with one-call undo.

Each canvas is a normal WordPress page (or post) whose body is a trio of files the WordPress plugin owns — `index.html`, `style.css`, `script.js` — rendered between the theme header and footer, or alone on a fully blank template. Claude writes those files, and only those files, through the MCP tools; writes are live immediately, and every write retains the file's previous version for instant rollback.

## Skills

| Skill | Trigger | What it does |
|---|---|---|
| **setup** | "set up AI-Canvas on `<site>`", "connect Claude to my website" | Guides the user through the wp-admin steps, then verifies the site and registers the MCP server automatically |
| **vibe** | "build a landing page on my site", "add a page to my website", "update the hero on `<page>`", "undo that change" | Builds and edits canvas pages through the connected MCP tools |

Both skills are written for **non-technical users**: one step at a time, literal wp-admin labels, no jargon in user-facing text, results reported as the page (link + screenshot) rather than files.

## setup

A strict role split. The user performs every step that changes their site — installing the two WordPress plugins, creating a dedicated Editor user, creating an Application Password — with Claude explaining exactly what to click and waiting. Once Claude holds the three inputs (site URL, username, Application Password), it automates everything that remains:

- Endpoint existence check, credential/`Authorization`-header passthrough check, and a REST capability check that catches missing `unfiltered_html` (multisite, `DISALLOW_UNFILTERED_HTML`) before the first write fails
- `claude mcp add` registration (direct HTTP, or the `@automattic/mcp-wordpress-remote` stdio proxy for hosts that strip the header) and an end-to-end smoke test
- Host-level fixes are routed through the hosting company's support with a drafted message, never through the user editing config files

The Application Password is the only credential involved — stored in the local MCP config so the connection persists across sessions, revocable any time from the user's profile screen.

## vibe

Page building with the guardrails that keep canvas pages healthy:

- **MCP tools only, enforced** — canvas content moves exclusively through the connected server's MCP tools; if they're missing (a server registered mid-session doesn't load until `/mcp` or a restart), the skill stops and asks the user to reconnect rather than improvising, and a preflight matches the tool prefix to the intended site when multiple ai-canvas servers are registered
- **Fragment and scoping ground rules** — `index.html` is injected into a complete page, so everything is wrapped in one distinctively-classed root and every selector is prefixed with it; canvas CSS never restyles the theme's header/footer
- **Performance rules applied on the first write** — reference right-sized image variants (the media tools return dimensions and generated sizes), explicit `width`/`height` on every image, below-fold-only lazy-loading with an eager `fetchpriority="high"` hero, `preload="none"` + IntersectionObserver video, literal HTML over client-side templating, IntersectionObserver sentinels instead of layout-reading scroll handlers, `<button>`-based ARIA widgets
- **Instant undo** — every `write-file` retains the previous version; `rollback-file` swaps it back live, and swapping again re-does
- **Self-verification in the browser** — with Claude in Chrome available, the agent opens the live URL, screenshots the render between the theme header and footer, exercises interactions, reads the console, and checks a phone-width viewport for overflow before reporting; `curl` is the fallback, reported as markup-only verification
- **Media Library workflow** — reuse existing assets via `list-media`, upload via URL or base64 with `alt` text, reference returned URLs verbatim

## Safeguard hook

The plugin ships a `PreToolUse` hook (`scripts/guard-mcp-endpoint.py`) that deterministically blocks the one dangerous fallback an agent might reach for when the MCP tools are unavailable: talking to the site's `/wp-json/ai-canvas/mcp` endpoint directly over HTTP. It denies:

- Bash commands that hit an ai-canvas MCP endpoint with credentials, custom headers, request bodies, method overrides, or MCP protocol payloads (`jsonrpc`, `tools/call`) — including HTTP-library one-liners
- Writing or editing helper scripts that embed the endpoint alongside anything that would call or authenticate against it

It deliberately allows the setup skill's unauthenticated status probe, all `claude mcp …` registration/management commands, and Markdown files (docs quote these commands). The deny message tells the agent the actual fix: ask the user to run `/mcp` or restart the session so the tools load. The hook fails open on unexpected input and requires only `python3` on PATH.

## Requirements

On the WordPress site (the setup skill walks the user through all of it):

- WordPress **6.9+** (Abilities API), a **block theme**, and HTTPS (Application Passwords require it; local Studio sites excepted)
- [AI-Canvas](https://github.com/a8cteam51/ai-canvas) WordPress plugin — **≥ 0.2.0** for `rollback-file` and image-size output — plus [WordPress MCP Adapter](https://github.com/WordPress/mcp-adapter) **≥ 0.6.1**
- A dedicated **Editor** user with an Application Password (Editor covers every tool's capability checks on a single site)

Locally: nothing beyond Claude Code. [Claude in Chrome](https://claude.com/chrome) is optional but recommended — it upgrades verification from "markup is served" to "page works".

```bash
# Install ai-canvas
/plugin install ai-canvas@a8cteam51-claude-code-plugins

# Connect a site (guided, one-time)
# > set up AI-Canvas on https://example.com

# Then build in natural language
# > build me a landing page for our spring launch
# > swap the hero photo for something warmer
# > undo that change
```
