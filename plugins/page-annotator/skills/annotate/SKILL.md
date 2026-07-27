---
name: annotate
description: This skill should be used when the user asks to "annotate the page", "annotate this page", "file issues from the page", "open the annotation overlay", "let me point at elements on the page", "report bugs by pointing at them", "QA this page and raise tickets", or invokes /page-annotator:annotate. Arms an annotation overlay in the page open in Chrome; the user clicks elements, leaves notes, and names a GitHub repository — each annotation then becomes one GitHub issue carrying a screenshot of the element in context plus browser and environment details. The overlay ships as a Tampermonkey userscript that this plugin installs and keeps up to date. For collaborative pointing by the user — not for autonomous browser testing or screenshot review.
argument-hint: "[optional URL or tab hint]"
---

# Annotate a live web page into GitHub issues

Arm an annotation overlay in the page the user is viewing in Chrome, wait while
they click elements and attach notes, then turn each annotation into a GitHub
issue with a screenshot. This is a front-end QA companion: instead of
describing a visual bug in words, the user points at the element in the real,
logged-in, fully-rendered page, and the finding lands in a tracker.

**One annotation → one issue.** This skill does not read or edit the codebase.

The overlay lives in the browser as a **Tampermonkey userscript**, not as an
injected payload. This plugin owns the canonical copy at
`assets/page-annotator.user.js` (relative to this skill's directory) and is
responsible for installing it and keeping the installed version in sync.

Two facts drive everything below:

- The userscript runs in Tampermonkey's **sandbox**; `javascript_tool` runs in
  the page's **main world**. They share only the DOM. So every exchange is a
  DOM read or an attribute write — never a `window` global.
- The userscript is **idle** on every page until armed. It stamps its version
  on `<html>` at document-start and waits.

| Marker | Direction | Meaning |
|---|---|---|
| `<html data-claude-annotator="0.3.0">` | script → you | Userscript installed, at that version |
| `<html data-claude-annotator-ack="…">` | script → you | Echo of the last command handled |
| `<html data-claude-annotate="…">` | you → script | `on` \| `off` \| `shot:<id>` \| `shot:end` |
| `<html data-claude-annotate-config="…">` | you → script | JSON: repo prefill and filed issue numbers |
| `<div id="__claude_annotator_host__">` | — | The overlay itself — present iff it is armed |
| `<script id="__claude_annotations__">` | — | The payload; **outlives** the overlay on cancel |

That last distinction matters: clicking **✕** removes the host but leaves the
state node behind holding `status: "cancelled"`, so the node is not a reliable
"is it armed" signal. Always test the host for that.

## Prerequisites

- The **Claude in Chrome extension**, installed and connected, with permission
  for the target site **and for `github.com`** — the attachment step needs the
  latter. All browser access goes through the `mcp__claude-in-chrome__*` tools.
- **Tampermonkey**, with this plugin's userscript installed (Step 4 handles
  installing and updating it).
- **`gh`**, installed and authenticated (`gh auth status`), with write access
  to the target repository.
- The target page must already be open in a Chrome tab.

If the browser tools cannot be loaded or return connection errors, stop and
tell the user to install/connect Claude in Chrome — do not fall back to
Playwright, curl, or any other mechanism.

## Step 1 — Parse the arguments

The argument string, if present, is a hint for which tab/URL to target
(Step 3). If it begins with a legacy mode word (`review`, `fix`, or `report`),
ignore that word and treat the rest as the tab hint — those modes no longer
exist.

If the argument looks like `owner/repo`, treat it as the target repository and
use it for the prefill in Step 4 instead of the working directory's remote.

## Step 2 — Load the browser tools

If the `mcp__claude-in-chrome__*` tools are deferred, load everything needed in
ONE ToolSearch call:

```text
select:mcp__claude-in-chrome__tabs_context_mcp,mcp__claude-in-chrome__javascript_tool,mcp__claude-in-chrome__navigate,mcp__claude-in-chrome__tabs_create_mcp,mcp__claude-in-chrome__tabs_close_mcp,mcp__claude-in-chrome__computer,mcp__claude-in-chrome__find,mcp__claude-in-chrome__upload_image,mcp__claude-in-chrome__read_console_messages
```

`read_console_messages` is for diagnostics only: the overlay logs
`[claude-page-annotator] overlay ready`, `... filing N annotation(s) into
owner/repo`, and `... cancelled`.

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
| `armed: false, payload: true` | A previous session was cancelled or finished. Arming resets it to a fresh batch — if the payload might hold unfiled annotations, read it (Step 6) before arming. |

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
is harmless.

