# page-annotator

Annotate the web page you're viewing in Chrome and file each note as a GitHub
issue — with a screenshot.

Ask Claude to annotate the page and a small overlay appears in your open tab.
Type the repo you want issues in, click elements, leave notes ("this button
wraps", "wrong color on hover", "cut off at this width"), hit **Create GitHub
issues** — and each annotation becomes its own issue, carrying a screenshot of
the element ringed in context plus the selector, markup and browser details. A
front-end QA companion: point at the problem instead of describing it, and
have the ticket written for you.

**One annotation → one issue.** The plugin does not read or change your code.

## Requirements

- The [Claude in Chrome](https://claude.com/chrome) extension, installed and
  connected to Claude Code, with permission for the site you're annotating
  **and for `github.com`**.
- [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey), with this
  plugin's userscript installed — Claude walks you through it the first time,
  and re-prompts whenever the plugin ships a newer version.
- The [`gh` CLI](https://cli.github.com), authenticated (`gh auth status`),
  with write access to the repository you're filing into.
- The target page open in a Chrome tab. Because it's your real browser
  session, logged-in states, feature flags, and real data all work.

The overlay is dependency-free vanilla JS, makes no network requests, and
communicates through a hidden DOM node.

## Installation

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
/plugin install page-annotator@a8cteam51-claude-code-plugins
```

Then run the skill once. If the userscript isn't installed (or is out of
date), Claude opens Tampermonkey's install page in a scratch tab and asks you
to click **Install**. The plugin's copy at
`skills/annotate/assets/page-annotator.user.js` is always the canonical one —
it has no `@updateURL`, so Tampermonkey never updates it behind the plugin's
back.

## Usage

```bash
/page-annotator:annotate                        # annotate the active tab
/page-annotator:annotate staging.example.com    # target a specific tab
/page-annotator:annotate a8cteam51/example      # prefill the repository
```

Natural-language triggers work too: "annotate the page", "file issues from
this page", "QA this page and raise tickets".

You can also arm the overlay yourself without asking Claude first, from the
Tampermonkey menu → **Annotate this page for Claude**. Claude will find it
already up on its next poll.

### The overlay

- The **owner/repo** field decides where issues go. It's remembered per site,
  so it usually only needs filling in once; Claude prefills it from the
  working directory's git remote when it can. **Create GitHub issues** stays
  disabled until it's valid.
- **Annotate element** → hover highlights elements; click one, optionally give
  the issue a title, type the note, then **Save note** (or Cmd/Ctrl+Enter).
  Saved elements get numbered pins. Leave the title blank and Claude writes
  one from your note.
- Click a numbered pin to re-open its note — edit the text or delete it.
- **Create GitHub issues** hands the batch over. Claude screenshots each
  annotated element, shows you the issues it's about to open, and waits for
  your go-ahead before publishing anything.
- Filed pins turn **green** and show their issue number. They're skipped by
  every later batch, so you can keep annotating and file again without
  duplicates.
- **✕** closes the overlay; refreshing or closing the tab also clears
  everything. **Esc** exits picking or closes the note panel.

### What lands in the issue

Your note, then the screenshot, then the element's page URL, unique CSS
selector, visible text and document position; the browser, platform, viewport,
screen size, language, time zone and colour scheme; and a collapsed block with
the trimmed `outerHTML` and ~20 computed styles.

## How it works

The userscript sits idle on every page, stamping its version onto `<html>` at
document-start. Nothing is visible until it's armed.

1. Claude probes `<html data-claude-annotator>` to check the userscript is
   installed and current, then arms the overlay by setting one attribute.
2. The overlay serializes annotations into a hidden
   `<script type="application/json">` node in the page.
3. Claude polls that node until you click **Create GitHub issues**.
4. For each annotation, Claude puts the overlay into capture mode — it scrolls
   the element into view, hides its own toolbar and pins, and rings the
   element — then takes a viewport screenshot.
5. Claude opens **one** GitHub tab to attach the screenshots, and closes it
   again. This is the only visible interruption, and it's announced first.
6. Claude previews the issues, waits for your approval, files them with `gh`,
   and writes the issue numbers back into the page so the pins turn green.

The userscript runs in Tampermonkey's sandbox while Claude's `javascript_tool`
runs in the page's main world; the DOM is the only thing they share, which is
why the whole protocol is four attributes and one node. It also means a strict
Content-Security-Policy doesn't interfere — the overlay isn't page script.

### Why a GitHub tab has to open

GitHub has no API for issue attachments. The endpoint behind drag-and-drop
accepts only a browser session cookie, and rejects personal access tokens,
OAuth apps and GitHub Apps alike. Committing screenshots to a branch instead
doesn't work either: those images fail to render in **private** repositories,
because GitHub's image proxy fetches them anonymously.

There are CLI tools that do this headlessly, but they work by reading your
GitHub session cookie out of your browser's keychain — a credential equivalent
to your password. This plugin won't do that on your behalf. It uses the
browser you're already signed into, once per batch, and closes the tab
afterwards. If the upload fails for any reason, the issues are still filed
without screenshots and Claude tells you where the images are on disk.

## Limitations

- Requires the Claude in Chrome extension, a userscript manager, and `gh` —
  there is no fallback for any of the three.
- The userscript matches `*://*/*` so it's available everywhere. Narrow the
  `@match` in Tampermonkey's editor if you'd rather scope it to your dev
  hosts; Claude will report `NO_RESPONSE` on any page it no longer covers.
- Elements inside iframes can't be picked (top document only — the script
  declares `@noframes`).
- Reloading or navigating the tab yourself clears unfiled annotations.
- Editing a note after its issue is filed does not update the issue — the pin
  says so. Ask Claude to comment on the existing issue instead.
- **Annotation data is published to an issue tracker.** The element's visible
  text and markup, the page URL, and your browser details all end up in the
  issue — publicly, if the repo is public. The overlay scrubs form values, URL
  query strings, and token-like strings from captured markup before it leaves
  the page, but visible text is kept verbatim. Claude shows you the rendered
  issues and waits for approval before anything is created.

## License

MIT
