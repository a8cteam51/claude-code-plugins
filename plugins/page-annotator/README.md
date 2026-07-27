# page-annotator

Annotate the web page you're viewing in Chrome and send the annotations
straight into Claude Code.

Ask Claude to annotate the page and a small overlay appears in your open tab.
Click elements, leave notes ("this button wraps", "wrong color on hover", "cut
off at this width"), hit **Send to Claude** — and Claude maps each note back to
your source code and fixes or reviews it. A front-end engineer's companion:
point at the problem instead of describing it.

## Requirements

- The [Claude in Chrome](https://claude.com/chrome) extension, installed and
  connected to Claude Code, with permission for the site you're annotating.
- [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey), with this
  plugin's userscript installed — Claude walks you through it the first time,
  and re-prompts whenever the plugin ships a newer version.
- The target page open in a Chrome tab. Because it's your real browser
  session, logged-in states, feature flags, and real data all work.

The overlay is dependency-free vanilla JS and communicates through a hidden
DOM node — nothing leaves the page, and it makes no network requests.

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
```

Natural-language triggers work too: "annotate the page", "let me point at
elements on the page", "QA this page by pointing at elements".

You can also arm the overlay yourself without asking Claude first, from the
Tampermonkey menu → **Annotate this page for Claude**. Claude will find it
already up on its next poll.

### Per-annotation actions

Each note carries its own action, chosen right in the overlay's note panel —
mix freely in one batch (one annotation on Review, the next on Fix):

| Action | What Claude does with that annotation |
|----------|--------------------------------------------|
| **Review** (default) | Maps the note to source, presents the finding with a proposed fix, asks before editing. |
| **Fix** | Treats the note as a fix instruction and edits the code immediately. |

### The overlay

- **Annotate element** → hover highlights elements; click one, type a note,
  toggle **Review** or **Fix**, then **Save note** (or Cmd/Ctrl+Enter). Saved
  elements get numbered pins — blue for Review, orange for Fix. The toggle is
  sticky, so consecutive notes keep the last choice.
- Click a numbered pin to re-open its note — edit the text, switch
  Review/Fix, or delete it. Changing anything after a Send re-arms the
  **Send to Claude** button as a new batch.
- **Send to Claude** hands everything over. The overlay stays on the page, so
  you can keep annotating and send further batches.
- **✕** closes the overlay; refreshing or closing the tab also clears
  everything. **Esc** exits picking or closes the note panel.

Each annotation captures the element's unique CSS selector, class list,
visible text, trimmed `outerHTML`, ~20 computed styles, and its position —
plus page URL and viewport size — so Claude can usually map straight to source
without re-querying the page.

## How it works

The userscript sits idle on every page, stamping its version onto `<html>` at
document-start. Nothing is visible until it's armed.

1. Claude probes `<html data-claude-annotator>` to check the userscript is
   installed and current, then arms the overlay by setting one attribute:
   `<html data-claude-annotate="on">`.
2. The overlay serializes annotations into a hidden
   `<script type="application/json">` node in the page.
3. Claude polls that node every few seconds until you click **Send to Claude**
   (or ~5 minutes pass, after which it waits for you to say "done").
4. Claude maps each annotation to your source code and acts per the chosen
   action. The overlay stays on the page for follow-up batches — cleanup is
   yours, via refresh, closing the tab, or **✕**.
5. After applying changes, Claude refreshes the tab automatically and re-arms
   the overlay, so the page shows the fix and the annotation tool persists for
   the next round.

The userscript runs in Tampermonkey's sandbox while Claude's `javascript_tool`
runs in the page's main world; the DOM is the only thing they share, which is
why the whole protocol is two attributes and one node. It also means a strict
Content-Security-Policy doesn't interfere — the overlay isn't page script.

## Limitations

- Requires both the Claude in Chrome extension and a userscript manager —
  there is no injected fallback.
- The userscript matches `*://*/*` so it's available everywhere. Narrow the
  `@match` in Tampermonkey's editor if you'd rather scope it to your dev
  hosts; Claude will report `NO_RESPONSE` on any page it no longer covers.
- Elements inside iframes can't be picked (top document only — the script
  declares `@noframes`).
- Reloading or navigating the tab yourself clears unsent annotations; the
  overlay returns idle and Claude re-arms it.
- Annotation data (including element markup from the page) becomes part of
  your Claude Code conversation — bear that in mind on pages with sensitive
  content. The overlay scrubs form values, URL query strings, and token-like
  strings from captured markup before it leaves the page, but visible text is
  kept verbatim.

## License

MIT