**Then prefill the repository.** Resolve a candidate — the `owner/repo`
argument from Step 1, else the working directory's remote:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

If that yields nothing (not a git repo, no GitHub remote), skip the prefill and
let the user type it. Otherwise push it in:

```js
document.documentElement.setAttribute('data-claude-annotate-config', JSON.stringify({ repo: 'owner/name' }));
await new Promise((r) => setTimeout(r, 50));
document.documentElement.dataset.claudeAnnotatorAck
```

The overlay only accepts the prefill when its repo field is empty, so a
repository the user set on a previous visit to this origin always wins. Never
overwrite what the user typed.

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
- The **owner/repo** field says where issues will be filed. It remembers the
  repository per site, so it usually only needs filling in once.
- Click **Annotate element**, click the element in question, optionally give
  the issue a title, type the note, then **Save note** (Cmd/Ctrl+Enter also
  saves). Repeat for as many elements as needed; saved elements get numbered
  pins.
- Click a numbered pin to re-open its note — edit it or delete it.
- Click **Create GitHub issues** when finished, or **✕** to cancel.
- Reloading or navigating the tab clears unfiled notes.

They can also arm it themselves from the Tampermonkey menu → **Annotate this
page for Claude**, without asking Claude first.

## Step 5 — Poll until the user is ready

Poll the state node with `javascript_tool`:

```js
(() => { const el = document.getElementById('__claude_annotations__'); if (!el) return 'MISSING'; try { const s = JSON.parse(el.textContent); return JSON.stringify({ status: s.status, repo: s.repo, total: s.annotations.length, pending: s.annotations.filter((a) => !a.issue).length }); } catch (_) { return 'PARSE_ERROR'; } })()
```

Between polls, wait with `sleep 5` in Bash. After the first ~2 minutes, slow
to `sleep 15`. Do not perform unrelated work between polls.

| Result | Action |
|------------|------------|
| `status: "annotating"` | Keep polling. |
| `status: "sent"` | The user clicked **Create GitHub issues** — proceed to Step 6. |
| `status: "filed"` | Everything in the batch is already filed; nothing to do. Keep polling for a new batch, or stop if the user is done. |
| `status: "cancelled"` | Confirm cancellation with the user and stop; leave the page as-is. |
| `MISSING` | The page reloaded/navigated, so the overlay went idle. Previous annotations are gone. Tell the user, then re-arm (Step 4) — no reinstall needed. |
| `PARSE_ERROR` | Read the full node contents to diagnose. Re-arming will not help; a fresh state node only appears after a reload. |
| Tool error | The tab may be closed or on a restricted page. Re-run `tabs_context_mcp` to check the tab still exists before telling the user anything. |

If `repo` is empty or malformed the Send button stays disabled, so a `sent`
status always carries a usable repository. If the user seems stuck, check
`repo` — an unfilled repo field is the likeliest reason they cannot send.

After ~5 minutes total without `sent`, stop polling and end the turn: tell the
user to say "done" after clicking **Create GitHub issues**, then read the state
directly when they return. If at that point the status is still `annotating`
but annotations exist, the user forgot to click it — every save is written to
the node immediately, so confirm with the user and use them.

## Step 6 — Collect the annotations

Read the full payload:

```js
(() => { const el = document.getElementById('__claude_annotations__'); return el ? el.textContent : 'MISSING'; })()
```

If that read errors or its result is blocked by a safety filter (captured
markup can still resemble sensitive data despite the overlay's capture-time
scrubbing), do not retry the raw read. Fall back to scoped reads. First the
core fields for every unfiled annotation:

```js
(() => { const s = JSON.parse(document.getElementById('__claude_annotations__').textContent); return JSON.stringify(s.annotations.filter((a) => !a.issue).map((a) => ({ id: a.id, title: a.title, note: a.note, selector: a.selector, tag: a.tag, classes: a.classes, text: a.text }))); })()
```

Then, per annotation, the visual details (substitute the annotation id; shrink
the slice if still blocked):

```js
(() => { const a = JSON.parse(document.getElementById('__claude_annotations__').textContent).annotations.find((x) => x.id === 1); return JSON.stringify({ styles: a.styles, rect: a.rect, outerHTML: a.outerHTML.slice(0, 500) }); })()
```

Save the payload verbatim to a working file — Step 9 feeds it to the filing
script:

