# page-annotator

Annotate the web page you're viewing in Chrome and send the annotations
straight into Claude Code.

Run the skill, and Claude injects a small overlay into your open tab via the
**Claude in Chrome** extension. Click elements, leave notes ("this button
wraps", "wrong color on hover", "cut off at this width"), hit **Send to
Claude** — and Claude maps each note back to your source code and fixes,
reviews, or reports on it. A front-end engineer's companion: point at the
problem instead of describing it.

## Requirements

- The [Claude in Chrome](https://claude.com/chrome) extension, installed and
  connected to Claude Code, with permission for the site you're annotating.
- The target page open in a Chrome tab. Because it's your real browser
  session, logged-in states, feature flags, and real data all work.

No servers, no runtime dependencies. The overlay is dependency-free vanilla
JS and communicates through a hidden DOM node — nothing leaves the page. (A
dev-only script, `scripts/build-overlay.sh`, regenerates the minified copy
that actually gets injected.)

## Installation

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
/plugin install page-annotator@a8cteam51-claude-code-plugins
```

## Usage

```bash
/page-annotator:annotate                        # annotate the active tab
/page-annotator:annotate staging.example.com    # target a specific tab
```

Natural-language triggers work too: "annotate the page", "let me point at
elements on the page", "QA this page by pointing at elements".

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
- **✕** cancels and removes the overlay; refreshing or closing the tab also
  clears everything. **Esc** exits picking or closes the note panel.

Each annotation captures the element's unique CSS selector, class list,
visible text, trimmed `outerHTML`, ~20 computed styles, and its position —
plus page URL and viewport size — so Claude can usually map straight to source
without re-querying the page.

## How it works

1. Claude reads the bundled `overlay.js` and executes it in your tab through
   the extension's `javascript_tool`.
2. The overlay serializes annotations into a hidden
   `<script type="application/json">` node in the page.
3. Claude polls that node every few seconds until you click **Send to Claude**
   (or ~5 minutes pass, after which it waits for you to say "done").
4. Claude maps each annotation to your source code and acts per the chosen
   mode. The overlay stays on the page for follow-up batches — cleanup is
   yours, via refresh, closing the tab, or **✕**.
5. After applying changes, Claude refreshes the tab automatically and
   re-injects the overlay, so the page shows the fix and the annotation tool
   persists for the next round.

Injection is fast after the first run: the overlay caches its own source in
the tab's sessionStorage, so re-injections — including the automatic
post-fix refresh — send a tiny snippet instead of the full script. The cache
clears when the tab closes.

## Limitations

- Requires the Claude in Chrome extension — there is no standalone fallback.
- Elements inside iframes can't be picked (top document only).
- Reloading or navigating the tab yourself removes the overlay and any unsent
  annotations; Claude re-injects after its own post-fix refresh and offers to
  re-inject after a manual one.
- Annotation data (including element markup from the page) becomes part of
  your Claude Code conversation — bear that in mind on pages with sensitive
  content. The overlay scrubs form values, URL query strings, and token-like
  strings from captured markup before it leaves the page, but visible text is
  kept verbatim.

## License

MIT
