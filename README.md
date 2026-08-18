# Automattic Special Projects Claude Code Plugins

Claude Code plugins built by [Automattic's Special Projects team](https://specialprojects.automattic.com/) for WordPress development, security, and client work.

## Install

Add the marketplace once, then install whichever plugins you need:

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
/plugin install <plugin-name>@a8cteam51-claude-code-plugins
```

| Plugin | What it does | Trigger |
| --- | --- | --- |
| [plugin-review](#plugin-review) | Security review a WordPress plugin and produce an approve/conditional/reject report | `/plugin-review [slug or URL]` |
| [pr-feedback](#pr-feedback) | Work through unresolved GitHub PR review threads and apply the valid fixes | `/pr-addr-feedback <PR URL>` |
| [studio-repo-clone](#studio-repo-clone) | Back a local WordPress Studio site with a GitHub repo as its `wp-content` | `/studio-repo-clone:init` |
| [wpbakery-to-gutenberg](#wpbakery-to-gutenberg) | Convert WPBakery pages on a Studio site to Gutenberg block markup in place | `/wpbakery-to-gutenberg:wpbakery-batch`, natural language |
| [html-to-block-theme](#html-to-block-theme) | Turn static HTML/CSS/JS designs into a standards-driven WordPress block theme | Natural language |
| [figma-extract](#figma-extract) | Pull images and design context out of the current Figma selection | `/figma-extract:extract` |
| [page-annotator](#page-annotator) | Annotate a page in Chrome and file each note as a GitHub issue with a screenshot | `/page-annotator:annotate` |
| [poseidon-local](#poseidon-local) | Run the Poseidon plan/implement agents locally instead of via GitHub Actions | `/poseidon-plan`, `/poseidon-implement` |
| [site-launch-comparison](#site-launch-comparison) | Screenshot two versions of a site and build a side-by-side before/after report | Natural language |

## plugin-review

Automated WordPress plugin security review and risk assessment. Point it at any plugin slug, wordpress.org URL, or local plugin directory and get a structured report with an approve/conditional/reject recommendation.

**What's included:**

- **plugin-review skill** - Full security review workflow: static analysis, vulnerability database checks, manual code review, and risk rating

**What it checks:**

- PHPCS with WordPress security sniffs
- Grep-based scanning for 29 vulnerability signatures (PHP + JS)
- WPScan vulnerability database (optional, requires free API key)
- NVD CVE database
- WordPress.org metadata (installs, ratings, reviews, support forum)
- GitHub repository signals
- Manual code review of AJAX handlers, REST routes, shortcodes, file uploads

**Requirements:**

- PHP, Composer, PHPCS (auto-detected by dependency checker)
- `WPSCAN_API_TOKEN` environment variable (optional, for WPScan lookups — get a free key at https://wpscan.com/register)

```bash
# Install plugin review
/plugin install plugin-review@a8cteam51-claude-code-plugins

# Review a plugin by slug
/plugin-review akismet

# Review a plugin by URL
/plugin-review https://wordpress.org/plugins/contact-form-7/

# Review the plugin in the current directory
/plugin-review
```

## pr-feedback

Address unresolved PR review comments directly from Claude Code. Point it at any GitHub PR URL and it fetches open review threads, evaluates whether the feedback is valid, applies clear fixes automatically, and surfaces questionable feedback for your decision.

**What's included:**

- **pr-addr-feedback command** - Slash command that processes unresolved review threads one by one

**What it does:**

- Fetches unresolved review threads via GitHub GraphQL API
- Reads the relevant code context for each comment
- Evaluates whether feedback is technically valid or a style preference
- Applies valid fixes automatically with minimal changes
- Prompts you on questionable feedback before acting
- Prints a summary table of all actions taken

**Requirements:**

- `gh` CLI authenticated with access to the target repo

```bash
# Install pr-feedback
/plugin install pr-feedback@a8cteam51-claude-code-plugins

# Address feedback on a PR
/pr-addr-feedback https://github.com/org/repo/pull/123
```

## studio-repo-clone

Back a local WordPress [Studio](https://developer.wordpress.com/studio/) site with a GitHub repo as its `wp-content`. Either scaffold a brand-new site from scratch, or convert an existing site's `wp-content` into a clone while preserving its uploads, SQLite database, and installed plugins and themes.

**What's included:**

- **`/studio-repo-clone:init` command** - Explicit slash command with `<owner/repo|git-url> [project-name]` arguments
- **clone-new-site skill** - Natural-language trigger for phrases like "spin up a Studio site from <repo>"
- **clone-into-existing-site skill** - Converts an already-working site's `wp-content` into a clone, preserving uploads, the SQLite database, the `db.php` drop-in, the `sqlite-database-integration` mu-plugin, and installed plugins/themes
- **scaffold.sh / clone-into-existing-site.sh** - Deterministic bash scripts that do all filesystem work; the agent only gathers inputs
- **install-safety-net.sh** - Installs and activates [safety-net](https://github.com/a8cteam51/safety-net) into every site it sets up, so a fresh clone of a production `wp-content` can't email real users or reach Jetpack from a developer's laptop

**What it does (new sites):**

- Preflights repo access with `git ls-remote` so private-repo auth failures surface before any download
- Downloads `wordpress.org/latest.zip` and SHA1-verifies the archive
- Stages WordPress + the cloned repo (as `wp-content`) in a temp dir, then moves into the target as the last step
- Patches `wp-content/.gitignore` to ignore Studio-generated files (`/database`, `/db.php`, `/index.php`), anchored to the wp-content root so unrelated `index.php` files in themes/plugins are unaffected
- Creates and starts a Studio site at the target via `studio site create` (SQLite, default WP/PHP versions)

**What it does (existing sites):**

- Confirms the exact set of moves with you before mutating anything
- Moves the current `wp-content` aside, clones the repo in its place, then moves `uploads/`, `database/`, `db.php`, and `mu-plugins/sqlite-database-integration/` back as whole units
- Restores `plugins/` and `themes/` child by child, so plugins and themes committed to the repo survive and only conflicting names are overwritten by the local copy

**Requirements:**

- `curl`, `unzip`, `git`, and `studio` (Studio CLI 1.8+) on `$PATH`
- A working git credential helper for private repos (e.g. `gh auth login` or SSH agent)

```bash
# Install studio-repo-clone
/plugin install studio-repo-clone@a8cteam51-claude-code-plugins

# Scaffold a site from a repo shorthand
/studio-repo-clone:init Automattic/some-repo

# Scaffold with an explicit project name
/studio-repo-clone:init Automattic/some-repo my-cool-project

# Convert an existing site — trigger the skill in natural language:
# > point my local site my-cool-project at Automattic/some-repo
```

## wpbakery-to-gutenberg

Convert a WPBakery (Visual Composer) page on a local WordPress [Studio](https://developer.wordpress.com/studio/) site to Gutenberg block markup in place. Hand it a page URL on a running Studio site and it resolves the URL to a post ID, extracts WPBakery's compiled CSS from the rendered page, walks the shortcode tree using a documented mapping table, validates the converted blocks against the site's real block editor, and writes the result back as a new revision.

**What's included:**

- **wpbakery-to-gutenberg skill** - Natural-language trigger for phrases like "convert this page", "migrate this page to blocks", or "convert WPBakery on <URL>"
- **`/wpbakery-to-gutenberg:wpbakery-batch` command** - Batch mode over a whole site: discovers candidate pages, asks you to scope the run, then dispatches **one subagent per page** so the main context only ever holds the candidate list and per-page summaries — never the post content or block markup — and writes a single combined report
- **references/shortcode-mappings.md** - Source of truth for `vc_*` shortcode → block mappings, including attribute decoders for `link=`, `font_container=`, and `css=`
- **scripts/update-post-content.php.tmpl** - Sentinel-verified PHP write template, staged inside the site directory to work around `studio wp eval-file -` silently no-op'ing on stdin heredocs

**What it does:**

- Resolves the page URL to a post ID via `url_to_postid` and verifies the post actually contains `[vc_` shortcodes before doing any work
- Fetches the rendered page and extracts WPBakery's `<style data-type="vc_shortcodes-custom-css">` block so per-shortcode `.vc_custom_*` styling can be applied to the converted block attributes
- Walks the shortcode tree depth-first, applying the mappings table and decoding `link=` / `font_container=` / `css=` attributes
- Downgrades unknown `vc_*` shortcodes to `core/html` with a `TODO(wpbakery-migration)` comment rather than inventing mappings
- Validates the converted markup via the Studio MCP `validate_blocks` tool (runs each block through the editor's real `save()` and returns the expected HTML for mismatches), with auto-fix from the expected HTML and a two-call ceiling
- Captures the pre-write revision ID so the rollback instructions in the final report are unambiguous
- Writes back via a staged PHP script with a sentinel echo, re-reads the post to confirm `<!-- wp:` markup landed, and smoke-tests the rendered page

**Requirements:**

- `studio` (Studio CLI 1.8+), `curl`, `perl` on `$PATH`
- Studio MCP server registered in Claude Code (one-time: `claude mcp add --scope user wordpress-studio -- studio mcp`) for the `validate_blocks` validation pass
- The target Studio site must be running

```bash
# Install wpbakery-to-gutenberg
/plugin install wpbakery-to-gutenberg@a8cteam51-claude-code-plugins

# Then trigger the skill in natural language with a page URL on the running site:
# > convert this page: http://localhost:8881/about-us/

# Or batch-convert a whole site
/wpbakery-to-gutenberg:wpbakery-batch ~/Studio/my-site
```

## html-to-block-theme

Convert a set of static **Claude Design** HTML/CSS/JS files into a standards-driven **WordPress block theme** on a local [Studio](https://developer.wordpress.com/studio/) site. The agent maps the design to WordPress primitives — templates, template parts, block patterns, `theme.json`, block styles, and page content — rather than reproducing it with hand-written CSS. It plans a blueprint first, then builds section by section and refines against the originals in a real browser.

**What's included:**

- **html-to-block-theme skill** - Natural-language trigger for phrases like "build a block theme from the designs in ./design"
- **blueprint-analyzer / section-builder agents** - Subagents for the planning pass and per-section build, keeping design HTML out of the main context
- **scripts/** - `scaffold-custom-block.sh`, `serve-html.sh`, `standards-audit.sh`, and a sentinel-verified `write-page-content.php.tmpl`
- **Bundled Playwright MCP** - Shipped via the plugin's `.mcp.json`; no separate install step

**What it does:**

- **Plans before building** — analyses every HTML file and its linked CSS/JS, then writes a blueprint to `<site-path>/.h2bt/blueprint.md` and surfaces it for review
- **Makes `theme.json` the source of truth** — design tokens (colour, typography, spacing, layout widths) are unified across the whole design set
- **Minimises custom CSS** — styling goes through block supports first, then block style variations registered with `register_block_style()`; any block CSS is split per block type under `assets/css/blocks/` and loaded on demand with `wp_enqueue_block_style()`, never as one monolithic stylesheet. Hand-written CSS is a last resort and every rule is reported
- **Scaffolds build-less custom blocks** — `block.json` + PHP `render.php` + vanilla `view.js` / the Interactivity API, with no node/webpack step
- **Refines against the originals** — screenshots the original design and the WordPress output at matched viewports via Playwright, then iterates
- Reports per-file fidelity, residual drift, custom CSS used (and why), and custom blocks created (and why)

**Requirements:**

- `studio` (Studio CLI) on `$PATH`, and a Studio site with a minimal block-theme scaffold the agent can take over (it can scaffold one via the Studio MCP if absent)
- Studio MCP server registered: `claude mcp add --scope user wordpress-studio -- studio mcp`
- Node.js / `npx` available (the bundled Playwright MCP runs via `npx -y @playwright/mcp@latest`)

```bash
# Install html-to-block-theme
/plugin install html-to-block-theme@a8cteam51-claude-code-plugins

# Then trigger the skill in natural language:
# > Build a block theme from the designs in ./design on my Studio site my-theme-dev.
```

## figma-extract

Extract images and design context from the **current Figma selection** straight out of Figma desktop's local **Dev Mode MCP** server — no Figma API token, no cloud round-trip.

**What's included:**

- **extract-figma-assets skill** - Natural-language trigger for phrases like "extract the assets from this Figma frame"
- **`/figma-extract:extract` command** - Slash command taking `[node-id|figma-url] [--out <dir>] [--context]`
- **scripts/extract-figma-assets.mjs** - Standalone Node script; uses only Node built-ins, so there is no npm install

**What it does:**

Writes to an output directory (default `./figma-extract`). By default it saves **images only**; pass `--context` (alias `--full`) to also save the design-context files.

| File | Contents | When |
| --- | --- | --- |
| `assets/*` | Every referenced image — PNG, JPG, GIF, WEBP, SVG — original filenames preserved | always |
| `assets/manifest.json` | Maps each design-context variable (`constName`) → filename, kind (`raster`/`svg`), source URL, relative path | always |
| `screenshot.png` | A render of the selection | unless `--no-screenshot` |
| `code.tsx` | Figma-generated reference code (trailing LLM-instruction text stripped) | `--context` |
| `variables.json` | Published Figma variables for the selection | `--context` |
| `metadata.xml` | The node's structural metadata | `--context` |

It opens an MCP session to `http://127.0.0.1:3845/mcp`, calls `get_design_context` / `get_variable_defs` / `get_metadata` / `get_screenshot`, parses the `const imgFoo = "..."` declarations out of the returned code, and downloads each asset (4 in parallel, with per-asset timeouts and a cache check so re-runs are cheap). A selection referencing no placed images is still a success.

**Requirements:**

- **Figma desktop** running with **Dev Mode MCP enabled** (Figma → Preferences → *Enable Dev Mode MCP server*)
- A frame/node selected in Figma, or an explicit node id / URL
- **Node.js 20+** on `$PATH`

```bash
# Install figma-extract
/plugin install figma-extract@a8cteam51-claude-code-plugins

# Current selection → ./figma-extract
/figma-extract:extract

# A specific node, into a chosen directory
/figma-extract:extract 1:23 --out ./design
```

## page-annotator

Annotate the web page you're viewing in Chrome and file each note as a GitHub issue — with a screenshot. Click elements, leave notes ("this button wraps", "wrong colour on hover"), hit **Create GitHub issues**, and each annotation becomes its own issue carrying a screenshot of the element ringed in context plus the selector, markup, and browser details. A front-end QA companion: point at the problem instead of describing it. **One annotation → one issue.** The plugin does not read or change your code.

**What's included:**

- **annotate skill** - `/page-annotator:annotate`, plus natural-language triggers like "QA this page and raise tickets"
- **page-annotator.user.js** - The dependency-free vanilla-JS overlay, installed as a Tampermonkey userscript; makes no network requests and talks to Claude through a hidden DOM node
- **scripts/** - `file-issues.mjs` and `serve-userscript.js`

**What it does:**

- Probes for the userscript, arms the overlay, and polls a hidden JSON node until you click **Create GitHub issues**
- Screenshots each annotated element in capture mode — scrolled into view, Claude's own toolbar and pins hidden, the element ringed
- Previews the issues and **waits for your approval** before filing anything, then writes issue numbers back so filed pins turn green and are skipped by later batches
- Remembers the target `owner/repo` per site, prefilling from the working directory's git remote when it can

Because it drives your real browser session, logged-in states, feature flags, and real data all work. One GitHub tab opens per batch to attach screenshots — GitHub has no API for issue attachments, and the plugin will not read your session cookie out of your keychain to fake one.

**Requirements:**

- The [Claude in Chrome](https://claude.com/chrome) extension, connected to Claude Code, with permission for the site you're annotating **and for `github.com`**
- [Tampermonkey](https://www.tampermonkey.net/) (or Violentmonkey) — Claude walks you through installing the userscript the first time, and re-prompts when the plugin ships a newer version
- The [`gh` CLI](https://cli.github.com) authenticated, with write access to the target repository

**Note:** annotation data is published to an issue tracker — element text, markup, page URL, and browser details all land in the issue, publicly if the repo is public. The overlay scrubs form values, URL query strings, and token-like strings from captured markup, but visible text is kept verbatim.

```bash
# Install page-annotator
/plugin install page-annotator@a8cteam51-claude-code-plugins

# Annotate the active tab
/page-annotator:annotate

# Target a specific tab, or prefill the repository
/page-annotator:annotate staging.example.com
/page-annotator:annotate a8cteam51/example
```

## poseidon-local

Run the [Poseidon](https://github.com/a8cteam51/poseidon-actions) **plan** and **implement** agents locally in your Claude Code session instead of via GitHub Actions — on the model you choose. In CI each agent is a composite action wrapping `anthropics/claude-code-action` with a fixed model and a hard turn cap; this plugin runs the same agents in your session, so you pick the model with `/model` and there is no turn cap.

**What's included:**

| Command | Ports | What it does |
| --- | --- | --- |
| `/poseidon-plan [owner/repo] <issue> [site:<blog-id>]` | `issue-plan` | Reads the issue, gathers site context via the `team51` MCP, posts a build-ready `### Poseidon plan` comment |
| `/poseidon-implement [owner/repo] <issue>` | `issue-implement` | Reads the approved plan, implements on `fix/issue-N` (Git Flow aware), lints, opens the PR(s) |

**Always up to date — nothing cached.** Neither skill stores the Poseidon instructions. Each run fetches the upstream `action.yml` live from `poseidon-actions@trunk` with `gh` and follows both embedded instruction blocks, so behaviour always tracks the deployed Poseidon version.

**Local deltas vs CI:**

- **MCP** — your local `team51` MCP replaces the OpsOasis credential-brokering gateway
- **Identity** — you act as your own `gh` user (CI used the `t51eng-poseidon[bot]` App)
- **Questions** — if the plan agent needs clarification it asks you in-session and continues, instead of posting a questions comment and waiting for a label re-add
- **Dropped** — run-tokens, progress pings, cost telemetry, `poseidon-pr` labeling, and the `pr-review-fix` auto-chain
- **Not ported** — `issue-implement-v2` (Pressable clone + Playwright verify)

**Requirements:**

- `gh` authenticated with access to **`a8cteam51/poseidon-actions`** (to fetch the instructions) and to the target repo
- For site-specific tickets: the `team51` MCP server (`mcp__team51__wpcom_*` / `pressable_*`)
- `poseidon-implement` must run from inside a clone of the target repo

```bash
# Install poseidon-local
/plugin install poseidon-local@a8cteam51-claude-code-plugins

# Plan an issue (set your model first with /model)
/poseidon-plan a8cteam51/some-repo 45

# Implement the approved plan, from inside a clone of the repo
/poseidon-implement 45
```

## site-launch-comparison

Capture full-page **before/after screenshots of two versions of a website** and build a self-contained, side-by-side HTML report you can open, scroll, and hand to a client. Built for relaunches — re-themes, redesigns, replatforms — and equally useful for routine staging-vs-production design QA. Stack-agnostic: WordPress/WooCommerce, a static site, or anything else serving HTML.

**What's included:**

- **site-launch-comparison skill** - Natural-language trigger for phrases like "compare our staging and production sites" or "screenshot the before and after"
- **scripts/setup_browser.sh** - Cross-platform headless Chromium install; falls back to unpacking Chromium's shared libraries into a local prefix when there's no root
- **scripts/discover_pages.py** - Intersects both sites' sitemaps and nav, keeps only URLs that return 200 on both, and ranks them so you get one of each template type
- **scripts/capture.py / capture_all.sh** - Resumable full-page capture at desktop and mobile viewports
- **scripts/build_report.py** - Assembles the side-by-side HTML report
- **references/troubleshooting.md** - Auth, bot blocks, mismatched URLs, output size

**What it does:**

- Proposes a page list for you to approve before spending time capturing anything
- Captures each page full-height at 1440px and 390px, with a viewport toggle in the report
- Waits out "Checking your browser" bot-check interstitials and validates page height before saving, so a challenge page never gets shipped as a screenshot
- Suppresses cookie banners, chat widgets and newsletter modals, and pre-scrolls each page so lazy-loaded images actually render
- Merges pages served at several URLs into one row (`/shop/` and `/products/`, `/cart/` and `/checkout/` when empty)
- Flags pages whose before and after are pixel-identical — usually a page the migration missed
- Resumable and budget-limited, so a long capture survives agent shells that cap each call at a couple of minutes

**Requirements:**

- Python 3.9+ and `pip install playwright pillow` (the setup script does this)
- macOS, Linux, or WSL. On a rootless Linux sandbox `apt-get` is used to fetch Chromium's libraries without installing them system-wide
- Roughly 10–20 seconds per screenshot. A 14-page, two-viewport run takes about 15 minutes and produces 100–200 MB of PNGs, so keep the output out of git or pass `--no-full`

```bash
# Install site-launch-comparison
/plugin install site-launch-comparison@a8cteam51-claude-code-plugins

# Then trigger the skill in natural language:
# > We just re-themed the client's store. Old site is at https://staging.example.com,
# > new one is live at https://www.example.com. Grab before/after screenshots of the
# > main pages and put them in one page I can send the client.

# Or name the pages yourself and it skips discovery:
# > Compare https://staging.example.com against https://www.example.com on
# > /, /shop/, and /about/. Desktop only.
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
