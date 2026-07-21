---
name: annotate
description: This skill should be used when the user asks to "annotate the page", "annotate this page", "open the annotation overlay", "let me point at elements on the page", "mark up the page for fixes", "QA this page by pointing at elements", or invokes /page-annotator:annotate. Injects an annotation overlay into the page open in Chrome via the Claude in Chrome extension; the user clicks elements and leaves notes — each tagged Review or Fix in the overlay — which flow back into the session for Claude to act on. For collaborative pointing by the user — not for autonomous browser testing or screenshot review.
argument-hint: "[optional URL or tab hint]"
---

# Annotate a live web page

Inject an annotation overlay into the page the user is viewing in Chrome, wait
while they click elements and attach notes, then collect those annotations and
act on them. This is a front-end QA companion: instead of describing a visual
bug in words, the user points directly at the element in the real, logged-in,
fully-rendered page.

The overlay is a self-contained vanilla-JS script bundled at
`assets/overlay.js` and injected as the minified `assets/overlay.min.js`,
both relative to this skill's directory. It communicates
outward through a single hidden DOM node —
`<script type="application/json" id="__claude_annotations__">` — which works
regardless of the JavaScript world the extension executes in. There is no
server and no network traffic; polling that node is the only channel.

## Prerequisites

- The **Claude in Chrome extension** must be installed and connected, with
  permission for the target site. All browser access goes through the
  `mcp__claude-in-chrome__*` tools.
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
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__read_console_messages
```

`read_console_messages` is for diagnostics only: the overlay logs
`[claude-page-annotator] overlay ready`, `... sent N annotation(s)`, and
`... cancelled`, which confirm what happened when an injection or poll looks
wrong.

## Step 3 — Choose the target tab

Call `tabs_context_mcp` and pick the tab:

1. If the user gave a URL/tab hint, use the tab whose URL or title matches it.
2. Otherwise use the active tab.
3. If neither is unambiguous (several plausible matches, or the active tab is
   clearly unrelated, e.g. a new-tab page), ask the user which tab to use.

Never reuse tab IDs remembered from an earlier session.

## Step 4 — Inject the overlay

Injection is two-tier: every full injection caches the overlay's own source
in the tab's sessionStorage, so most injections need only a tiny snippet.

**Fast path — always try this first** (near-instant):

```js
(() => { try { const src = sessionStorage.getItem('__claude_annotator_src__'); if (!src) return 'NO_CACHE'; return (0, eval)('(' + src + ')')(); } catch (e) { return 'CACHE_FAILED: ' + (e && e.message); } })()
```

On success it returns the same ready string as a full injection. Exception:
if the overlay assets were edited during this session, skip the fast path
once — a full injection refreshes the cache.

**Full path** — on `NO_CACHE` or `CACHE_FAILED`: read `assets/overlay.min.js`
from this skill's directory and execute its full contents with
`javascript_tool` (fall back to `assets/overlay.js` only if the min file is
missing). Do not rewrite or partially inline it — inject verbatim.

On both paths, re-injection replaces any previous overlay AND discards its
saved annotations, so never re-inject over an active session without warning
the user first.

A successful run returns `[claude-page-annotator] ready on <url>` and logs
`[claude-page-annotator] overlay ready` to the console.

Then tell the user, briefly:

- A toolbar appeared in the top-right of the page.
- Click **Annotate element**, click the element in question, type the note,
  pick **Review** (Claude proposes, user approves) or **Fix** (Claude edits
  immediately), then **Save note** (Cmd/Ctrl+Enter also saves). Repeat for as
  many elements as needed; saved elements get numbered pins — blue for
  review, orange for fix.
- Click a numbered pin to re-open its note — edit the text, switch
  Review/Fix, or delete it.
- Click **Send to Claude** when finished, or **✕** to cancel.
- Do not reload or navigate the tab — that removes the overlay.

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
| `MISSING` | The page reloaded/navigated, wiping the overlay. Tell the user and offer to re-inject (previous annotations are lost). |
| `PARSE_ERROR` | Read the full node contents to diagnose; if unrecoverable, warn that re-injecting discards saved notes and re-inject only with the user's go-ahead. |
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
belongs to the user: refreshing the page, closing the tab, or clicking **✕**.
The overlay stays live after Send, so the user can annotate more elements,
edit or delete existing notes via their pins, and send another batch. The
annotations array is cumulative: on any later collection, process ids not
already handled, plus any already-handled annotation whose `updatedAt` (or
note/action content) changed since it was processed. Deleted annotations
simply disappear from the array.

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
   The refresh removes the overlay and state node.
5. Re-inject the overlay using the Step 4 fast path — the sessionStorage
   cache survives the reload — so the tool persists across the refresh, then
   tell the user the page is refreshed with their changes and resume polling
   (Step 5) for a verification round or the next batch.

## Failure modes

- **Browser tools unavailable / connection errors** — Claude in Chrome is not
  installed or connected. Stop and say so.
- **Injection returns an error** — the site may block extension access or the
  extension lacks permission for it; ask the user to grant the site permission
  in the extension settings.
- **Elements inside iframes** — the picker cannot cross iframe boundaries;
  the user can only annotate the top document. Mention this only if relevant.
- **Native dialogs** — never execute JavaScript that triggers
  `alert`/`confirm`/`prompt`; a modal dialog freezes the extension bridge.
- **Blocked raw read** — the extension bridge's safety filters may block the
  full-payload read when captured markup resembles sensitive data. Switch to
  the scoped-read fallback in Step 6; never re-run a blocked raw read
  verbatim.
- **`CACHE_FAILED` mentioning eval or CSP** — the site blocks `eval` in the
  extension world (rare). Use the full injection path; everything else works
  the same.
- **Hashed class names** — selectors on CSS-modules/styled-components sites
  lean on structure and text instead; the overlay filters common generated
  class-name patterns out of selectors, though unusual schemes can slip
  through.

## Additional resources

- **`assets/overlay.js`** — the readable overlay source (toolbar, element
  picker, note panel, state serialization). Read it only when debugging the
  overlay itself.
- **`assets/overlay.min.js`** — the minified build injected on the full
  path. After editing `overlay.js`, regenerate it with
  `scripts/build-overlay.sh` at the plugin root — the two files must stay in
  sync.
- **`references/source-mapping.md`** — annotation payload schema and
  strategies for mapping rendered DOM back to source across common stacks.
