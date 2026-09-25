---
name: publish-design-options
description: Package the design options from this session behind one private Spacefast link for partner review
---

# Publish design options

Package the completed HTML design options into a single private Spacefast space
with a minimal index page, and hand the user one shareable Access URL.

Arguments (optional): `$ARGUMENTS` — a directory containing the options, or an
explicit list of entry HTML files. Supplying a path is the most reliable
invocation; without it, discovery is inferred and must be confirmed.

Read the `publish-to-spacefast` skill before publishing. Do not
reimplement its API handling — this skill delegates all publish mechanics to
the Spacefast CLI.

**Standing constraints — do not deviate without being asked:**

- The space is **private**. Report the Access URL only. Never run a public
  share grant.
- **One space per project**, reused across runs; each run is a new immutable
  version.
- Never handle a token. The CLI reads its own credential store. Do not read the
  macOS keychain, `~/.spacefast/`, or any auth file.
- Never fall back to an anonymous publish — anonymous receipts carry no
  `data.access`, which breaks the private-link requirement. No credential means
  stop.

---

## 1. Resolve the scope root

`$ARGUMENTS` if given, else `git rev-parse --show-toplevel`, else `$PWD`.
Never `$HOME`, never `/`.

## 2. Discover the options

Cheapest, highest-precision signal first. Stop at the first tier that yields
candidates.

