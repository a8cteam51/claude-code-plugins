---
name: annotate
description: This skill should be used when the user asks to "annotate the page", "annotate this page", "open the annotation overlay", "let me point at elements on the page", "mark up the page for fixes", "QA this page by pointing at elements", or invokes /page-annotator:annotate. Arms an annotation overlay in the page open in Chrome; the user clicks elements and leaves notes — each tagged Review or Fix in the overlay — which flow back into the session for Claude to act on. The overlay ships as a Tampermonkey userscript that this plugin installs and keeps up to date. For collaborative pointing by the user — not for autonomous browser testing or screenshot review.
argument-hint: "[optional URL or tab hint]"
---

# Annotate a live web page

Arm an annotation overlay in the page the user is viewing in Chrome, wait
while they click elements and attach notes, then collect those annotations and
act on them. This is a front-end QA companion: instead of describing a visual
bug in words, the user points directly at the element in the real, logged-in,
fully-rendered page.

The overlay lives in the browser as a **Tampermonkey userscript**, not as an
injected payload. This plugin owns the canonical copy at
`assets/page-annotator.user.js` (relative to this skill's directory) and is
responsible for installing it and keeping the installed version in sync.

Two facts drive everything below:

- The userscript runs in Tampermonkey's **sandbox**; `javascript_tool` runs in
  the page's **main world**. They share only the DOM. So every exchange is a
  DOM read or a single attribute write — never a `window` global.
- The userscript is **idle** on every page until armed. It stamps its version
  on `<html>` at document-start and waits.

| Marker | Meaning |
|---|---|
| `<html data-claude-annotator="0.2.0">` | Userscript installed, at that version |
| `<html data-claude-annotate="on">` | Command: arm the overlay (Claude writes this) |
| `<html data-claude-annotate="off">` | Command: tear the overlay down |
| `<div id="__claude_annotator_host__">` | The overlay itself — present iff it is armed |
| `<script id="__claude_annotations__">` | The payload; **outlives** the overlay on cancel |

That last distinction matters: clicking **✕** removes the host but leaves the
state node behind holding `status: "cancelled"`, so the node is not a reliable
"is it armed" signal. Always test the host for that.

## Prerequisites

- The **Claude in Chrome extension**, installed and connected, with permission
  for the target site. All browser access goes through the
  `mcp__claude-in-chrome__*` tools.
- **Tampermonkey**, with this plugin's userscript installed (Step 4 handles
  installing and updating it).
- The target page must already be open in a Chrome tab.

If the browser tools cannot be loaded or return connection errors, stop and
tell the user to install/connect Claude in Chrome — do not fall back to
Playwright, curl, or any other mechanism.

## Step 1 — Parse the arguments

The argument string, if present, is a hint for which tab/URL to target
(Step 3) — there is no mode argument. If it begins with a legacy mode word
(`review`, `fix`, or `report`), ignore that word and treat the rest as the
tab hint.

Each annotation instead carries its own `action`, chosen per element in the
overlay UI:

| Action | Meaning |
|----------|-------------|
| `review` (default) | Map the annotation to source, present the finding with a proposed fix, and wait for approval before editing any file. |
| `fix` | Treat the note as a fix instruction: map to source and apply the edit immediately. |

## Step 2 — Load the browser tools

If the `mcp__claude-in-chrome__*` tools are deferred, load everything needed in
ONE ToolSearch call:

```text
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__read_console_messages
```

`read_console_messages` is for diagnostics only: the overlay logs
`[claude-page-annotator] overlay ready`, `... sent N annotation(s)`, and
`... cancelled`, which confirm what happened when arming or a poll looks
wrong.

## Step 3 — Choose the target tab

Call `tabs_context_mcp` and pick the tab:

1. If the user gave a URL/tab hint, use the tab whose URL or title matches it.
2. Otherwise use the active tab.
3. If neither is unambiguous (several plausible matches, or the active tab is
   clearly unrelated, e.g. a new-tab page), ask the user which tab to use.

