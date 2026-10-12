---
name: publish
description: Move a locally designed AI Canvas page onto the user's WordPress site through their own logged-in Chrome (Claude in Chrome), with no password or connection setup. Asks the user whether the page keeps the site's header and footer or stands alone, creates the two AI Canvas page templates if the site lacks them, pastes the page into the post editor's Code editor by clipboard, and saves a draft for the user to review. Also sends changes to a page already on the site, brings a page from the site down to this computer, makes a draft live, and lists the Media Library. Use only when the user asks to "put it on my site", "publish this", "move it to WordPress", "send that to the site", "update the page on my site", "make it live", "pull my page down", or asks what images are on their site.
---

# Put a page on the site

This moves a page built with `ai-canvas:design` onto the user's WordPress site, working in their own Chrome where they are already logged in. There is no password, key, or connection to set up. The page itself travels by clipboard, so it never passes through you as text; small scripts in the page do the rest. Run this only when the user asks for it.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/canvas.sh" <command> DIR
```

## What it needs

- **Claude in Chrome** (`mcp__claude-in-chrome__*`). Load `tabs_context_mcp`, `tabs_create_mcp`, `navigate`, `computer`, `find`, `javascript_tool`, `browser_batch`, and `tabs_close_mcp` in one `ToolSearch`. Without it, see "Without the browser tools".
- **The user logged in to wp-admin** in that Chrome, as an Administrator.
- **A block theme** and **[Jamie's Visual HTML Editor](https://wordpress.org/plugins/jamies-visual-html-editor/)** active on the site. The plugin gives the block its full width and lets the owner click text and images to edit them.

"Check the site" below tests all three and says what is missing.

## Rules for working in wp-admin

Each of these comes from a failure.

1. **Never type a password.** If a login screen appears, ask the user to log in and wait.
2. **Take a screenshot before sending keys to a tab.** Keys sent to a tab before its first screenshot go nowhere, with no error.
3. **Paste only into the Code editor. Never click, select, or type inside the visual canvas of a canvas page.** The visual HTML editor starts editing whatever is touched, rewrites the whole block from the live document, and the editor saves that on its own a minute later.
4. **Script results are one short line of JSON: names, numbers, booleans, hashes.** A result containing page markup, `key=value` text, or an address with a `?` comes back as `[BLOCKED: Cookie/query string data]`. Build addresses yourself from the site address and the page number.
5. **Leave the editor clean.** Before leaving an editor tab it must be back in the visual view and not dirty. A dirty editor raises a "Leave site?" dialog that freezes the browser tools. If a step failed midway, run "Discard".
6. **Work in a tab you opened, and close it when you finish.**

## The two templates

Every page uses one of two page templates, and **the user chooses**. Both print the page content at full width inside `<main>` with no page title, so the same block works under either.

| Template | Slug | The page gets |
|---|---|---|
| **AI Canvas** | `ai-canvas` | The site's own header above and footer below |
| **AI Canvas (blank)** | `ai-canvas-blank` | Nothing around it: no header, no footer |

Ask in plain words, never by template name: "Should this page have your site's usual header and footer around it, or stand on its own with nothing else on the page?" Ask once per page, on its first publish, unless the user has already said. A page that will stand alone has no site menu to lean on, so open the preview's `alone.html` and look before sending it.

## First time on the site

1. `canvas.sh status DIR`. No site recorded: continue here. A site recorded: go to "Send changes".
2. Ask which site, unless the user already said, and repeat the address back before going on.
3. Ask which of the two templates (above).
4. `canvas.sh copy DIR`. Note the `sha256` it prints; call it the local hash.
5. Open a new tab at `SITE/wp-admin/post-new.php?post_type=page` and take a screenshot. A login screen: rule 1. A dialog over the editor ("Choose a pattern", a welcome guide): `find` its Close button and click it, changing nothing in it.
6. Run **Check the site**. Stop on anything it reports (table below).
7. If `templates` lacks either slug, run **Create the templates**.
8. Run **Open the Code editor**. `dialogs` must be `0`; a dialog still open covers the text box, so close it and run the script again. Then `find` the text box labelled "Type text or HTML", click it, select all, and paste (`cmd+a`, `cmd+v`; `ctrl` where Chrome runs on Windows or Linux).
9. Run **Save** with the local hash, the chosen template, the page title (the block's `<h1>` text unless the user gave one), and `status: 'draft'`. It refuses to save unless the editor holds exactly the local page.
10. `canvas.sh record DIR --site SITE --id ID --status draft --template TEMPLATE`. It prints the preview and edit addresses.
11. **Check the page on the site**, then close the tab.
12. Tell the user it is on their site as a draft only they can see, with the preview address and a screenshot, and that it goes live when they say.

### Check the site

```js
window.aiCanvasSha = async (text) => {
  const stored = text.replace(/\n+$/, '');
  if (!crypto.subtle) return 'chars:' + [...stored].length;
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(stored));
  return [...new Uint8Array(bytes)].map((b) => b.toString(16).padStart(2, '0')).join('');
};
const [theme] = await wp.apiFetch({ path: '/wp/v2/themes?status=active' });
const me = await wp.apiFetch({ path: '/wp/v2/users/me?context=edit' });
const plugins = await wp.apiFetch({ path: '/wp/v2/plugins?status=active' }).catch(() => null);
const templates = await wp.apiFetch({ path: '/wp/v2/templates' }).catch(() => null);
const page = await wp.apiFetch({ path: '/wp/v2/pages/' + wp.data.select('core/editor').getCurrentPostId() + '?context=edit' });
JSON.stringify({
  blockTheme: theme.is_block_theme,
  canPublishPages: !!me.capabilities.publish_pages,
  canPublishScripts: !!me.capabilities.unfiltered_html,
  canManageTemplates: !!me.capabilities.edit_theme_options,
  visualHtmlEditor: plugins ? plugins.some((p) => p.plugin.indexOf('jamies-visual-html-editor/') === 0) : null,
  templates: templates ? templates.map((t) => t.slug).filter((slug) => slug.indexOf('ai-canvas') === 0) : null,
  pageId: page.id,
  pageStatus: page.status,
  pageTemplate: page.template,
  storedSha: await aiCanvasSha(page.content.raw),
});
```

| Result | Meaning and what to do |
|---|---|
| `blockTheme: false` | A classic theme. The templates need a block theme (Appearance shows **Editor**, not **Customize**). Stop and explain. |
| `canPublishPages: false` | The login cannot publish pages. The user logs in as an Administrator. |
| `canPublishScripts: false` | The site strips styles and scripts from this login's pages: a multisite network (only network admins may) or a site with `DISALLOW_UNFILTERED_HTML`. Stop; the network admin or host decides. |
| `canManageTemplates: false` | Not an Administrator, so the templates cannot be created. Same fix. |
| `visualHtmlEditor: false` | The plugin is missing. Have the user install it: **Plugins → Add New Plugin**, search **Jamie's Visual HTML Editor**, **Install Now**, **Activate**. You do not install plugins. Reload and check again. |
| `storedSha` starts `chars:` | A plain `http://` site that is not `localhost`; the browser cannot hash there. Compare against `chars:` plus the `chars` number from `canvas.sh hash` wherever a hash is called for. |