1. **An explicit path or file list in `$ARGUMENTS`.** Skip scanning entirely.
2. **HTML entry files written or edited earlier in this session.** This command
   runs at the end of the design work (this plugin's `create-design` skill), so
   the transcript already names them. Prefer these; use the filesystem only to
   fill gaps.
3. **Scoped scan**, only if 1 and 2 are empty:

```bash
find "$ROOT" -type f -name '*.html' -maxdepth 4 \
  -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/dist/*' \
  -newermt '-24 hours'
```

Cap at 20 candidates. Over that, stop and ask for a path.

**Classify the shape and say which one was detected:**

| Shape | Signal | Treatment |
|---|---|---|
| folder-per-option | two or more sibling dirs each holding `index.html` | each dir is one option |
| flat siblings | several `*.html` in one dir sharing assets | each file is one option |
| one multi-page site | an entry file whose `href`s resolve to other candidates | **one option, not N** |

The disambiguating test is cross-linking: separate options never link to each
other, pages of one site do. Grep each candidate's `href`s against the other
candidates. If it resolves as one site, say "this is one site, not N options"
and get a decision before continuing.

## 3. Name the options

In precedence order, and state which source was used for each:

1. **The direction names from this session's conversation** — the visual-thesis
   labels. These are the names the user thinks in and the only ones meaningful
   to a reviewer.
2. Each entry file's `<title>`.
3. The directory or file slug — a fallback, and mark it as one.

## 4. Confirmation gate — mandatory

Print a table: proposed name | name source | entry path | last modified. Accept
inline renames. Require explicit approval before staging.

Do not offer or honour a flag that skips this gate. Every other failure in this
flow is loud; this is the only step that can succeed and be wrong. Publishing a
stale option folder from a previous run returns a perfectly normal-looking
Access URL, behind a URL identical to last time's, that nobody can tell is wrong.

## 5. Auth preflight

Before any staging work, so failure is cheap:

```bash
sf whoami --json
```

`sf` is installed at `/usr/local/bin/sf` as a shim that pins Node 20 — the
default `node` here is v18, which crashes the CLI (`toSorted is not a
function`), and the standalone Bun binary warns that this CPU lacks AVX. If
`sf` is ever missing, fall back to
`PATH="$HOME/.nvm/versions/node/v20.20.2/bin:$PATH" npx -y spacefast@0.4.1 …`.

If `whoami` fails, stop and ask the user to re-authenticate. Do not attempt an
anonymous publish.

## 6. Space identity

Walk up from the scope root looking for `.spacefast/space.json`. Cross-check
with `sf spaces list`. Also check for a publish receipt earlier in this
conversation.

- Space found → publish a new version to that `spaceId`.
- No space → confirm with the user before creating one.

After a successful publish, write only the non-secret form at the **project
root** (never in the staging dir):

```json
{"space":"<spc_id>"}
```

Never write `state.json` or any credential file. Mention once that in a git repo
this file should be gitignored or committed deliberately — do not edit
`.gitignore` automatically.

## 7. Stage into a fresh scratchpad directory

Use a new directory under the session scratchpad, not a directory inside the
project. Two reasons, both load-bearing:

- The publish root becomes a provable whitelist of exactly what was copied,
  rather than "a repo minus exclusions." No ancestor `.env` or `.git` can leak
  by construction.
- A fresh directory per run makes stale carryover impossible. A persistent
  in-project staging dir would let run 2's third option ship inside run 3,
  invisibly, behind an identical URL.

**Layout mirrors the source shape.** Per-option directories stay directories,
each with its entry file as `index.html`:

```
stage/
  index.html            # generated
  01-<slug>/index.html + siblings
  02-<slug>/...
```

Flat siblings stay flat, so a shared `styles.css` is neither duplicated nor
orphaned. Dereference symlinks (`cp -RL`) or reject them — the publish walker
hard-fails on symlinks. Exclude `.DS_Store`. Print the absolute staging path in
the final report.

## 8. Link audit — never rewrite the options' HTML

Strip HTML comments first — a commented-out link is not a real dependency and
will otherwise fail the audit. Then walk every local `href` and `src` in the
staged tree and assert the target file exists, compared **case-sensitively** (APFS is case-insensitive and will hide a
`Styles.css` vs `styles.css` bug that 404s once published).

| Pattern | Action |
|---|---|
| `file://` path | **hard fail** — always broken once published; list every occurrence |
| `<base href>` | **hard fail** — almost certainly wrong after staging |
| root-relative `/styles.css` | report; breaks under per-option dirs. Offer flat staging or stop |
| `../shared/tokens.css` | fix by raising the staging root to the common ancestor — never by copying assets upward |
| `https://` CDN link | warn only, never block (the house samples use Google Fonts) |

If paths do not survive a straight copy, report and stop. Rewriting the
options' markup is where silent, plausible-looking damage happens.

## 9. Choose the index template, then generate the page

Before filling anything, check whether a template was already chosen for this
project earlier in the session (this run, or a prior publish/design run —
check for a `.design-template` file at the scope root resolved in step 1,
whether or not that root happens to be a `projects/<slug>/` folder). If so,
reuse it without re-asking.

Otherwise, read `${CLAUDE_PLUGIN_ROOT}/skills/publish-design-options/templates/
MANIFEST.md`, list every template there (name + one-line description) with the
one marked **Default** pre-selected, and ask the user which to use for this
partner share. A bare confirmation ("yes" / enter / "the default") picks the
default — this is a lightweight confirm, not a multi-question gate, and stays
that way even as more templates are added.

Fill the chosen template (today, only `${CLAUDE_PLUGIN_ROOT}/skills/
publish-design-options/templates/design-options-index.html`, the `deck`
template) and write the
result as `index.html` at the staging root. It follows the team's
presentation pattern: full-bleed blue cover with the Automattic wordmark and
an oversized tight-tracked headline, then a numbered table of contents in
black on white, then a provenance footer. Do not restyle it per run —
consistency across runs is the point. Change it only when the template
itself changes. This is the same template `create-design` fills for
`directions/index.html`, so a project's local nav page and its published
partner-facing page match.

Tokens to substitute, all of them required:

| Token | Value |
|---|---|
| `{{PROJECT}}` | Project or client name — appears in `<title>` and under the cover headline |
| `{{VERSION}}` | `Version 1.0`, or the round of review this is |
| `{{DATE}}` | Long-form date, e.g. `January 1, 2026` |
| `{{COUNT}}` | Number of options |
| `{{OPTIONS}}` | One `<li>` per option, in the shape below |
| `{{PROVENANCE}}` | `<dt>`/`<dd>` pairs: a `Published` timestamp, then one per option naming its absolute source path |

Each option is one list item — the numeral is generated by CSS, so do not write
one:

```html
    <li><a href="01-slug/index.html">
      <span>
        <span class="toc__name">Option name</span>
        <span class="toc__note">One line on what this direction does.</span>
      </span>
    </a></li>
```

HTML-escape every substituted value, and assert no `{{` remains in the output
before continuing. Keep each `toc__note` to one line — what the direction does,
in the language used with the user, not a feature list.

The provenance block is the highest-value element on the page: every run sits
behind an identical-looking URL, so the timestamp and source paths are the only
thing that makes a stale or wrong publish visible to someone looking at it.

## 10. Verify before publishing

Serve the staging directory over loopback HTTP and check it in a browser — not
`file://`, which masks exactly the case-sensitivity and root-relative failures
that matter here.

Add a `launch.json` entry **in the working directory, never in the staging
dir** — a `.claude/` folder inside the stage would be published — and root the
server at the stage with `--directory`:

```json
{ "name": "design-options", "runtimeExecutable": "python3",
  "runtimeArgs": ["-m","http.server","--directory","<STAGE>","8731"], "port": 8731 }
```

Then `preview_start` it.

1. Index: `read_page` and assert exactly N option links, each resolving.
2. Each option: `read_network_requests` and **abort on any same-origin non-2xx.**
   This is the load-bearing check — a missing stylesheet renders an unstyled
   page that a screenshot cannot distinguish from an intentional brutalist
   direction. Third-party CDN failures warn only.
3. `read_console_messages` with `onlyErrors` per option; surface what it finds.
4. One screenshot per option as a human-checkable receipt.

Any same-origin 4xx or 5xx aborts before publish. If loopback is unavailable,
fall back to the static link audit from step 8 and say which mode ran.

## 11. Pre-publish assertion

```bash
find "$STAGE" \( -name .spacefast -o -name .git -o -name '.env*' \
  -o -name node_modules -o -name '*.zip' \) -print -quit
```

Must be empty. Otherwise abort.

## 12. Publish

One CLI call. Updating an existing space:

```bash
sf publish "$STAGE" --space "$SPACE_ID" --team allan-team --wait --json -y \
  -m "Design options: <names> — <date>"
```

Creating the space the first time — drop `--space`, add:

```
--access private --name "<project> — design options"
```

`--wait` follows the `data.next` continuation loop, so there is no poll logic to
write here.

**The Bash sandbox blocks outbound network.** This step needs the
sandbox-disabled path. On a connect timeout to `api.spacefast.com`, say so
rather than retrying.

## 13. Get the shareable link, then report

**`sf publish` does not return `data.access`.** The `publish-to-spacefast`
skill claims owned publishes carry a reusable Access URL; this CLI emits none,
and the bare live URL returns **403** to anyone outside the team. Do not
report the live URL as though a partner can open it.

What actually exists: Spacefast **auto-creates a Link named `Open`** on the
space at first publish, carrying `page.view`, `comments.read`, and
`comments.write`, with no expiry. It survives later publishes. That is the
partner link — read it, never create one:

```bash
sf share link ls --space "$SPACE_ID" --team allan-team --json 2>&1
sf share link copy <lnk_id> --space "$SPACE_ID" --team allan-team --show-secret --json 2>&1
```

Two quirks, both verified: `share link ls` does **not** accept `--show-secret`
(only `copy` returns the URL), and `copy --json` writes its JSON to **stderr**,
so `2>&1` is required or you get an empty result. Pick the active link named
`Open`; if it is missing or revoked, say so and stop rather than minting a
replacement — creating a grant widens access and is the user's call.

Then report:

- The **share link URL** — this is the one to send to partners. It works with
  no sign-in; the token in the query string sets a session cookie, after which
  same-origin assets load normally.
- The Live URL and immutable version URL as metadata, each labelled
  **team-only, 403 for partners**.
- `data.activation.outcome` — what decides whether the version is serving.
  Never infer liveness from version status.
- The option list as published, and the staging path.
- Warnings: CDN dependencies, root-relative paths, size diagnostics.
- One sentence worth passing on: the link is link-equals-access. Anyone who
  receives it gets in, including whoever a Slack channel forwards it to. It has
  no expiry; `sf share link revoke <id>` is how it ends.
- Republishing the same bytes returns the **same** version ID — content is
  deduplicated. That is not a failure; it means nothing changed.

Never print API keys, space keys, or state files. The share link itself is the
deliverable and is meant to be reported.

## 14. On failure

Report the problem document's `code`, `type`, and `requestId`, and follow its
documented recovery.

Before retrying a publish, re-read `.spacefast/space.json` and `sf spaces list`.
A publish that names no existing `spaceId` **creates a new space**, so a blind
retry after an uncertain write silently duplicates the project's space.
Identical files alone do not make a retry safe.

## Out of scope

Creating or widening grants — the command reads the auto-created `Open` link
and never mints one. Reading the keychain or auth files. Anonymous
publish and claim flows. Rewriting option HTML to repair paths or inject a
`<base>`. Reimplementing the publish API, manifests, or resumable uploads.
Custom domains, rollback, `_redirects` / `_headers` / `sf.jsonc`. Editing
`.gitignore` or touching git state. Screenshot thumbnails on the index page.
Design critique or accessibility checks — the `create-design` skill already
ran those. Slack or email delivery of the link.
