# Annotation payload schema & GitHub issue filing

## Payload schema

The state node `<script type="application/json" id="__claude_annotations__">`
contains one JSON object:

```json
{
  "version": 3,
  "script": "0.3.0",
  "status": "annotating | sent | filed | cancelled",
  "repo": "a8cteam51/example-site",
  "page": {
    "url": "https://staging.example.com/pricing",
    "title": "Pricing — Example",
    "referrer": "https://staging.example.com/",
    "viewport": { "width": 1512, "height": 823, "dpr": 2 },
    "capturedAt": "2026-07-27T14:03:22.000Z"
  },
  "env": {
    "userAgent": "Mozilla/5.0 (Macintosh; …) Chrome/141.0.0.0 Safari/537.36",
    "platform": "macOS",
    "language": "en-GB",
    "timezone": "Europe/London",
    "screen": { "width": 1728, "height": 1117 },
    "colorScheme": "dark",
    "reducedMotion": false
  },
  "annotations": [
    {
      "id": 1,
      "title": "",
      "note": "This button wraps to two lines on desktop — it shouldn't",
      "selector": "#pricing > div.tier-card:nth-of-type(2) > a.btn-primary",
      "tag": "a",
      "classes": ["btn", "btn-primary"],
      "text": "Start free trial",
      "outerHTML": "<a class=\"btn btn-primary\" href=\"/signup\">Start free trial</a>",
      "styles": { "display": "inline-flex", "font-size": "16px", "width": "142px" },
      "rect": { "x": 640, "y": 1180, "width": 142, "height": 58 },
      "scroll": { "x": 0, "y": 900 },
      "createdAt": "2026-07-27T14:04:10.000Z",
      "issue": { "number": 42, "url": "https://github.com/a8cteam51/example-site/issues/42" }
    }
  ]
}
```

Field notes:

- `version` — payload schema version. **3** is the GitHub-issue schema. It
  drops `action` (the old Review/Fix toggle), and adds `repo`, `env`, and the
  per-annotation `title`, `scroll` and `issue`. Version 1 and 2 payloads come
  from a pre-0.3.0 userscript: tell the user to update rather than trying to
  file from them.
- `script` — the version of the installed userscript that produced this
  payload. If it disagrees with the `@version` in the plugin's
  `assets/page-annotator.user.js`, the browser is running a stale copy and
  should be updated (SKILL.md Step 4a).
- `status` — `annotating` while the user works, `sent` once they click
  **Create GitHub issues**, `filed` once every annotation carries an `issue`,
  `cancelled` if they closed the overlay with **✕**. Editing anything after a
  send drops it back to `annotating`.
- `repo` — `owner/name`, from the toolbar field. The overlay remembers it per
  origin in the userscript manager's storage, and disables Send until it looks
  valid, so a `sent` payload always has a usable one.
- `title` — the user's optional issue title. Usually empty; generate one from
  the note when it is.
- `issue` — stamped back by Claude after filing (SKILL.md Step 10). Its
  presence means "already filed": `file-issues.mjs` skips it, and the overlay
  turns the pin green. This is the entire duplicate-prevention mechanism.
- `updatedAt` — present only when the note was edited after first save. Ids are
  monotonic and never reused, so an edited annotation keeps its number and a
  deleted one leaves a permanent gap.
- `selector` — verified unique at capture time. IDs are preferred; common
  generated class-name patterns (CSS modules, styled-components, hex hashes)
  are filtered out; falls back to a full `nth-of-type` path.
- `text` — whitespace-collapsed `textContent`, max 200 chars.
- `outerHTML` — truncated at 1,500 chars and sanitized at capture: `value` and
  `on*` attributes removed, URL query strings stripped, `data:` URIs and
  token-looking strings redacted to `…`, inline script/style contents emptied.
  `class` and `id` are kept verbatim. Treat as a structural fingerprint, not a
  complete copy.
- `page.url`, `page.referrer` — token-looking strings redacted to `…`; short
  query params (e.g. `?page_id=2`) survive.
- `styles` — ~20 computed properties (box model, typography, color, flex).
  Computed values, not authored values.
- `rect` — document coordinates (scroll offset already added), rounded.
  `scroll` is where the viewport was when the note was taken.
- `classes` — the full class list (minus the overlay's own `__claude*`
  internals), including hashed/utility classes the selector filtered out.

## Issue layout

`scripts/file-issues.mjs` owns the rendering — do not hand-assemble bodies.
Each issue comes out as:

1. The user's note, verbatim, first — it is the point of the issue.
2. The screenshot, if one was attached.
3. **Where** — page (linked), selector, tag, visible text, document position.
4. **Environment** — browser and version, platform, viewport, screen,
   language, time zone, colour scheme, reduced-motion, capture time.
5. A collapsed `<details>` block with the sanitized `outerHTML`, the computed
   styles table, and the raw user agent.
6. A footer crediting the plugin and the annotation number.

Values are escaped for table cells (pipes, newlines) and code fences are sized
to survive backticks in the content.

Titles: the user's `title` if they set one, otherwise the one Claude supplies
in `--meta`. The script falls back to the note's first sentence, truncated to
70 characters, so it can never produce an untitled issue — but that fallback is
a safety net, not the intended path.

## Why the screenshot needs a browser

GitHub has no attachment API. The upload endpoint behind drag-and-drop accepts
only a browser `user_session` cookie — personal access tokens, OAuth apps and
GitHub Apps are all rejected — and `cli/cli` has declined to work around it
(cli/cli#12960). The alternatives were weighed and rejected:

| Approach | Why not |
|---|---|
| Commit the PNG to a branch, link `raw.githubusercontent.com` | Camo fetches anonymously, so the image does not render in a **private** repo — it degrades to a broken image. Also adds commits and a branch to the user's repo. |
| `gh-image` and similar extensions | Genuinely headless, but they work by reading the `user_session` cookie out of the browser's keychain — a credential equivalent to the account password. Not a dependency to add on a user's behalf. |
| Release assets, gists | Same anonymous-fetch problem, plus gists mangle binaries. |

So the flow uses the browser the user already has, exactly once per batch, and
`https://github.com/user-attachments/assets/…` URLs — the only form that
renders inline regardless of repository visibility, inheriting the repo's own
access control.

### Minting the URLs

The new-issue form is used purely as a means of reaching the uploader:

1. One scratch tab → `https://github.com/<owner>/<repo>/issues/new`.
2. `find` the hidden `input[type=file]` belonging to the body editor.
3. Per screenshot: `upload_image` with the `imageId` from the `computer`
   screenshot and that `ref`, then poll the editor's text until a new
   `user-attachments` URL replaces the `Uploading…` placeholder. Diff against
   the previous snapshot to know which URL is new.
4. Close the tab. **Never submit; never type a title** — an empty form avoids
   any unsaved-changes prompt, and a native dialog would freeze the extension
   bridge.

`uploadToken` is only issued to users with write access to the target
repository, so a read-only collaborator will not get URLs this way.

### When it fails

The upload is the most fragile part of the flow, because it depends on
GitHub's editor markup. It is also the least important: an issue without a
screenshot is still a useful issue. On any failure — input not found, upload
never resolves, github.com not permitted for the extension — file the issues
without images and tell the user where the PNGs are on disk. Never retry in a
loop, and never let it block filing.
