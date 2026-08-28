---
name: setup
description: Guide a user through connecting Claude Code to a WordPress site running the AI-Canvas plugin — walk them through the wp-admin steps (plugin installs, connection user, Application Password), then automatically verify the site and register the MCP server once the URL and credentials exist. Use when the user asks to "set up AI-Canvas", "connect my site to AI-Canvas", "install AI-Canvas on <site>", "hook Claude up to my WordPress site for landing pages", "add the ai-canvas MCP server", or describes wanting an AI to build vibe-coded landing pages on their WordPress site and it is not connected yet.
argument-hint: "[site-url]"
---

# Set up AI-Canvas on a WordPress site

Goal: end state is `claude mcp list` showing an `ai-canvas` server connected to the user's site.

**Role split — this is the core of the skill.** The user performs every step that changes their site (installing plugins, creating the user, creating the Application Password) with you explaining exactly what to do and waiting; you never run wp-cli against their site, install anything, or create users/credentials yourself, even if tooling for it is available. Once you hold the three inputs — site URL, username, Application Password — you automate everything that remains: verification, diagnosis, and MCP registration.

AI-Canvas serves AI-written HTML/CSS/JS to visitors **unsanitized** (XSS by design). Before anything else, confirm the user understands this is for development/trusted sites, not sites with real users or customer data. If they hesitate, stop.

## Phase A — guided manual setup (the user acts, you instruct)

Present each step, then wait for the user to confirm before moving on. Adapt the instructions if they mention having wp-cli/SSH — give them commands to run themselves, never run the commands for them.

### A1. Confirm the site qualifies

Ask the user to verify, telling them where to look:

- **WordPress 6.9+** — wp-admin Dashboard → Updates shows the current version (or `wp core version` if they have shell).
- **A block theme is active** — Appearance shows an **Editor** entry (block themes) rather than **Customize** (classic). All bundled default themes since Twenty Twenty-Two qualify.
- **HTTPS** — Application Passwords are disabled over plain HTTP (local Studio sites excepted).

If any check fails, stop and explain what to change first — the plugin does not degrade gracefully on classic themes or older WordPress.

### A2. Install the two WordPress plugins

Neither is on WordPress.org — point the user at the release zips, not the plugin directory search:

1. **MCP Adapter** (must be ≥ 0.6.1): `https://github.com/WordPress/mcp-adapter/releases/latest/download/mcp-adapter.zip`
2. **AI-Canvas**: the latest zip from the a8cteam51/ai-canvas releases page. If there is no release or the link 404s, ask the user where their copy of the plugin lives rather than guessing.

wp-admin path: Plugins → Add New Plugin → Upload Plugin → upload and activate **mcp-adapter first**, then ai-canvas. (AI-Canvas declares `Requires Plugins: mcp-adapter`, so activating it first fails with a clear message — that error means "activate mcp-adapter first", not a broken install.)

### A3. Create the connection user and Application Password

Have the user:

1. Create a dedicated user, Users → Add New User, role **Editor** — not an administrator account. Editor covers everything the tools check (`publish_pages`, `edit_post`, `upload_files`, `unfiltered_html`) while keeping the credential's blast radius to content.
2. Open that user's profile → **Application Passwords** → name it (e.g. `claude-code`) → Add New → copy the generated password now (it is shown once).

Two setups where Editor is not enough, both by core's design for unfiltered HTML: **multisite** grants `unfiltered_html` to super admins only, and a site defining **`DISALLOW_UNFILTERED_HTML`** grants it to no one. Warn the user now if either applies — canvas writes will be refused later otherwise (Phase B3 verifies this concretely).

### A4. Collect the three inputs

Ask for: **site URL**, **username**, **Application Password**. Note for the user: the password ends up stored in their local Claude Code MCP config — that is its purpose — but if they prefer it never appear in the chat transcript, offer the alternative of you preparing the final registration command with a placeholder for them to run themselves (the `!` prefix runs it in-session). Everything in Phase B except B4 works with the password supplied either way, since B1 is unauthenticated and they can run the B2/B3 curl themselves too.

## Phase B — automated verification and registration (you act)

Run these yourself; report each result as you go. Stop at the first failure, explain the fix (which may be another manual step for the user), and re-run.

### B1. Endpoint exists (no auth needed)

```bash
curl -s -o /dev/null -w "%{http_code}" https://SITE/wp-json/ai-canvas/mcp
```

- **401** → correct (endpoint live, wants auth). Proceed.
- **404** → plugins inactive, or stale permalinks (user: Settings → Permalinks → Save, or `wp rewrite flush`).

### B2. Credentials work and the host passes Authorization through

```bash
curl -s -o /dev/null -w "%{http_code}" -u 'USERNAME:APP_PASSWORD' https://SITE/wp-json/wp/v2/users/me
```

(Spaces WordPress displays in the password are fine — validation strips them.)

- **200** → proceed.
- **401** → either wrong credentials, or the host strips the `Authorization` header before PHP sees it. Distinguish by having the user re-check the password first; if credentials are right, it's the header. On Apache the user adds to `.htaccess`: `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`. If the host config is untouchable, fall back to the stdio proxy (B4, option B).

### B3. The user has the required capabilities

```bash
curl -s -u 'USERNAME:APP_PASSWORD' 'https://SITE/wp-json/wp/v2/users/me?context=edit'
```

Check the `capabilities` map in the response for `publish_pages`, `upload_files`, and `unfiltered_html`. A missing `unfiltered_html` with an Editor role means multisite or `DISALLOW_UNFILTERED_HTML` (see A3) — surface it now, since canvas writes would return "Permission denied" later; do not attempt a workaround.

### B4. Register the MCP server

**Option A — direct HTTP (Claude Code):**

```bash
claude mcp add ai-canvas https://SITE/wp-json/ai-canvas/mcp \
  -s user -t http -H "Authorization: Basic $(echo -n 'USERNAME:APP_PASSWORD' | base64)"
```

Run it with the real values if the user shared the password; otherwise hand them the command with a placeholder to run via `!`.

**Option B — stdio proxy** (Claude Desktop, or hosts that fail B2's header check): configure `@automattic/mcp-wordpress-remote` via `npx` in the client's MCP config with `WP_API_URL`, `WP_API_USERNAME`, `WP_API_PASSWORD`.

### B5. Verify end to end

1. `claude mcp list` → `ai-canvas ✓ Connected`. New MCP servers load on session start — tell the user to restart the session if the tools aren't visible yet.
2. In the new session, call the `list-canvases` tool: an empty list is success; an auth error means B2/B3 needs revisiting.
3. Offer a smoke test: create a canvas titled "Hello Canvas", write a one-line `index.html`, open the returned URL. Remind the user this publishes a live page; permanently deleting the post afterwards also removes its files (trash alone does not).

## Troubleshooting quick reference

| Symptom | Cause → fix |
|---|---|
| `claude mcp list` shows failed | Endpoint URL typo, or B2 header failure — re-run the curl checks |
| Tools connect but writes return "Permission denied" | Missing `unfiltered_html` (role below Editor, multisite, or `DISALLOW_UNFILTERED_HTML`) — see B3 |
| Tools missing from the list | mcp-adapter ≤ 0.4.x — user updates to ≥ 0.6.1 |
| `/wp-json/ai-canvas/mcp` 404s | Plugins inactive, or stale permalinks → Settings → Permalinks → Save |
| MCP `initialize` returns 403 | Connection user below Contributor — the transport requires `edit_posts`; use an Editor |
| Page renders without header/footer styling | Theme is classic, not block — A1 was skipped |
