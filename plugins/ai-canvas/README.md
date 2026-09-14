# ai-canvas

Vibe-code pages and posts on any WordPress site from Claude Code. Connect a site once with an Application Password, then describe the page you want; Claude writes it as a single full-width Custom HTML block (markup, CSS, and JS), publishes it through the site's built-in REST API, and checks the result in your browser.

No WordPress plugin of ours is required. The site needs one thing from the plugin directory, [Jamie's Visual HTML Editor](https://wordpress.org/plugins/jamies-visual-html-editor/), which lets the site owner click text and images on the finished page to edit them in wp-admin and gives the Custom HTML block its full-width alignment.

## Skills

| Skill | Trigger | What it does |
|---|---|---|
| **setup** | "connect Claude to my website", "set up AI-Canvas on `<site>`" | Walks a beginner through wp-admin (plugin install, Administrator user, Application Password), then verifies the connection and saves it |
| **vibe** | "build a landing page on my site", "write a post about…", "change the photo on my page", "undo that" | Creates and updates pages and posts as one HTML block, with browser verification and undo |

Both skills are written for **non-technical users**: one step at a time, literal wp-admin labels, no jargon in user-facing text, results reported as the page (link plus screenshot) rather than files or API calls.

## How it works

Each page or post body is one block:

```html
<!-- wp:html {"align":"full"} -->
<style data-wp-block-html="css">…</style>
<script data-wp-block-html="js">…</script>
<div class="canvas-my-page">…</div>
<!-- /wp:html -->
```

WordPress stores it as an ordinary page on one of two page templates the setup skill creates over REST: **AI Canvas (with header and footer)**, built by copying the header and footer parts from the theme's own page template, or **AI Canvas (blank)**, which renders nothing but the block. Neither shows a page title. The visual HTML editor plugin turns `align: full` into the theme's full-width wrapper, and the site owner can open the page in wp-admin and click any heading, paragraph, or image to change it.

`scripts/wp.sh` is the only route to the site. It needs nothing but `bash` and `curl`, which macOS, Linux, and Git Bash on Windows all include. Credentials live in one file per site under `~/.claude/ai-canvas/sites/` (mode 600), read by curl itself, so the Application Password never appears on a command line after setup. Content travels as a multipart form field, so nothing is JSON-encoded on the way up, and a small awk decoder handles the way down. Commands: `sites`, `add-site`, `remove-site`, `me`, `find`, `get`, `create`, `update`, `revisions`, `restore`, `trash`, `media`, `upload`, `check`, `templates`, `template-get`, `template-ensure`, `template-delete`.

## setup

A strict role split. The user performs every step that changes their site with Claude explaining exactly what to click and waiting; Claude never installs plugins or creates users or credentials itself. Once it holds the site address, username, and Application Password it:

- Saves the connection with `wp.sh add-site`
- Verifies credentials and capabilities with `wp.sh me`, catching a missing `unfiltered_html` (multisite, `DISALLOW_UNFILTERED_HTML`) or `edit_theme_options` (role below Administrator) before anything is built
- Creates the two page templates with `wp.sh template-ensure`, discovering the theme's header and footer parts from its page template
- Routes host-level problems (a stripped Authorization header) through the hosting company's support with a drafted message rather than server file edits
- Offers a first page as a smoke test; its `check` step confirms the visual HTML editor plugin is active

## vibe

- **Two templates.** Framed (site header and footer, no title) by default; blank for standalone landing pages. Chosen from the brief, or by one plain question.
- **One block, scoped.** A single root element with a distinctive class, every selector prefixed with it, JS in an IIFE. Theme header and footer are never restyled. States only JS can leave (scroll reveals, tab panels) live under an `.is-js` class the script adds, so the page is complete in wp-admin's editor, where the script never runs.
- **Human-editable output.** Text stays in ordinary elements and images in plain `<img>` tags so the site owner can edit them in wp-admin after the fact.
- **Undo.** WordPress revisions are the history. `create` re-saves once so the first version is recorded (core skips revisions on insert), every `update` records the new version, and `restore` sends a revision back without decoding it. The owner sees the same history under Revisions in wp-admin.
- **Verification.** With Claude in Chrome: open the live URL, screenshot, exercise the JS, read the console, check phone width. Without it: `wp.sh check` confirms the page is served with its style and script intact and reports whether the full-width wrapper is present.
- **Performance rules on the first write.** Right-sized Media Library variants, explicit image dimensions, fold-aware lazy loading, IntersectionObserver over scroll handlers, `<button>`-based widgets with ARIA state.
- **Posts** ask once whether to publish or draft, since publishing notifies subscribers.

## Requirements

On the WordPress site (the setup skill walks the user through all of it):

- HTTPS (Application Passwords require it; local Studio sites excepted)
- [Jamie's Visual HTML Editor](https://wordpress.org/plugins/jamies-visual-html-editor/) active, for in-place editing and full-width alignment
- A dedicated **Administrator** user with an Application Password. Administrator is required because creating page templates needs `edit_theme_options`; the password is revocable from the user's profile at any time.
- A **block theme**. The page templates only exist on block themes; classic themes are not supported.

Locally: Claude Code only; the script uses `bash` and `curl`, which are already present on macOS, Linux, and Git Bash on Windows. [Claude in Chrome](https://claude.com/chrome) is optional but recommended; it upgrades verification from "page is served" to "page works".

```bash
# Install ai-canvas
/plugin install ai-canvas@a8cteam51-claude-code-plugins

# Connect a site (guided, one-time)
# > connect Claude to my website https://example.com

# Then build in natural language
# > build me a landing page for our spring launch
# > swap the hero photo for something warmer
# > undo that change
```
