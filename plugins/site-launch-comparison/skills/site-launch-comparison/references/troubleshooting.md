# Troubleshooting

Read the section you need — this file is a lookup table, not a linear guide.

- [Authentication](#authentication)
- [Bot challenge never clears](#bot-challenge-never-clears)
- [Blank, short, or wrong-looking captures](#blank-short-or-wrong-looking-captures)
- [Setup failures](#setup-failures)
- [Sites whose URLs don't line up](#sites-whose-urls-dont-line-up)
- [Very long or very heavy pages](#very-long-or-very-heavy-pages)
- [Output size and git](#output-size-and-git)
- [Config reference](#config-reference)

---

## Authentication

Staging sites are usually gated. Three common gates, three fixes — all live in
an `auth` block in `config.json`. Keys can be global, or scoped per side, which
matters because the staging site is typically protected and production isn't.

### HTTP basic auth

```json
"auth": {
  "before": { "basic": { "username": "staging", "password": "secret" } }
}
```

### Session cookies

Best when the site uses a login form or a shared-access link. Have the user log
in themselves in a normal browser and copy the relevant cookie, or extract it
from a shared preview URL.

```json
"auth": {
  "before": {
    "cookies": [
      { "name": "wordpress_logged_in_abc", "value": "...",
        "domain": "staging.example.com", "path": "/" }
    ]
  }
}
```

`domain` must match the host (no scheme). If the cookie doesn't take effect,
check whether the site sets it on a leading-dot domain (`.example.com`).

### WP Engine / Pressable / hosting-level password prompts

These are usually basic auth — use the basic block above. If instead the host
shows an HTML password form, log in once with a cookie and reuse it.

### Don't ask for passwords in chat

If a site needs credentials the user hasn't already put in the config, ask them
to add it to `config.json` themselves, or use a password manager / credential
tool if one is available. Don't invite secrets into the conversation.

---

## Bot challenge never clears

Symptoms: `RETRY … bot challenge did not clear`, or captures that are ~18 KB and
show "Checking your browser".

In order of what to try:

1. **Just run it again.** These challenges are rate-sensitive; a later run from
   the same session often sails through once the cookie is set.
2. **Raise the wait.** `PER_PAGE_LIMIT=160 BUDGET=140 python3 scripts/capture.py …`
   gives each page more room.
3. **Slow down.** Some WAFs escalate under rapid sequential requests. Capturing
   one viewport at a time (edit `viewports` down to one, run, then swap) spreads
   the load.
4. **Check it's not actually a block.** `curl -sS -o /dev/null -w "%{http_code}"
   -L <url>` from the same environment. A 403 that never becomes 200 means the
   host is blocking the datacenter IP outright, not challenging it. In that case
   the sandbox can't reach the site — say so plainly and offer to capture the
   reachable side only, or ask whether the user can allowlist.

Never work around a block by pulling the page through a third-party proxy or
cache. If the site won't serve the sandbox, that's the answer.

---

## Blank, short, or wrong-looking captures

**`page looks empty (height N)`** — the page genuinely rendered shorter than
`min_height` (default 600 px). Legitimate for sparse pages like an empty cart.
Lower it in config: `"min_height": 400`.

**Hero image missing or half-faded** — an on-scroll animation didn't finish.
The pre-scroll usually handles it; if a specific page is stubborn, raise the
settle time by editing the `page.wait_for_timeout(900)` near the end of
`capture()`, or accept it and note it to the user.

**A cookie banner or chat widget still shows** — add a selector to `HIDE_CSS` in
`scripts/capture.py`. Match on a stable attribute (`[id*="…"]`), not a hashed
class name. Delete the stale PNGs for that page so the rerun recaptures them:
the resume logic skips any file already above `MIN_BYTES`.

**Personalized or rotating content** (A/B tests, randomized hero, live counters)
will differ between runs for reasons that have nothing to do with the theme.
Worth flagging to the user rather than presenting as a migration difference.

**Different content, not different design** — staging often has stale or dummy
data. Say so when it shows up; the user may prefer a page with parity.

---

## Setup failures

**`playwright: command not found`** — `setup_browser.sh` writes
`/tmp/browser-env.sh` which adds `~/.local/bin` to PATH. Source it.

**`error while loading shared libraries: libXdamage.so.1`** and friends — the
local library prefix isn't on `LD_LIBRARY_PATH`. Source `/tmp/browser-env.sh`
in *this* shell; every call starts fresh, so sourcing it once earlier doesn't
carry over.

**`apt-get download` fails** — no access to the distro mirrors. If a system
Chromium exists (`which chromium chromium-browser google-chrome`), point
Playwright at it with `executable_path` in `chromium.launch()`. Otherwise report
that the environment can't run a browser.

**`sudo: … no new privileges`** — something invoked `playwright install-deps`.
Don't; `setup_browser.sh` deliberately avoids it.

---

## Sites whose URLs don't line up

Discovery intersects the two sites, so a redesign that changed permalinks yields
few or no shared paths. Pair them explicitly instead — `path` is the after side,
`before_path` the old URL:

```json
{ "slug": "04-product", "title": "Product — Widget",
  "before_path": "/shop/blue-widget/", "path": "/product/blue-widget/" }
```

Ask the user for the mapping rather than guessing. If the old site is gone
entirely, this skill doesn't apply — there's no before to capture. The Wayback
Machine is not a substitute; it renders inconsistently and shouldn't be
presented as the client's old site.

---

## Very long or very heavy pages

`capture.py` stops pre-scrolling at 45,000 px, which covers almost everything.
A page longer than that (endless-scroll archives) will capture the top portion.
Either accept it or point the config at a more representative URL.

Chromium can fail to composite extremely tall full-page screenshots. If a
specific page fails repeatedly with a screenshot error rather than a timeout,
capture it at a smaller viewport height, or crop to the top few thousand pixels
— the fold is where the theme change reads anyway.

---

## Output size and git

Full-page PNGs at two viewports for a dozen pages run to 100–200 MB. Before
writing into a repo, check:

```bash
git -C <repo> check-ignore -v <dest>/full/<something>.png || echo "NOT ignored"
```

If it isn't ignored, tell the user and suggest adding `full/` to `.gitignore`,
or writing the output outside the repo. The `web/` JPEGs are ~10% of the size
and are what the HTML actually loads, so keeping only those is a reasonable
middle ground.

---

## Config reference

```json
{
  "project": "Report title",
  "before": { "base": "https://old.example.com", "label": "Before", "sublabel": "old theme" },
  "after":  { "base": "https://example.com",     "label": "After",  "sublabel": "new theme" },
  "viewports": [
    { "id": "desktop", "width": 1440, "height": 1000, "mobile": false },
    { "id": "mobile",  "width": 390,  "height": 844,  "mobile": true }
  ],
  "out": "/tmp/shots",
  "scale": 1,
  "min_height": 600,
  "auth": { "before": { "basic": { "username": "", "password": "" }, "cookies": [] } },
  "pages": [
    { "slug": "01-home", "title": "Home", "path": "/" },
    { "slug": "02-product", "title": "Product", "path": "/product/x/", "before_path": "/shop/x/" }
  ]
}
```

| Field | Notes |
|---|---|
| `out` | Where PNGs accumulate. Keep it stable across runs — that's what makes resuming work. |
| `scale` | Device pixel ratio. `2` gives retina-quality shots at roughly 4× the bytes. |
| `min_height` | Below this, a capture is treated as failed. Lower for sparse pages. |
| `slug` | Filename stem and HTML anchor. Must be unique. |
| `before_path` | Optional; defaults to `path`. For migrations that changed URLs. |

Environment variables for `capture.py`:

| Var | Default | Purpose |
|---|---|---|
| `BUDGET` | 90 | Seconds before the run exits cleanly. Keep under the shell's cap. |
| `PER_PAGE_LIMIT` | 100 | Hard ceiling per page, enforced with SIGALRM. |
