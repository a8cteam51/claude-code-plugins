---
name: setup
description: Guide a beginner through connecting Claude Code to their WordPress site so it can build pages and posts — walk them through wp-admin (install the visual HTML editor plugin, create a connection user, create an Application Password), then verify the connection and save the credentials automatically. Use when the user asks to "set up AI-Canvas", "connect Claude to my website", "let Claude edit my site", "connect my WordPress site", "add my site", "install AI-Canvas on <site>", or wants an AI to build pages on their WordPress site and no site is connected yet, or when the vibe skill reports that no site is set up.
argument-hint: "[site-url]"
---

# Connect a WordPress site

End state: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/wp.sh" sites` lists the user's site, and `wp.sh me <site>` reports `missing: none`.

The script needs only `bash` and `curl`, which macOS, Linux, and Git Bash on Windows all include. Nothing else has to be installed on the user's computer.

**Role split.** The user does everything that changes their site (installing a plugin, creating a user, creating an Application Password) with you telling them exactly what to click and waiting. You never install anything, create users, or make credentials yourself, even if other tools could. Once you hold the three inputs — site address, username, Application Password — you do everything else: verification and saving the connection.

**Assume a beginner.** One step at a time, wait for confirmation after each. Use the exact words wp-admin shows on screen. Explain what an Application Password is in plain terms ("a separate password made just for this connection — your normal login is untouched, and you can switch it off any time"). Keep "REST", "API", "curl", "JSON", and HTTP codes out of user-facing text. Every failed check is reported as what happened plus what to do next. If the user turns out to be technical, condense; never the reverse.

## Phase A — guided manual steps (the user acts)

### A1. Check the site qualifies

Ask the user to check, telling them where to look:

- **Site address.** The address they type to reach their site, starting with `https://`. Application Passwords only work over `https://` (local test sites such as `http://localhost:…` are the exception).
- **They can log in to wp-admin as an administrator.** They will need that to install a plugin and create a user.
- **A block theme is active.** Appearance shows **Editor** (block theme) rather than **Customize** (classic theme). Required: the page templates this plugin creates only exist on block themes. If the theme is classic, stop and explain that the site needs a block theme first (all default WordPress themes since Twenty Twenty-Two qualify).

### A2. Install the visual HTML editor plugin

This plugin lets the user edit text and pictures on the pages you build by clicking on them in wp-admin, and it is what makes full-width sections possible.

Have them go to **Plugins → Add New Plugin**, search for **Jamie's Visual HTML Editor**, click **Install Now**, then **Activate**. Plugin page for reference: https://wordpress.org/plugins/jamies-visual-html-editor/

Do not proceed past this step on the user's word alone; A2 is verified in B5 on the first page you build.

### A3. Create the connection user and Application Password

1. **Users → Add New User.** Username something like `claude`, any email they control, role **Administrator**. Administrator is needed because the plugin creates two page templates on the site (one with the site header and footer, one completely blank), and only administrators can manage templates. Say this plainly, and add the safeguard: the Application Password created next is the only thing this computer holds, and clicking **Revoke** on it later cuts the access off completely.
2. **Open that user's profile** (Users → All Users → click the name) → scroll to **Application Passwords** → in **New Application Password Name** type `claude-code` → click **Add New Application Password**. Copy the password shown — it appears once. It looks like groups of letters and numbers separated by spaces; copy the whole thing, spaces included.

If the **Application Passwords** section is missing from the profile: the site is on plain `http://` (see A1), or a security plugin has switched them off. Ask which security plugins are active and point them to that plugin's settings for "Application Passwords" or "REST API".

Two setups where even an administrator cannot publish the HTML blocks this plugin writes: **multisite networks** (only network admins can) and sites with **`DISALLOW_UNFILTERED_HTML`** set. B2 detects both. Do not attempt a workaround; explain that the site's configuration blocks it and who can change that (the network admin or whoever hosts the site).

### A4. Collect the three inputs

