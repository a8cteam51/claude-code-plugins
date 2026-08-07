---
name: site-from-host
description: Set up a local WordPress Studio site that mirrors a hosted Pressable or WordPress.com site — creates <siteurl>.local from the source site's domain, clones the given GitHub repo as wp-content, pulls that site's plugins and (optionally) its database with the team51 CLI, and optionally wires up BE Media from Production so missing uploads load from the same source site. Use when the user says "set up site <ID or URL> with <repo>", "spin up <domain> locally from <repo>", "make me a local copy of <site>", "studio site for <pressable site> using <repo>", "set up <site> locally with plugins", or any variant naming BOTH a hosted site (Pressable/WPCOM ID or URL) AND a repo. For a repo with no hosted counterpart, use this plugin's clone-new-site skill instead.
---

# Local Studio site from a hosted Pressable / WPCOM site

Builds a local mirror of a hosted site: `<siteurl>.local`, `wp-content` = the repo,
plugins pulled off the live host, and (optionally) media served from that same host.

Scripts live in `${CLAUDE_PLUGIN_ROOT}/scripts/`, alongside `scaffold.sh`. Delegate
every filesystem mutation, team51 call and Studio call to them — never re-implement a
step inline; that is what makes the workflow repeatable.

## Step 0 — collect inputs

From the user's message, extract:

- **Site** — a numeric Pressable/WPCOM site ID, or a domain (`example.com`).
- **Repo** — `owner/repo`, `https://github.com/owner/repo(.git)`, or `git@github.com:owner/repo.git`.

If either is missing, ask once via AskUserQuestion (free-text via "Other"). Never guess a repo.

Preflight (one command, before anything else):

```bash
for c in studio team51 git curl tar; do command -v "$c" >/dev/null 2>&1 || echo "MISSING: $c"; done
```

Stop and tell the user if anything is missing. `team51` needs a loaded identity — if
1Password is locked it will prompt in the terminal; that is expected, not an error.
The database pull additionally needs a team51 build with the
`*:download-site-database` commands (on `trunk` since July 2026); `team51 list`
shows them if the CLI is current.

## Step 1 — identify the site and pull its plugins

Always assume Pressable first. `pull-site-plugins.sh` does that, falls back to
WordPress.com only when Pressable reports the site as unknown, and reports which
host won along with the site's ID and URL.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/pull-site-plugins.sh" \
  --site "<site-id-or-domain>"
```

This is the slowest step and the one most likely to fail (SSH/SFTP/auth), so it runs
before anything touches disk. Read `RESULT_HOST`, `RESULT_SITE_ID`, `RESULT_SITE_URL`
and `RESULT_ARCHIVE` from its output. `RESULT_SITE_URL` is the source site's own URL, and it
is what both the `.local` domain and the media fallback are derived from — this is the site
being mirrored, which is often a dev or staging box rather than the public production domain.

Pass `--host pressable` or `--host wpcom` only if the user explicitly named the host.

If it fails, surface the script's output verbatim and stop. Do not retry with the
other host by hand — the script already made that decision deliberately.

## Step 2 — derive the local domain and confirm the plan

Derive a default `.local` domain from `RESULT_SITE_URL`: strip the scheme, strip a
leading `www.`, drop the final TLD label, and squash what remains into one lowercase
alphanumeric label.

- `https://progressiveshopper.com` → `progressiveshopper.local`
- `https://api.progressiveshopper.com` → `apiprogressiveshopper.local`
- `https://example.wpcomstaging.com` → `examplewpcomstaging.local`

Cross-check against sites that already exist so you never propose a taken domain:

```bash
studio site list --format json 2>/dev/null | jq -r '.[] | "\(.customDomain)\t\(.path)"'
```

Note the derivation is a default, not a rule. A Pressable dev/staging hostname
(`<name>-development.mystagingwebsite.com`) is not a real domain — propose the repo
name or the site's actual production domain instead, and say why.

Then ask in ONE AskUserQuestion call (batch the questions — this is the only
interactive stop in the workflow; the limit is 4, so keep it to these four):