Never reuse tab IDs remembered from an earlier session.

## Step 4 — Probe, then arm

**Probe** the target tab — one call, tells you both whether the userscript is
installed and whether the overlay is already up:

```js
JSON.stringify({ script: document.documentElement.dataset.claudeAnnotator || null, armed: !!document.getElementById('__claude_annotator_host__'), payload: !!document.getElementById('__claude_annotations__') })
```

Compare `script` against the version this plugin ships:

```bash
grep -m1 '^// @version' "${CLAUDE_PLUGIN_ROOT}/skills/annotate/assets/page-annotator.user.js"
```

| Probe result | Action |
|---|---|
| `script` matches the plugin's version | Arm it (below). |
| `script` is `null` | Not installed (or the page loaded before install) — run **4a**. |
| `script` differs from the plugin's version | Installed copy is stale — run **4a** to update. |
| `armed: true` | The overlay is already up; skip to Step 5 rather than re-arming. |
| `armed: false, payload: true` | A previous session was cancelled or sent. Arming resets it to a fresh batch — if the payload might hold unprocessed annotations, read it (Step 6) before arming. |

**Arm** the overlay. The userscript reacts to the attribute via a
`MutationObserver`, which fires asynchronously — so confirm in the same call
rather than assuming:

```js
document.documentElement.setAttribute('data-claude-annotate', 'on');
await new Promise((r) => setTimeout(r, 50));
document.getElementById('__claude_annotator_host__') ? 'ARMED' : 'NO_RESPONSE'
```

`ARMED` means the toolbar is up. `NO_RESPONSE` means the attribute landed but
nothing reacted — the userscript is not running on this page (check its
`@match`, and that it is enabled in Tampermonkey).

Arming is idempotent and never discards saved annotations, so a repeated arm
is harmless — unlike the injection mechanism this replaced.

### Step 4a — Install or update the userscript

Never navigate the target tab for this; it would destroy the page state the
user wants to annotate. Use a scratch tab.

1. Start the local install server in the background and read its output:

   ```bash
   node "${CLAUDE_PLUGIN_ROOT}/scripts/serve-userscript.js"
   ```

   It prints `VERSION=<x.y.z>` and `INSTALL_URL=<url>`, then serves for five
   minutes. It exits non-zero if the script's `@version` and `VERSION`
   constant disagree — if that happens, fix the file rather than working
   around it.

2. `tabs_create_mcp`, then `navigate` **that** tab to the `INSTALL_URL`.
   Tampermonkey intercepts the `.user.js` navigation and shows its own
   install page.