### Create the templates

Creates whichever of the two is missing; it is safe to run again. **AI Canvas** copies the header and footer parts from the theme's own page template. **AI Canvas (blank)** is the same without them.

```js
const [theme] = await wp.apiFetch({ path: '/wp/v2/themes?status=active' });
const have = (await wp.apiFetch({ path: '/wp/v2/templates' })).map((t) => t.slug);
const get = (slug) => wp.apiFetch({ path: '/wp/v2/templates/' + theme.stylesheet + '//' + slug + '?context=edit' });
const raw = (await get('page').catch(() => get('index'))).content.raw;
const cut = raw.indexOf('<!-- wp:post-content');
const parts = (text) => (text.match(/<!-- wp:template-part \{.*?\} \/-->/g) || []).join('\n');
const header = parts(cut === -1 ? raw : raw.slice(0, cut));
const footer = parts(cut === -1 ? '' : raw.slice(cut));
const main = [
  '<!-- wp:group {"tagName":"main","style":{"spacing":{"margin":{"top":"0"}}},"layout":{"type":"constrained"}} -->',
  '<main class="wp-block-group" style="margin-top:0"><!-- wp:post-content {"align":"full","layout":{"type":"constrained"}} /--></main>',
  '<!-- /wp:group -->',
].join('\n');
const wanted = [
  { slug: 'ai-canvas', title: 'AI Canvas', description: 'Site header, the page content at full width, site footer. No page title.', content: [header, main, footer].filter(Boolean).join('\n') },
  { slug: 'ai-canvas-blank', title: 'AI Canvas (blank)', description: 'Only the page content at full width. No header, footer, or page title.', content: main },
];
const created = [];
for (const template of wanted) {
  if (have.indexOf(template.slug) !== -1) continue;
  await wp.apiFetch({ path: '/wp/v2/templates', method: 'POST', data: template });
  created.push(template.slug);
}
JSON.stringify({ created, headerParts: header ? header.split('\n').length : 0, footerParts: footer ? footer.split('\n').length : 0 });
```