1. **Local domain** — `<derived>.local` (recommended), plus a sensible alternative,
   Other for custom. The project name and folder are the domain minus `.local`, under
   `<studio-base>/`. Put the resolved path in each option's `preview` so the user sees
   where it lands. `<studio-base>` is the most common parent of existing site paths from
   the JSON above; fall back to `$HOME/Studio`. If the user needs a different base, they
   can say so via Other.
2. **WP_DEBUG_LOG** — Yes (recommended) / No.
3. **Media** — how missing uploads should be handled. Default to the site the plugins and
   database actually came from, i.e. `RESULT_SITE_URL` — NOT the "real" production domain,
   even when the source is a dev/staging box with an ugly hostname. Uploads have to match
   the database being imported; pointing at a different site serves media whose attachment
   paths the imported posts never reference. Name the actual host in the option label so the
   user can see which site it is:
   - `Use <RESULT_SITE_URL>` (recommended) — the site being mirrored
   - `Use a different origin` — ask for that URL as a follow-up. Offer this when a separate
     production site plausibly exists, and say plainly that its uploads may not match.
   - `No — I'll pull media myself` — skip the plugin entirely
4. **Database** — pull the hosted site's database?
   - `Yes` (recommended) — full content mirror; note dumps are often hundreds of MB
   - `No` — leave the fresh WordPress install

State the resolved target directory in plain text so the user can object before
anything is written.

## Step 3 — scaffold WordPress + repo + Studio site

Delegate to this plugin's `scaffold.sh` — the same script `clone-new-site` uses. It
downloads and SHA1-verifies WordPress, clones the repo as `wp-content`, patches
`wp-content/.gitignore` for Studio-generated files, registers the Studio site, and
installs + activates `safety-net`.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/scaffold.sh" \
  --target-dir "<resolved-target>" \
  --repo "<repo-as-given>" \
  --site-name "<project-name>" \
  [--debug-log]
```

Pass `--repo` exactly as the user gave it; the script normalises shorthand. Include
`--debug-log` only if the user opted in.

`safety-net` matters here: this site is a clone of production, and safety-net is what
stops it emailing real customers from a laptop. If the script reports it failed, say so
prominently.

## Step 4 — set the .local domain

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/set-local-domain.sh" \
  --target-dir "<resolved-target>" \
  --domain "<name>.local"
```

HTTPS is on by default, matching the existing Studio sites. This restarts the site and
prints `RESULT_URL`. macOS may prompt for a password when Studio registers the hostname.

## Step 5 — merge the pulled plugins

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/merge-plugins.sh" \
  --archive "<RESULT_ARCHIVE>" \
  --target-dir "<resolved-target>"
```

Repo-tracked plugins win: anything already in `wp-content/plugins` is skipped, so only
the plugins the repo does not ship get filled in. Report `RESULT_SKIPPED` — if a plugin
the user expected is on that list, it is because the repo already provides it.

Only pass `--overwrite` if the user explicitly asks to take production's copy of
everything, and warn them it clobbers repo-tracked plugin files.

## Step 6 — media fallback (only if the user chose an origin)

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/setup-media-fallback.sh" \
  --target-dir "<resolved-target>" \
  --production-url "<RESULT_SITE_URL, or the different origin the user gave>"
```

Pass `RESULT_SITE_URL` from Step 1 unless the user explicitly chose a different origin. Do
not substitute a "real" production domain you inferred from the repo or site name.

Installs and activates `be-media-from-production` into `wp-content/plugins` and
defines `BE_MEDIA_FROM_PRODUCTION_URL` in `wp-config.php`.

If the user chose "I'll pull media myself", skip this entirely — do not install the
plugin as a "helpful" extra.

## Step 7 — database (only if the user opted in)

This runs LAST, and the order is not negotiable. Importing replaces `wp_options`,
which includes `active_plugins` — so it deactivates `safety-net` and
`be-media-from-production`. It also needs production's plugin files already on disk
(Step 5), because the imported `active_plugins` list refers to them.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/pull-database.sh" \
  --site "<site-id-or-domain>" \
  --host "<RESULT_HOST>" \
  --target-dir "<resolved-target>" \
  --source-host "<RESULT_SITE_URL>" \
  --local-domain "<name>.local"
