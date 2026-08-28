---
name: setup
description: Connect Claude Code to a WordPress site running the AI-Canvas plugin — install the required WP plugins, create scoped credentials, verify host compatibility, and register the MCP server. Use when the user asks to "set up AI-Canvas", "connect my site to AI-Canvas", "install AI-Canvas on <site>", "hook Claude up to my WordPress site for landing pages", "add the ai-canvas MCP server", or describes wanting an AI to build vibe-coded landing pages on their WordPress site and it is not connected yet.
argument-hint: "[site-url]"
---

# Set up AI-Canvas on a WordPress site

Goal: end state is `claude mcp list` showing an `ai-canvas` server connected to the user's site, with the six AI-Canvas tools available. Work through the phases in order; each has a verifiable exit condition. Do not skip verification steps — most setup failures are host quirks that the checks below catch early.

AI-Canvas serves AI-written HTML/CSS/JS to visitors **unsanitized** (XSS by design). Before anything else, confirm the user understands this is for development/trusted sites, not sites with real users or customer data. If they hesitate, stop.

## Phase 1 — identify the site and access level

Establish via the user (AskUserQuestion if not stated):

1. **Site URL** (must be HTTPS — Application Passwords are disabled over plain HTTP; local Studio sites are the exception).
2. **What access exists**, in order of preference:
   - WP-CLI (SSH, or `studio wp` for local WordPress Studio sites)
   - Team51/Pressable tooling (if the user is Team51, the `team51` MCP tools can run wp-cli remotely)
   - wp-admin only → the install steps below become instructions you give the user instead of commands you run

## Phase 2 — verify prerequisites

Required: **WordPress 6.9+** (Abilities API in core) and a **block theme**.

With wp-cli: `wp core version` and `wp theme list --status=active` (block themes have a `theme.json` + `templates/`; all bundled Twenty Twenty-Two and later default themes qualify). Without wp-cli, ask the user to check Dashboard → Updates and Appearance → Themes.

If WP < 6.9 or the theme is classic, stop and tell the user what to change first — the plugin will not function degraded.

## Phase 3 — install the two WordPress plugins

Both install from GitHub releases (neither is on WordPress.org — do not send the user to the plugin directory search):

```bash
wp plugin install https://github.com/WordPress/mcp-adapter/releases/latest/download/mcp-adapter.zip --activate
wp plugin install <ai-canvas-release-zip-url> --activate
```

The AI-Canvas zip lives at the a8cteam51/ai-canvas releases page; if that URL 404s, ask the user for the zip location rather than guessing. Version constraints that matter:

- `mcp-adapter` must be **≥ 0.6.1** (0.6.0 fatals on web requests; ≤ 0.4.x silently breaks Claude Code tool listing).
- AI-Canvas declares `Requires Plugins: mcp-adapter`, so activating it without the adapter fails with a clear message — that error means "activate mcp-adapter first", not a broken install.

wp-admin-only path: user downloads both zips, uploads via Plugins → Add New → Upload, activates mcp-adapter first.

Verify: `wp plugin list` shows both active, and `curl -s -o /dev/null -w "%{http_code}" https://SITE/wp-json/ai-canvas/mcp` returns 401 (endpoint exists, wants auth) — a 404 means the plugins are not active or permalinks need flushing (`wp rewrite flush`).

## Phase 4 — create scoped credentials

Use a **dedicated Editor-role user**, not an administrator. Editor covers everything the tools check (`publish_pages`, `edit_post`, `upload_files`) and keeps the blast radius to content — the Application Password authenticates against the entire REST API, not just the AI-Canvas tools, so role choice is the real permission boundary.

```bash
wp user create ai-canvas-agent agent@example.com --role=editor
wp user application-password create ai-canvas-agent "claude-code" --porcelain
```

(or wp-admin: Users → Profile → Application Passwords). The spaces WordPress displays in the password are fine — validation strips them.

**Do not ask the user to paste the password into chat.** Give them the finished command to run themselves (the `!` prefix in Claude Code runs it in-session), with the password as the only thing they fill in.

## Phase 5 — verify the host passes Authorization through

The whole auth story depends on the `Authorization` header surviving to PHP. Have the user run (or run yourself if they shared credentials via environment):

```bash
curl -s -o /dev/null -w "%{http_code}" -u 'ai-canvas-agent:APP_PASSWORD' https://SITE/wp-json/wp/v2/users/me
```

- **200** → proceed.
- **401** → the host strips the header. On Apache, add to `.htaccess`: `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`. If the host config is untouchable, fall back to the stdio proxy (Phase 6, option B).

## Phase 6 — register the MCP server

**Option A — direct HTTP (preferred, works for Claude Code):**

```bash
claude mcp add ai-canvas https://SITE/wp-json/ai-canvas/mcp \
  -s user -t http -H "Authorization: Basic $(echo -n 'ai-canvas-agent:APP_PASSWORD' | base64)"
```

The user runs this themselves with their password substituted.

**Option B — stdio proxy** (Claude Desktop, or hosts that fail Phase 5): configure `@automattic/mcp-wordpress-remote` via `npx` in the client's MCP config with `WP_API_URL`, `WP_API_USERNAME`, `WP_API_PASSWORD`.

## Phase 7 — verify end to end

1. `claude mcp list` → `ai-canvas ✓ Connected`. (New MCP servers load on session start — the user may need to restart the session.)
2. In a fresh session, call the `list-canvases` tool. An empty list is success; an auth error means Phase 4/5 needs revisiting.
3. Offer a smoke test: create a canvas titled "Hello Canvas", write a one-line `index.html`, open the returned URL. Remind the user this publishes a live page, and delete it afterwards if they want (`wp post delete <id>` — trashing the post does not remove the file set).

## Troubleshooting quick reference

| Symptom | Cause → fix |
|---|---|
| `claude mcp list` shows failed | Endpoint URL typo, or Phase 5 failure — re-run the curl check |
| Tools connect but every call errors "Permission denied" | User role too low for that tool (see Phase 4 capability list) |
| Tools missing from the list | mcp-adapter ≤ 0.4.x — upgrade to ≥ 0.6.1 |
| `/wp-json/ai-canvas/mcp` 404s | Plugins inactive, or stale permalinks → `wp rewrite flush` |
| Page renders without header/footer styling | Theme is classic, not block — Phase 2 was skipped |
