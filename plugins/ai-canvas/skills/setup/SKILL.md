---
name: setup
description: Guide a user through connecting Claude Code to a WordPress site running the AI-Canvas plugin — walk them through the wp-admin steps (plugin installs, connection user, Application Password), then automatically verify the site and register the MCP server once the URL and credentials exist. Use when the user asks to "set up AI-Canvas", "connect Claude to my website", "let Claude edit my site", "connect my site to AI-Canvas", "install AI-Canvas on <site>", "hook Claude up to my WordPress site for landing pages", "add the ai-canvas MCP server", or describes wanting an AI to build vibe-coded landing pages on their WordPress site and it is not connected yet.
argument-hint: "[site-url]"
---

# Set up AI-Canvas on a WordPress site

Goal: end state is `claude mcp list` showing an `ai-canvas` server connected to the user's site.

**Role split — this is the core of the skill.** The user performs every step that changes their site (installing plugins, creating the user, creating the Application Password) with you explaining exactly what to do and waiting; you never run wp-cli against their site, install anything, or create users/credentials yourself, even if tooling for it is available. Once you hold the three inputs — site URL, username, Application Password — you automate everything that remains: verification, diagnosis, and MCP registration.

**Assume a non-technical user from the start.** One step at a time, waiting after each; exact click paths using wp-admin's literal labels (the words on their screen are how they find things); credentials explained in plain terms ("an Application Password is a separate password created just for this connection — your normal login is untouched"); no jargon — "MCP", "endpoint", "curl", and HTTP status codes stay out of user-facing text, and every failed check is reported as what happened plus what to do next. If the user turns out to be technical, condense; never the reverse.

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
2. Open that user's profile → **Application Passwords** → name it (e.g. `claude-code`) → Add New → copy the generated password now (it is shown once). It looks like groups of letters separated by spaces — copy the whole thing, spaces included.

Two setups where Editor is not enough, both by core's design for unfiltered HTML: **multisite** grants `unfiltered_html` to super admins only, and a site defining **`DISALLOW_UNFILTERED_HTML`** grants it to no one. Warn the user now if either applies — canvas writes will be refused later otherwise (Phase B3 verifies this concretely).

### A4. Collect the three inputs

Ask for: **site URL**, **username**, **Application Password**. If any of the three is missing or garbled, ask the user for it — do not go looking for it yourself through other tooling (host APIs, wp-cli, team tools); the user just created these values and is the only authoritative source. The Application Password is the only credential involved — never ask for, or accept, their WordPress login password; if they paste it, tell them to change it and use the Application Password instead. Reassure them in plain terms: the password is stored on this computer so the connection keeps working next time, and they can cut off access whenever they want by revoking it on the same profile screen where they created it.

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
- **401** → either wrong credentials, or the host strips the `Authorization` header before PHP sees it. Distinguish by having the user re-check the password first; if credentials are right, it's the header. That is host configuration, not something to walk a non-technical user through: draft a short message they can send to their hosting support asking to pass the Authorization header through to PHP (on Apache it's one `.htaccess` line: `SetEnvIf Authorization "(.*)" HTTP_AUTHORIZATION=$1`). Meanwhile, or if the host won't change it, fall back to the stdio proxy (B4, option B).

### B3. The user has the required capabilities

```bash
curl -s -u 'USERNAME:APP_PASSWORD' 'https://SITE/wp-json/wp/v2/users/me?context=edit'
```

Check the `capabilities` map in the response for `publish_pages`, `upload_files`, and `unfiltered_html`. A missing `unfiltered_html` with an Editor role means multisite or `DISALLOW_UNFILTERED_HTML` (see A3) — surface it now, since canvas writes would return "Permission denied" later; do not attempt a workaround.

### B4. Register the MCP server

First check `claude mcp list` for existing registrations. If an ai-canvas server is already registered pointing at a **different** site (a local Studio site is common), do not silently invent a new name or overwrite it — tell the user what exists and decide together: replace it, or keep both with the new one named for its site (e.g. `ai-canvas-mysite`). End state must leave no ambiguity about which server name serves which site, because the vibe skill writes live to whichever server its tools point at.

**Option A — direct HTTP (Claude Code):**

```bash
claude mcp add ai-canvas https://SITE/wp-json/ai-canvas/mcp \
  -s user -t http -H "Authorization: Basic $(echo -n 'USERNAME:APP_PASSWORD' | base64)"
```

Run it yourself with the real values — do not hand a non-technical user a command to run. After this command, the credential never appears in conversation again: no echoing the Application Password or the `Authorization: Basic …` value in summaries, notes, or "here's how to re-add it later" snippets. If a registration is ever needed again, re-run this phase from the stored config or fresh credentials instead of quoting the secret.

**Option B — stdio proxy** (Claude Desktop, or hosts that fail B2's header check): configure `@automattic/mcp-wordpress-remote` via `npx` in the client's MCP config with `WP_API_URL`, `WP_API_USERNAME`, `WP_API_PASSWORD`.

### B5. Verify end to end

1. `claude mcp list` → `ai-canvas ✓ Connected`. That is the last direct check this skill makes against the site — B1–B3 were the only sanctioned HTTP calls, and they are done.
2. **The tools will not appear in this session, and that is expected, not a failure.** MCP servers load at session start, so a server registered mid-session contributes no tools until the user runs `/mcp` (reconnect) or restarts the session. Tell them that plainly ("one last step: restart me, or type `/mcp`, and I'll be connected to your site") and stop there. Never fill the gap by calling the endpoint directly with the credentials — canvas operations go through the MCP tools only, ever; a plugin hook blocks the HTTP route regardless.
3. In the new session, call the `list-canvases` tool: an empty list is success; an auth error means B2/B3 needs revisiting.
4. Offer a smoke test: create a canvas titled "Hello Canvas", write a one-line `index.html`, open the returned URL. Remind the user this publishes a live page; permanently deleting the post afterwards also removes its files (trash alone does not).

## Troubleshooting quick reference

| Symptom | Cause → fix |
|---|---|
| Tools not visible right after registration | Expected — servers load at session start; user runs `/mcp` or restarts the session. Never bypass with direct HTTP in the meantime |
| Two ai-canvas registrations, unclear which site the tools hit | Re-run the B4 pre-check: `claude mcp list` shows each URL; rename/remove with the user until names map unambiguously to sites |
| `claude mcp list` shows failed | Endpoint URL typo, or B2 header failure — re-run the curl checks |
| Tools connect but writes return "Permission denied" | Missing `unfiltered_html` (role below Editor, multisite, or `DISALLOW_UNFILTERED_HTML`) — see B3 |
| Tools missing from the list | mcp-adapter ≤ 0.4.x — user updates to ≥ 0.6.1 |
| `/wp-json/ai-canvas/mcp` 404s | Plugins inactive, or stale permalinks → Settings → Permalinks → Save |
| MCP `initialize` returns 403 | Connection user below Contributor — the transport requires `edit_posts`; use an Editor |
| Page renders without header/footer styling | Theme is classic, not block — A1 was skipped |