```

Pass `--host` from Step 1 — the script does not re-detect it. The script pulls the
dump, imports it, rewrites the source hostname to the local domain, and reactivates
whatever the import deactivated. Read `RESULT_POSTS`, `RESULT_USERS`,
`RESULT_REACTIVATED` and `RESULT_DUMP`.

Two things to know when reporting:

- Studio's importer already rewrites `siteurl`, `home` and most serialized content on
  the way in. The search-replace only mops up stragglers.
- On SQLite, `wp search-replace` reports a wildly inflated replacement count (millions).
  It is a miscount, not data damage. Judge the result by `RESULT_POSTS`/`RESULT_USERS`
  and a page load, never by that number.

Then load the homepage. A 500 with `Call to undefined function <something>_...` in the
active theme means the repo ships a child theme whose parent the source platform
provided (WPCOM installs parents like Seedlet outside wp-content). Read the parent slug
from the child's `style.css` `Template:` header and install it:

```bash
studio wp --path "<resolved-target>" theme install <parent-slug>
```

After this step the site holds real production user accounts and email addresses.
If `safety-net` is not active, say so loudly — that is the guard against mailing real
people from a laptop.

## Step 8 — local admin login

Ask once, at this point rather than in the Step 2 batch (that batch is already at the
four-question limit, and the answer only matters once the database is settled):

- `Yes — set admin / admin` (recommended) — the usual choice for a throwaway local mirror
- `No — leave the existing accounts alone`

Frame it with what is actually true of this site. If the database was imported, Studio's
generated password no longer works and the imported accounts' passwords are unknown, so
without this there is no way in. If it was not imported, Studio's credentials still work
and this is only a convenience.

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/ensure-admin-user.sh" \
  --target-dir "<resolved-target>"
```

The script updates the password and ensures the administrator role if `admin` already
exists, and creates the account otherwise. It is idempotent, and it never emails the
account. Read `RESULT_ACTION`, `RESULT_USERNAME` and `RESULT_PASSWORD`.

`--username`, `--password` and `--email` are available if the user wants something other
than `admin` / `admin`.

This is local-only, through `studio wp` against the site directory. Never run any
equivalent against the hosted site.

## Reporting

Emit a short summary (8-12 lines):

- Host the site was found on (Pressable / WPCOM) and its site ID
- Production URL
- Local URL from `RESULT_URL`, and the target directory
- Repo cloned into `wp-content`
- Plugins added (count) and skipped-because-already-in-repo (count, with names if few)
- `WP_DEBUG_LOG` state, safety-net state (active / NOT active)
- Media fallback: on (with the origin) or skipped
- Database: imported (posts/users counts, dump path) or skipped
- Admin credentials — whichever actually works now: the Step 8 login if it was set,
  otherwise Studio's from Step 3, and note that a database import invalidated those.
  Never print credentials the user cannot actually log in with.
- Whether any merged plugins show up as untracked in `wp-content`. Most team51 repos
  ignore `plugins/*` with explicit `!plugins/<name>` opt-ins, so usually nothing does —
  check with `git status` rather than asserting it either way.

On any non-zero exit, surface that script's stderr verbatim and stop. Do not attempt to
repair partial state. Recovery, if asked:

- Plugin pull failed → re-run Step 1; nothing was written to the target
- Scaffold failed → follow the clone-new-site skill's recovery guidance for scaffold.sh
- Domain failed → re-run `set-local-domain.sh`, or set the domain in the Studio app
- Merge failed → re-run `merge-plugins.sh` with the same archive; it is idempotent
- Media failed → re-run `setup-media-fallback.sh`
- Database failed → re-run `pull-database.sh`; pass `--dump <RESULT_DUMP>` if the dump
  already downloaded, so a large pull is not repeated
- Admin login failed → re-run `ensure-admin-user.sh`; it is idempotent

## Constraints

- Never run `curl`, `unzip`, `git clone`, `tar -x`, `studio site create`,
  `studio site set`, `studio import`, or `team51 *:download-site-{plugins,database}`
  outside these scripts.
- Never commit, push, or otherwise touch git history in the cloned repo.
- Never run destructive commands against the *hosted* site. This workflow is read-only
  with respect to production: it downloads plugins and reads the site URL, nothing else.
- Do not `--overwrite` plugins or install the media plugin without an explicit user choice.