3. Tell the user to click **Install** (or **Reinstall**/**Update** if they
   already have an older copy) on that page, and to say when they're done.
   Do not click it for them — installing a userscript is the user's decision,
   and the button lives in extension UI.

4. When they confirm: close the scratch tab, kill the server, then **reload
   the target tab** (`navigate` to its live `location.href`). The userscript
   only attaches at document-start, so a page loaded before the install will
   not have it until reloaded.

5. Re-probe. If `script` is still `null`, the most likely causes are: the
   install was not completed, Tampermonkey is disabled, or the script's
   `@match` does not cover this URL. Report which and stop — do not fall back
   to injecting the overlay.

If Tampermonkey itself is not installed, its install page will not appear and
the browser will offer to download the file instead. Say so and point the user
at Tampermonkey (or Violentmonkey, which honours the same metadata); do not
attempt to install a browser extension.

### After arming, tell the user, briefly

- A toolbar appeared in the top-right of the page.
- Click **Annotate element**, click the element in question, type the note,
  pick **Review** (Claude proposes, user approves) or **Fix** (Claude edits
  immediately), then **Save note** (Cmd/Ctrl+Enter also saves). Repeat for as
  many elements as needed; saved elements get numbered pins — blue for
  review, orange for fix.
- Click a numbered pin to re-open its note — edit the text, switch
  Review/Fix, or delete it.
- Click **Send to Claude** when finished, or **✕** to cancel.
- Reloading or navigating the tab clears saved notes (the overlay returns
  idle, and Claude re-arms it).

They can also arm it themselves from the Tampermonkey menu → **Annotate this
page for Claude**, without asking Claude first.

## Step 5 — Poll until the user sends

Poll the state node with `javascript_tool`:

```js
(() => { const el = document.getElementById('__claude_annotations__'); if (!el) return 'MISSING'; try { const s = JSON.parse(el.textContent); return JSON.stringify({ status: s.status, count: s.annotations.length }); } catch (_) { return 'PARSE_ERROR'; } })()
```

Between polls, wait with `sleep 5` in Bash. After the first ~2 minutes, slow
to `sleep 15`. Do not perform unrelated work between polls.

| Result | Action |
|------------|------------|
| `status: "annotating"` | Keep polling. |
| `status: "sent"` | Proceed to Step 6. |
| `status: "cancelled"` | Confirm cancellation with the user and stop; leave the page as-is. |
| `MISSING` | The page reloaded/navigated, so the overlay went idle. Previous annotations are gone. Tell the user, then re-arm (Step 4) — no reinstall needed. |
| `PARSE_ERROR` | Read the full node contents to diagnose. Re-arming will not help; a fresh state node only appears after a reload. |
| Tool error | The tab may be closed or on a restricted page. Re-run `tabs_context_mcp` to check the tab still exists before telling the user anything. |

After ~5 minutes total without `sent`, stop polling and end the turn: tell the
user to say "done" after clicking **Send to Claude**, then read the state
directly when they return. If at that point the status is still `annotating`
but annotations exist, the user forgot to click Send — every save is written
to the node immediately, so confirm with the user and use them.

## Step 6 — Collect the annotations

Read the full payload:

```js
(() => { const el = document.getElementById('__claude_annotations__'); return el ? el.textContent : 'MISSING'; })()
```

If that read errors or its result is blocked by a safety filter (captured
markup can still resemble sensitive data despite the overlay's capture-time
scrubbing), do not retry the raw read. Fall back to scoped reads. First the
core fields for every annotation:

```js
(() => { const s = JSON.parse(document.getElementById('__claude_annotations__').textContent); return JSON.stringify(s.annotations.map(a => ({ id: a.id, note: a.note, action: a.action, selector: a.selector, tag: a.tag, classes: a.classes, text: a.text }))); })()
```

Then, per annotation and only when mapping actually needs them, the visual
details (substitute the annotation id; shrink the slice if still blocked):

```js
(() => { const a = JSON.parse(document.getElementById('__claude_annotations__').textContent).annotations.find(x => x.id === 1); return JSON.stringify({ styles: a.styles, rect: a.rect, outerHTML: a.outerHTML.slice(0, 500) }); })()
```

Parse the JSON (schema documented in `references/source-mapping.md`).

Leave the overlay and the state node in place — never remove them. Cleanup
belongs to the user: refreshing the page, closing the tab, clicking **✕**, or
the Tampermonkey menu → **Close annotator**. The overlay stays live after
Send, so the user can annotate more elements, edit or delete existing notes
via their pins, and send another batch. The annotations array is cumulative:
on any later collection, process ids not already handled, plus any
already-handled annotation whose `updatedAt` (or note/action content) changed
since it was processed. Deleted annotations simply disappear from the array.

## Step 7 — Map annotations to source

For each annotation, locate the code that produces the element. The payload
carries a CSS selector, tag, class list, trimmed text content, a trimmed
`outerHTML`, key computed styles, and the document coordinates — enough to map
without re-querying the page in most cases.

Search the codebase using class names, IDs, visible text, and attribute values
from the payload. Framework-specific strategies (Tailwind, CSS modules,
WordPress block themes, styled-components) are detailed in
`references/source-mapping.md` — consult it before grepping a stack with
hashed or utility class names. State the mapped file for each annotation and
flag any annotation that could not be confidently mapped rather than guessing.

## Step 8 — Act on each annotation

Group the collected annotations by their `action` field and handle both
groups in one pass. Annotations missing an `action` (captured by an older
overlay) default to `review`.

**`fix` annotations** — Apply the edit immediately for every one that maps
cleanly. If a note reads as an observation rather than an instruction, or the
element could not be mapped, do not force an edit — move it to the review
group instead and say why. Summarize every change as annotation →
`file:line` → what changed.

**`review` annotations** — Present a numbered list: the user's note, the
element (selector + text), the mapped `file:line`, and the proposed fix. Ask
which to apply (all, a subset, or none) and apply only the approved ones.

Deliver both in a single message: fixes applied first, then the review
findings awaiting a decision.

After making any code change, run Step 9 so the user sees the result
immediately. If no changes were made (review-only batch with every proposal
declined), skip Step 9 — the overlay is still live for further batches.

## Step 9 — Refresh and re-arm

After applying changes, refresh the page for the user and restore the
annotation tool:

1. If the project has a build step, wait for it to complete first so the
   refresh actually shows the new code.
2. Read the tab's live URL — `location.href` via `javascript_tool`. Do not
   navigate to the captured `page.url`; its token redaction may have altered
   it.
3. Run the Step 5 poll snippet once before reloading: if the node shows
   annotations beyond the ids already handled, the user kept annotating while
   the changes were being made — collect those first (Step 6), because the
   refresh destroys them.
4. Reload the tab by calling `navigate` with that URL (fall back to
   `location.reload()` via `javascript_tool` if `navigate` is unavailable).
5. Re-arm with the Step 4 arm snippet — the userscript reattaches on its own
   at document-start, so no probe or reinstall is needed — then tell the user
   the page is refreshed with their changes and resume polling (Step 5) for a
   verification round or the next batch.

## Failure modes

- **Browser tools unavailable / connection errors** — Claude in Chrome is not
  installed or connected. Stop and say so.
- **Probe returns `script: null` after a confirmed install** — the page was
  loaded before the userscript existed (reload it), Tampermonkey is disabled,
  or the `@match` does not cover this URL.
- **Arm returns `NO_RESPONSE`** — the attribute write landed but no userscript
  reacted. Same causes as above; re-probe rather than retrying the arm.
- **Version mismatch on every probe** — the user installed from somewhere
  other than this plugin. Re-run Step 4a; the plugin's copy is canonical.
- **Elements inside iframes** — the userscript declares `@noframes` and the
  picker cannot cross iframe boundaries; the user can only annotate the top
  document. Mention this only if relevant.
- **Native dialogs** — never execute JavaScript that triggers
  `alert`/`confirm`/`prompt`; a modal dialog freezes the extension bridge.
- **Blocked raw read** — the extension bridge's safety filters may block the
  full-payload read when captured markup resembles sensitive data. Switch to
  the scoped-read fallback in Step 6; never re-run a blocked raw read
  verbatim.
- **Hashed class names** — selectors on CSS-modules/styled-components sites
  lean on structure and text instead; the overlay filters common generated
  class-name patterns out of selectors, though unusual schemes can slip
  through.

A strict page CSP is *not* a failure mode here: the userscript runs in
Tampermonkey's sandbox, outside the page's CSP, and the attribute write and
DOM reads Claude performs are unaffected by CSP too.

## Additional resources

- **`assets/page-annotator.user.js`** — the canonical overlay userscript
  (toolbar, element picker, note panel, state serialization, arming
  plumbing). This plugin is the source of truth for its version; read it only
  when debugging the overlay itself. After editing it, bump **both** the
  `@version` metadata line and the `VERSION` constant, then reinstall via
  Step 4a.
- **`scripts/serve-userscript.js`** — serves the userscript over loopback so
  Tampermonkey can install it, and guards the two version fields against
  drift.
- **`references/source-mapping.md`** — annotation payload schema and
  strategies for mapping rendered DOM back to source across common stacks.