`headerParts: 0` or `footerParts: 0` means the theme's page template has no such part, so the AI Canvas template has none either. Tell the user; do not guess at one.

### Open the Code editor

```js
await wp.data.dispatch('core/editor').switchEditorMode('text');
JSON.stringify({
  mode: wp.data.select('core/editor').getEditorMode(),
  textBox: !!document.querySelector('.editor-post-text-editor'),
  dialogs: document.querySelectorAll('.components-modal__frame').length,
});
```

### Save

Replace `LOCAL_HASH`, `TEMPLATE`, and `TITLE`. For a page already on the site, drop `title` and `status` from the `editPost` call so they stay as they are.

```js
const ed = wp.data.select('core/editor');
const edit = wp.data.dispatch('core/editor');
const holds = await aiCanvasSha(ed.getEditedPostContent());
if (holds !== 'LOCAL_HASH') throw new Error('The editor does not hold the local page. Run Discard, copy again, and paste again.');
await edit.editPost({ title: 'TITLE', status: 'draft', template: 'TEMPLATE' });
await edit.savePost();
const saved = await wp.apiFetch({ path: '/wp/v2/pages/' + ed.getCurrentPostId() + '?context=edit' });
await edit.switchEditorMode('visual');
JSON.stringify({
  saved: ed.didPostSaveRequestSucceed(),
  id: saved.id,
  status: saved.status,
  template: saved.template,
  storedSha: await aiCanvasSha(saved.content.raw),
  dirty: ed.isEditedPostDirty(),
});
```

`saved` is `true`, `storedSha` equals the local hash, `template` is the one chosen, and `dirty` is `false`. A different `storedSha` after a successful save means the site changed the page as it stored it: see "When it goes wrong".

### Discard

Throws away what is in the editor and not yet saved, and puts the editor back in its visual view. Run it whenever a step fails between opening the Code editor and a successful save.

```js
const id = wp.data.select('core/editor').getCurrentPostId();
await wp.data.dispatch('core').clearEntityRecordEdits('postType', 'page', id);
await wp.data.dispatch('core/editor').switchEditorMode('visual');
JSON.stringify({ dirty: wp.data.select('core/editor').isEditedPostDirty(), mode: wp.data.select('core/editor').getEditorMode() });
```

## Check the page on the site

Open `SITE/?page_id=ID&preview=true` (a draft) or the page's own address (live) in the tab, then:

```js
const root = document.querySelector('[class|="canvas"]');
const doc = document.documentElement;
JSON.stringify({
  found: !!root,
  fullWidth: !!root && Math.round(root.getBoundingClientRect().width) === doc.clientWidth,
  scriptRan: !!root && root.classList.contains('is-js'),
  scriptMangled: [...document.querySelectorAll('script[data-wp-block-html]')].some((s) => s.textContent.indexOf('&#038;') !== -1),
  h1: document.querySelectorAll('h1').length,
  mainElements: document.querySelectorAll('main').length,
  siteHeader: !!document.querySelector('header.wp-block-template-part'),
  siteFooter: !!document.querySelector('footer.wp-block-template-part'),
  blankTemplate: document.body.classList.contains('page-template-ai-canvas-blank'),
  overflowX: Math.max(0, doc.scrollWidth - doc.clientWidth),
});
```

`found`, `fullWidth`, and `scriptRan` are `true`; `scriptMangled` is `false`; `h1` and `mainElements` are `1`; `overflowX` is `0`. On **AI Canvas**, `siteHeader` and `siteFooter` are `true` and `blankTemplate` is `false`; on **AI Canvas (blank)** it is the reverse.

Then take a screenshot and look. The page matches the local preview, and on AI Canvas the site's real header and footer are there and untouched; a changed header or footer is a selector that escaped the root class. Use any widget once. Fix problems in `block.html` with the design skill, then "Send changes"; never patch the page on the site.

## Send changes

For a page that `canvas.sh status DIR` shows on a site.

1. `canvas.sh status DIR` gives the site, the page number, its status and template, and the hash recorded at the last publish. `local: same as the last publish` means there is nothing to send.
2. **A live page changes for visitors the moment you save.** If the recorded status is `publish`, say so and get a clear yes first.
3. `canvas.sh copy DIR`, then open `SITE/wp-admin/post.php?post=ID&action=edit` in a new tab and take a screenshot.
4. Run **Check the site**. If `storedSha` is not the recorded hash, the page was edited on the site since you last sent it; sending now would erase that. Stop and go to "Bring a page down".
5. **Open the Code editor**, click the text box, select all, paste, then **Save** without `title` and `status`. `TEMPLATE` is the recorded one; the page keeps its template unless the user asks to switch, and then it is the other slug.
6. `canvas.sh record DIR --site SITE --id ID --status STATUS --template TEMPLATE`, **Check the page on the site**, close the tab, and report.

## Bring a page down

For a page that was edited on the site, or that has no folder here yet. The owner's edits arrive with harmless rewriting from the site's editor (`<path/>` as `<path></path>`, an empty `style=""`); that is not damage.

1. Find the page number: `site.txt`, or **Find a page** with the title the user gives. For a page with no folder, make one beside the user's other pages (`mkdir -p .../ai-canvas/<slug>`); if they have none yet, ask where to keep it first, as the design skill's "Where a page lives" says.
2. Open `SITE/wp-admin/post.php?post=ID&action=edit` in a new tab, take a screenshot, run **Check the site**, and note `storedSha`, `pageStatus`, and `pageTemplate`.
3. **Open the Code editor**, click the text box, select all, and copy (`cmd+a`, `cmd+c`).
4. Run **Discard**. Nothing was changed; this returns the editor to its visual view.
5. `canvas.sh paste DIR`. It snapshots what was there, replaces `block.html` with the clipboard, and prints its `sha256`, which must equal `storedSha`. If it refuses because the clipboard is not one `wp:html` block, the page was not built as an AI Canvas page; stop and say so.
6. `canvas.sh record DIR --site SITE --id ID --status STATUS --template TEMPLATE` with the status and template from step 2, close the tab, and rebuild the preview with the design skill.

When local changes were waiting as well, the snapshot from step 5 holds them. Compare it with the new `block.html` (`diff`), carry the user's pending changes over onto the site's version, check, and then "Send changes".

### Find a page

On any wp-admin screen:

```js
const pages = await wp.apiFetch({ path: '/wp/v2/pages?context=edit&status=any&per_page=20&search=' + encodeURIComponent('TITLE WORDS') });
JSON.stringify(pages.map((p) => ({ id: p.id, title: p.title.raw, status: p.status, template: p.template, modified: p.modified })));
```

## Make it live

Publishing shows the page to the public, so do it only on the user's clear word for this page. On any wp-admin screen for the site:

```js
const saved = await wp.apiFetch({ path: '/wp/v2/pages/ID', method: 'POST', data: { status: 'publish' } });
JSON.stringify({ id: saved.id, status: saved.status, address: saved.link.indexOf('?') === -1 ? saved.link : null });
```

`address: null` means the site uses plain links; the page is at `SITE/?page_id=ID`. Then `canvas.sh record DIR --site SITE --id ID --status publish --template TEMPLATE`, **Check the page on the site** at its live address, and tell the user the address. The page is not in any menu; visitors reach it by its address until the user adds it to one.

## Media Library

To see what images the site has, on any wp-admin screen:

```js
const items = await wp.apiFetch({ path: '/wp/v2/media?media_type=image&per_page=30&search=' + encodeURIComponent('WORDS') });
JSON.stringify(items.map((m) => ({
  id: m.id,
  title: m.title.rendered,
  alt: m.alt_text,
  full: [m.media_details.width, m.media_details.height, m.source_url],
  sizes: Object.entries(m.media_details.sizes || {}).filter(([name]) => name !== 'full').map(([name, s]) => [name, s.width, s.height, s.source_url]),
})));
```

Leave the search empty for the most recent uploads. Each size is its name, width, height, and address. Reference the address of the smallest size that covers where the image is shown, exactly as returned. An image with empty `alt` still needs alt text in the block. New images: the user adds them in wp-admin (**Media → Add New Media File**) and tells you when they are up.

## Without the browser tools

You cannot work in the site. Say so, and offer the manual route: `canvas.sh copy DIR`, then the user opens **Pages → Add New Page**, the **⋮** menu → **Code editor**, clicks in the box, pastes, clicks **Exit code editor**, picks **AI Canvas** or **AI Canvas (blank)** under Template in the sidebar if the site has them, and saves the draft. The templates cannot be created this way; without one the theme prints the page title above the page and may hold it to the theme's content width. Installing [Claude in Chrome](https://claude.com/chrome) removes all of this.

## When it goes wrong

| What you see | Meaning and what to do |
|---|---|
| A login screen | The user is not logged in to this site in Chrome. They log in; you wait. |
| Keys do nothing; the text box stays as it was | No screenshot was taken in the tab first (rule 2), or a dialog is still open over the text box. Take one, close any dialog, and repeat. |
| `[BLOCKED: Cookie/query string data]` | The script's result looked like an address or `key=value` text (rule 4). Return plain JSON fields only. |
| **Save** throws "does not hold the local page" | Something else was on the clipboard, or the paste missed the text box. **Discard**, `canvas.sh copy` again, click the box, select all, paste. |
| `saved: false` | WordPress refused the save. A message naming `template` means the template is missing: **Create the templates**, then paste and save again. |
| `storedSha` differs from the local hash after a successful save | The site altered the page as it stored it. With `canPublishScripts: false` it stripped the style and script. Otherwise a plugin is filtering page content; report it. |
| `fullWidth: false` on the site | The page is not on an AI Canvas template, or Jamie's Visual HTML Editor is inactive. |
| `scriptMangled: true`, or the page's widgets do nothing | A bare `<` in the block; the design skill's lint catches it. Fix locally and send again. |
| The tools stop responding after leaving the editor | A "Leave site?" dialog is open because the editor was dirty (rule 5). The user dismisses it in Chrome. |
| `storedSha` on the site differs from the hash recorded at the last publish | The owner edited the page in wp-admin. "Bring a page down" before changing anything. |