```bash
WORK=$(mktemp -d)   # reuse this directory for the whole batch
```

Skip any annotation that already carries an `issue`; it was filed in an
earlier batch. The schema is documented in `references/github-issues.md`.

## Step 7 — Capture a screenshot per annotation

For each unfiled annotation, put the overlay into capture mode, screenshot,
then release it. Capture mode scrolls the element into view, hides the
overlay's own toolbar and pins, and rings the element.

```js
document.documentElement.setAttribute('data-claude-annotate', 'shot:1');
await new Promise((r) => setTimeout(r, 250));
document.documentElement.dataset.claudeAnnotatorAck
```

Wait for the ack to equal `shot:<id>:ok` for **the id you just asked for** —
the attribute keeps its previous value, so seeing `shot:1:ok` after requesting
`shot:2` means the command has not been handled yet. Poll a couple more times
before treating it as a failure.

| Ack | Meaning |
|---|---|
| `shot:<id>:ok` | Ringed and ready — take the screenshot now. |
| `shot:<id>:missing` | That annotation's element is gone from the DOM (page changed). Skip its screenshot; the issue is still worth filing without one. |
| `shot:<id>:no-overlay` | The overlay is not armed. Re-arm (Step 4). |

Then take the picture with the `computer` tool, on the target tab:

- `action: "screenshot"`, `save_to_disk: true`.
- Keep both the returned **`imageId`** (Step 8 uploads it) and the **local
  path** (the fallback if the upload fails).

When the whole batch is captured, release capture mode once:

```js
document.documentElement.setAttribute('data-claude-annotate', 'shot:end');
await new Promise((r) => setTimeout(r, 100));
document.documentElement.dataset.claudeAnnotatorAck
```

This also scrolls the page back to where the user was.

## Step 8 — Mint GitHub attachment URLs

GitHub has no API for issue attachments: the upload endpoint accepts only a
browser session, not a token. The only URL that renders inline in a **private**
repository is `https://github.com/user-attachments/assets/…`, and the only way
to obtain one is through the web editor. So this step uses the browser — once
for the whole batch, not once per annotation.

**Tell the user first**, in one line: a GitHub tab is about to open, it is only
there to attach the screenshots, and it will close on its own. An unannounced
window is the thing this step is most likely to be disliked for.

1. `tabs_create_mcp`, then `navigate` that tab to
   `https://github.com/<owner>/<repo>/issues/new`. Do not navigate a tab the
   user already had open.
2. Confirm it loaded — a 404 means the repository does not exist or the user
   cannot see it. Stop and say so.
3. `find` the file input for attachments in the issue body editor (query
   something like "hidden file input for attaching files to the issue body").
4. For each captured annotation:
   - Snapshot the editor's current text:

     ```js
     [...document.querySelectorAll('textarea')].map((t) => t.value).join('\n')
     ```

   - `upload_image` with that annotation's `imageId` and the input's `ref`.
   - Poll the same snippet until a new
     `https://github.com/user-attachments/assets/…` URL appears (GitHub shows
     an `Uploading…` placeholder first). Diff against the previous snapshot to
     identify which URL is the new one.
   - Record the URL against the annotation id.
5. `tabs_close_mcp` the scratch tab.

**Never submit the form, and never type into the title field.** The form is
only a means of reaching the uploader. Leaving the title empty also keeps the
page from prompting about unsaved changes — a native dialog would freeze the
extension bridge.

If any part of this fails — the input cannot be found, an upload never
resolves, github.com is not permitted for the extension — **do not retry in a
loop**. Fall back: file the issues without screenshots, and tell the user
plainly that the screenshots are on disk at the paths from Step 7 so they can
drag them in themselves.

## Step 9 — Preview, confirm, then file

Write the two inputs the filing script needs into `$WORK`:

- `payload.json` — the payload from Step 6, verbatim.
- `meta.json` — the repository, plus per-annotation title and screenshot URL:

  ```json
  {
    "repo": "owner/name",
    "annotations": {
      "1": { "title": "Trial CTA wraps to two lines at desktop widths",
             "screenshot": "https://github.com/user-attachments/assets/…" }
    }
  }
  ```

  Supply a `title` for every annotation the user left untitled: imperative,
  specific, ≤70 characters, describing the problem rather than the element.
  Where the user typed their own title, pass it through unchanged.

Render the issues without publishing anything:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/file-issues.mjs" \
  --payload "$WORK/payload.json" --meta "$WORK/meta.json" --dry-run
