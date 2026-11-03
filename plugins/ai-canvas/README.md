# ai-canvas

Design a WordPress page with Claude on your own computer, then move it to your site when it is ready. Claude writes the page as a single full-width Custom HTML block (markup, CSS, and JS), shows it in a local preview, and changes it on your feedback. Nothing touches the site until you ask; then the page goes in through your own logged-in Chrome, with no password, key, or connection to set up.

## Skills

| Skill | Trigger | What it does |
|---|---|---|
| **design** | "build me a landing page", "change the hero photo", "undo that" | Writes the page to a local folder, builds a preview, checks it, and iterates on feedback. Never touches a site. |
| **publish** | "put it on my site", "send that change to the site", "make it live", "pull my page down" | Asks whether the page keeps the site's header and footer or stands alone, moves it into wp-admin by clipboard, creates the AI Canvas page templates if the site lacks them, saves a draft, and checks the result on the site. |

Both skills are written for **non-technical users**: plain language, real copy instead of placeholder text, results reported as the page (address plus screenshot) rather than files or code.

## How it works

Each page is one folder on your computer, in a place you choose. Claude asks where before the first draft; your Desktop is the usual answer.

```text
~/Desktop/ai-canvas/<page-slug>/
├── block.html    the page: one complete Custom HTML block
├── preview/      index.html, alone.html, editor.html, theme.html, phone.html
├── history/      snapshots, so "undo that" always works
└── site.txt      where the page lives on the site, once it does
```

`block.html` holds one block:

```html
<!-- wp:html {"align":"full"} -->
<style data-wp-block-html="css">…</style>
<script data-wp-block-html="js">…</script>
<div class="canvas-my-page">…</div>
<!-- /wp:html -->
```

**Designing.** `scripts/canvas.sh preview` lints the block against the rules WordPress enforces silently (a `<` inside the script, a second `<h1>`, a document-level tag, an unprefixed selector) and builds five preview pages: the page between a stand-in header and footer, the page with nothing around it, the page with its script never run (what wp-admin's editor shows the site owner), the page under a deliberately hostile theme stylesheet, and the page at phone width. Each preview page exposes `aiCanvasReport()`, one line of JSON covering script errors, heading structure, overflow, images, target sizes, and which theme styles reached the block. With [Claude in Chrome](https://claude.com/chrome), Claude opens the preview, reads the report, looks at screenshots, and uses the page's widgets by mouse and keyboard before showing you anything.

**Publishing.** `scripts/canvas.sh copy` puts the block on the system clipboard and prints its hash. In your Chrome, Claude opens the page in wp-admin, switches the post editor to its Code editor, pastes, and confirms the editor holds exactly the local page (same hash) before WordPress saves it. The page never passes through Claude as text, so it arrives byte for byte. The first publish saves a draft only you can see; it goes live when you say.

**The templates.** Every page uses one of two page templates, and the publish skill asks you which: **AI Canvas** (the site's header, the page content at full width, the site's footer) or **AI Canvas (blank)** (only the page content, nothing around it). Neither prints a page title, and both wrap the content in `<main>`, so the same block works under either. The publish skill creates them on first use, copying the header and footer parts from the theme's own page template.

**Changes after publishing.** You keep designing locally; "send that to the site" replaces the page's content the same way. If the page was edited in wp-admin in the meantime, the publish skill notices (the stored hash no longer matches), copies the site's version down through the Code editor, and carries your pending changes over before sending anything.

## scripts/canvas.sh

Local only; it never contacts a site. Commands: `lint`, `preview`, `serve`, `keep`, `undo`, `hash`, `copy`, `paste`, `record`, `status`, and `contrast` (WCAG ratio for hex color pairs). It needs bash and the system's standard tools; `serve` needs python3, php, or ruby.

## Requirements

On the WordPress site:

- A **block theme**. The page templates only exist on block themes.
- [Jamie's Visual HTML Editor](https://wordpress.org/plugins/jamies-visual-html-editor/) active. It gives the Custom HTML block its full-width alignment and lets the site owner click text and images to edit them in wp-admin.
- You, logged in to wp-admin in Chrome as an **Administrator** (creating the templates needs it). On a multisite network only network admins can publish pages with scripts.

On your computer: Claude Code and [Claude in Chrome](https://claude.com/chrome). Designing works without Claude in Chrome, though Claude then cannot see the page; publishing without it is a manual paste and cannot create the templates.

Developed and tested on macOS against WordPress 7.1 with Twenty Twenty-Five. The clipboard commands also have paths for Linux (`wl-copy`, `xclip`, `xsel`) and Windows (PowerShell, from Git Bash or WSL) that have not been run yet.

```bash
# Install ai-canvas
/plugin install ai-canvas@a8cteam51-claude-code-plugins

# Design locally
# > build me a landing page for our spring launch
# > make the heading bigger and swap the photo for something warmer
# > undo that

# Move it to the site when it is right
# > put it on my site https://example.com
# > make it live
```