Ask for **site address**, **username**, and **Application Password**. If any is missing or garbled, ask again — never go looking for them through other tools. Never accept the user's normal WordPress login password; if they paste it, tell them to change it and create an Application Password instead.

Reassure them: the Application Password is saved in a private file on this computer so the connection keeps working next time, and they can cut it off any time by clicking **Revoke** next to it on the same profile screen.

## Phase B — automated verification (you act)

Run these yourself and report each result in plain language. Stop at the first failure, explain the fix, and re-run.

### B1. Save the connection

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/wp.sh" add-site https://SITE USERNAME 'APP PASSWORD'
```

This writes a private file under `~/.claude/ai-canvas/sites/` (readable only by the user's account). After this command the password never appears in conversation again — not in summaries, not in "how to re-add it later" snippets. If it is ever needed again, re-run this phase with fresh credentials.

If `sites` already lists this host, `add-site` replaces that entry. If it lists a different site, keep both; the vibe skill asks which site to use when more than one is saved.

### B2. Credentials and permissions

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/wp.sh" me SITE
```

- **Reports the user and `missing: none`** → proceed.
- **"rejected the username or Application Password"** → have the user re-check the password first (a fresh one is fastest: Revoke, then Add New). If a correct password still fails, the hosting company is dropping the login information before WordPress sees it. Draft a short message the user can send to their host's support: "Please allow the HTTP Authorization header to reach PHP for WordPress REST API requests." Non-technical users should not edit server files themselves.
- **`missing` contains `unfiltered_html`** → multisite or `DISALLOW_UNFILTERED_HTML` (A3). Pages would save with the styling and interactivity stripped out. Explain and stop; this needs the site owner or host.
- **`missing` contains `edit_theme_options`** → the role is below Administrator, so templates cannot be created. Have them change it (Users → click the name → Role → Administrator → Update User).
- **`missing` contains `publish_pages`/`publish_posts`/`upload_files`** → the role is below Administrator; same fix.
- **Could not reach the site** → typo in the address, or the site blocks automated requests (some security plugins do). Check the address in a browser first.

### B3. Create the two page templates

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/wp.sh" template-ensure SITE
```

This reads the theme's own page template, copies whichever header and footer parts it uses, and creates two templates on the site: **AI Canvas (with header and footer)** and **AI Canvas (blank)**. It is safe to run again; existing templates are left alone. The owner sees them in the Site Editor under Templates and in the page editor's Template dropdown. Report `header_parts: 0` or `footer_parts: 0` to the user: the theme's page template has no such part, so the framed template will match the theme in that respect.

### B4. Confirm the browser tool, if present

If `mcp__claude-in-chrome__*` tools are available in this session, tell the user you will be able to look at pages in their browser to check your work. If not, mention that installing Claude in Chrome is optional and lets you check pages visually; otherwise you verify that the page is served correctly.

### B5. First page

Offer a smoke test now: build a small page titled "Hello" through the vibe skill. It publishes a live page (unlinked from menus, so visitors will not find it unless told the address). The vibe skill's `check` step reports whether the full-width wrapper is present; if not, the plugin from A2 is not active — go back to A2. Trash the test page afterwards if the user wants.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `add-site` succeeds but `me` reports rejected credentials | Wrong password, or the host strips the Authorization header — see B2 |
| `me` works but `missing` lists `unfiltered_html` | Multisite or `DISALLOW_UNFILTERED_HTML` — site owner or host must change it |
| Application Passwords section absent from the profile | Site is on `http://`, or a security plugin disabled them |
| Page publishes but `check` shows no `alignfull_wrapper` | Jamie's Visual HTML Editor not active (A2) |
| `template-ensure` says the connection user cannot manage templates | Role below Administrator — B2 |
| `template-ensure` says the theme has no `page` template | Classic theme — A1 |
| Page publishes but `script_was_escaped` is true | Connection user lacks `unfiltered_html` — multisite, or the constant above |
| Two saved sites, unclear which to use | `wp.sh sites` shows both; name the site in each request, or `remove-site` the stale one |