```

Show the user the numbered list of titles, one full body as a sample, and say
explicitly that each issue will include the element's visible text and markup
and the browser details — and, if the script reported the repository as
public, that this will be publicly visible.

**Wait for an explicit yes in chat.** Clicking **Create GitHub issues** in the
overlay signals intent, but publishing to a tracker needs confirmation here.
If the user wants only some of them, pass `--only 1,3`.

Then file for real — same command without `--dry-run`. It prints
`{"<id>": {"number": N, "url": "…"}}` on stdout and progress on stderr, skips
anything already filed, and exits non-zero if any issue failed while still
printing the ones that succeeded.

## Step 10 — Stamp the results back

Push the created issue numbers into the page so the pins turn green and a
later batch will not re-file them:

```js
document.documentElement.setAttribute('data-claude-annotate-config', JSON.stringify({ issues: { "1": { "number": 42, "url": "https://github.com/owner/name/issues/42" } } }));
await new Promise((r) => setTimeout(r, 50));
document.documentElement.dataset.claudeAnnotatorAck
```

Expect `config:ok`. Do this even after a partial failure — stamping the
successes is what makes a retry safe.

Then report to the user: each annotation as `#N → issue link`, and anything
that failed or was filed without a screenshot, with the reason.

Leave the overlay and the state node in place — never remove them. Cleanup
belongs to the user: refreshing the page, closing the tab, clicking **✕**, or
the Tampermonkey menu → **Close annotator**. The overlay stays live, so the
user can annotate more elements and file another batch. Do not reload the tab;
nothing was changed on the page and a reload would discard unfiled notes.

## Failure modes

- **Browser tools unavailable / connection errors** — Claude in Chrome is not
  installed or connected. Stop and say so.
- **`gh` missing or unauthenticated** — stop and tell the user to run
  `gh auth status`. Do not fall back to the GitHub REST API with curl.
- **Repository unreachable** — `file-issues.mjs` checks this before publishing
  anything and exits with the `gh` error. Usually a typo in the overlay's repo
  field, or no access.
- **Probe returns `script: null` after a confirmed install** — the page was
  loaded before the userscript existed (reload it), Tampermonkey is disabled,
  or the `@match` does not cover this URL.
- **Arm returns `NO_RESPONSE`** — the attribute write landed but no userscript
  reacted. Same causes as above; re-probe rather than retrying the arm.
- **Version mismatch on every probe** — the user installed from somewhere
  other than this plugin. Re-run Step 4a; the plugin's copy is canonical.
- **Attachment upload fails** — fall back to text-only issues plus the local
  screenshot paths (Step 8). Never let this block the filing.
- **Elements inside iframes** — the userscript declares `@noframes` and the
  picker cannot cross iframe boundaries; the user can only annotate the top
  document. Mention this only if relevant.
- **Native dialogs** — never execute JavaScript that triggers
  `alert`/`confirm`/`prompt`, and never leave a dirty GitHub form behind; a
  modal dialog freezes the extension bridge.
- **Blocked raw read** — the extension bridge's safety filters may block the
  full-payload read when captured markup resembles sensitive data. Switch to
  the scoped-read fallback in Step 6; never re-run a blocked raw read
  verbatim.
- **Edited after filing** — an annotation that already carries an `issue` is
  always skipped, even if the user later edits its note. The overlay says as
  much in the panel. If the user wants the change reflected, add a comment to
  the existing issue with `gh issue comment` rather than filing a duplicate.

A strict page CSP is *not* a failure mode here: the userscript runs in
Tampermonkey's sandbox, outside the page's CSP, and the attribute writes and
DOM reads are unaffected by CSP too.

## Additional resources

- **`assets/page-annotator.user.js`** — the canonical overlay userscript
  (toolbar, element picker, note panel, capture mode, state serialization,
  arming plumbing). This plugin is the source of truth for its version; read it
  only when debugging the overlay itself. After editing it, bump **both** the
  `@version` metadata line and the `VERSION` constant, then reinstall via
  Step 4a.
- **`scripts/file-issues.mjs`** — renders and creates the issues. Its header
  documents the flags; `--dry-run` is what Step 9's preview uses.
- **`scripts/serve-userscript.js`** — serves the userscript over loopback so
  Tampermonkey can install it, and guards the two version fields against
  drift.
- **`references/github-issues.md`** — payload schema, the issue body layout,
  and the detail of the attachment-minting flow and its fallbacks.
