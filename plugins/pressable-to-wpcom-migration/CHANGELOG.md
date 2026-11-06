# Changelog

## [Unreleased]

### Changed
- The audit checks what a site serves from outside wp-content, which the copy
  does not bring (`web_root.php` → `webroot.json`). Found by hand on
  eagleman.com, where the theme moves PDFs tagged "papers" to
  `/srv/htdocs/papers` and 98 redirect rules point old uploads paths there.
  It reports:
  - folders and files in the web root;
  - content links and attachments that point there;
  - upload paths moved away from wp-content;
  - redirect rules from file paths, which never run on WordPress.com because
    it serves `/wp-content/` paths without WordPress;
  - theme and mu-plugin code that builds paths outside wp-content.

  New steps copy the files before the window (`platform.web-root`), again
  after the freeze (`sync.web-root`), and check them on the copy
  (`verify.web-root`, with `web_root_compare.py`). The copy is made as on
  eagleman.com: `web_root_fetch.php` downloads each file from the source's
  public URL into the same path on the target, and fetching an old redirected
  path places the file at that path, which is how the 98 redirects were kept.
  It writes files on the target, so it runs after a yes.
- The audit lists repo files at the wp-content root (`webroot.repo-files`).
  The copy brought eagleman.com's README.md, LICENSE and composer files into
  the new site's wp-content, publicly readable (dotfiles there answer 403).
  `sync.web-root` deletes them, and `deploy_check.py allowlist` now gives the
  plain `.deployignore` lines that keep root tooling out (`exclude_lines`),
  instead of assuming a WordPress.com deploy leaves it out (eagleman#331).
- `cut.domain`: in a Pressable zone the old `atomic-domain` TXT cannot be
  replaced (Pressable manages it and hides it), and adding the new value beside
  it fails with "multiple domain verification TXT records". The new values go
  in the WordPress.com zone, and primary is set once the name servers point
  there or the domain is off the Pressable site.
- `dns.export` writes each TXT value as one quoted string: WordPress.com's
  BIND import rejects the split form that DKIM keys over 255 characters use.
- Connecting a domain adds WordPress.com's default DMARC and SPF records.
  The zone steps delete them, and `dns_compare.py` flags a second SPF or DMARC
  record on the new server.
- `dns_compare.py --names-from` takes a zone file as well as a folder, reads
  `$ORIGIN` and relative names, `*.zone` and `zone-*.records.json`, and stops
  if it finds no names. Handed a file it used to compare the apex and `www`
  only (2 names, not eagleman.com's 54). It now compares a CNAME name by its
  CNAME and leaves `atomic-domain` values out, which brought eagleman.com's
  comparison from 202 differences to the 3 real ones.
- `post.stats` says what a correct merge shows: `report_blog_id` is the new
  blog and `include_blog_id` the old one. eagleman.com's first merge ran the
  other way and the new blog showed no history.
- The Pressable deploy allowlist in `.deployignore` is removed before
  WordPress.com deploys are connected (`post.deploy-allowlist`), after
  Pressable's Git deployments are disconnected. WordPress.com deployments
  ignore its `!` lines and copy nothing (popculturemondays#298). The audit
  checks for it with `deploy_check.py allowlist`.
- `deploy_check.py drift` follows gitignore rules, `!` lines included. With the
  allowlist in place it used to treat every file as ignored, compare nothing
  and report `clean`. It now reports `nothing-compared` when nothing is left
  to compare, and ignores `!` lines for `--host wpcom` as WordPress.com does.
- VideoPress content and Jetpack plan gaps are reported as work for a person,
  like WooPayments. They no longer hold a site or count as decisions.
- Stats merge and subscriber migration are steps on every site.
- The staging site is its own last phase, after the DNS zone move, made with
  `team51 wpcom:clone-site`.
- Scope is the migration only. The migrated site stays Team 51-managed, so
  Atlantis is kept and checked, not removed, and the handover phase is gone.
- Deleting the Pressable site is gated on stats, subscribers, WooPayments and
  VideoPress being finished.
- Domains registered at WordPress.com get an ownership finding: the owning
  account must be a WordPress.com user on the new `a8cteam51` site before the
  domain is attached (`prep.domain-owner`, `verify.domain-owner`).
- The Atlantis encryption key is carried over by its own step
  (`platform.atlantis-key`). The audit records a short hash of the key and the
  message count, and `compare_sites.py` flags a key mismatch.
- The audit's wp-config parser now finds constants defined inside a
  `defined()` guard, as Atlantis writes its key. It missed them before.
- From the first real migration (2026-10-16):
  - Go-live steps for moving a domain between WP Cloud hosts: move a
    WordPress.com-registered domain in DARC (`cut.domain-move`), remove it
    from the Pressable site (`cut.release-pressable`), replace the
    `atomic-domain` TXT records before setting primary (`cut.domain`), rebuild
    the zone straight away when the move switched name servers
    (`cut.zone-records`), and check the apex and `www` hosting provider
    (`cut.hosting-check`).
  - `verify.domain-owner` connects the domain owner's WordPress.com account
    through the Jetpack debug tool, with no partner action.
  - The Pressable zone export moved before the window.
  - The freeze mu-plugin does nothing outside Pressable (the copy carried it
    to the new site, where it blocked XML-RPC), and `post-sync.sh` removes it.
  - Connecting WordPress.com deploys moved after cutover (`post.deploy-connect`).
  - `cut.unquarantine` clears the edge cache, which kept the quarantine's
    `noindex`.
  - The front-end comparison treats core packages served by Gutenberg and
    Jetpack packages served from wpcomsh as notes.
  - Create-site notes: `site_name_refused` from a domain-only subscription,
    the second confirmation prompt, the platform's default plugins.
  - Bilmur and bot-protection constants are dropped; `WP_ENVIRONMENT_TYPE` is
    not needed.

- The source step installs the Reprint exporter plugin and adds the public
  key the Migration Assistant shows. Jetpack's built-in exporter is not used.
- The site name passed to `wpcom:create-site` has no dashes, and the runbook
  gives the right temporary address.

- The Jetpack check no longer stops on the source's blog ID in the target's
  local `jetpack_options`; that is left by the copy. It checks connection
  health and the `out-of-sync-posts` sticker instead, and forbids
  disconnecting or reconnecting Jetpack. The parity and site comparisons
  report the ID as a note, not a failure.

- The copy runs once, inside the cutover window with the source frozen. The
  rehearsal sync, the final re-sync and the re-sync survival check are gone:
  a Migration Assistant run cannot be repeated against the same target. The
  runbook phases are now prepare, platform items, get ready (TTL, exporter,
  monitoring), then the window: freeze and copy, check the copy, go live.

### Added
- The Team 51 migrations space on Spacefast
  (`https://t51-pressable-migrations.space.fast/`) as the shared record of
  every migration. `scripts/space.py` checks for a site's entry, lists all
  migrations, publishes a site's report, status and progress (additive, one
  site at a time, every publish a version) and pulls a migration's progress
  into a new folder. The audit checks the space first and publishes at the
  end; `state.py --publish` updates the page after each step. New
  `migration-status` skill answers status questions from the space.
  `build_audit.py` now stores step titles, phases, the verdict and counts in
  `state.json`.
- `space.py login`: the skills sign in to Spacefast themselves. It starts the
  CLI's device login in the background and prints the approval link for the
  agent to pass on; `login --wait` returns once it is approved. No command to
  run before starting the agent.
- `pages/process.html`: the migration process as one page (every step, who
  does it, the branches the audit decides), published to the space's
  `/process/` with `space.py publish-process`.
- `REPORT.html`: the audit and the runbook as one self-contained page for a
  browser. Verdict, what the job involves (the cutover window step by step,
  what takes calendar time, the access and tools needed, what makes the site
  more than a standard migration), findings to expand, and the runbook with
  placeholders highlighted until the new site exists. Light and dark themes,
  readable on a phone, prints with everything expanded.
- `scripts/db_diff.py` (with `db_diff.php`): read-only row-level diff of every
  table, source against target, fingerprinted in SQL in buckets so it takes
  about six WP-CLI calls. Treats the site's host names as equal, separates
  gaps (data on the source missing or different on the target) from platform
  and target-only differences, and writes the gap rows as REPLACE statements
  for review. It is the go-live gate (`verify.db-diff`).
- `scripts/frontend/`: a front-end check. Samples pages from the source's
  sitemaps, snapshots them on both sides in headless Chrome (desktop and
  mobile, logged out, no proxy) and compares status, console errors, failed
  requests, assets, fonts, computed styles, layout, broken images and
  screenshots. Runbook steps after the first sync, before the freeze
  (baseline) and after cutover. Needs Node 20+, Google Chrome and
  `npm ci --prefix scripts/frontend`.
- A step after every sync to confirm in Blog RC that the WordPress.com cleanup
  finished, re-queue it if not, and check it did not remove the connection
  owner.
- A Jetpack connection repair on the new site after each sync, in the Jetpack
  debug tool: Restore User Connection, then Schedule Sync under Full Sync.
- Steps and findings for Team 51 monitoring: settings rows before and after
  cutover, a check that the new site reports the production domain before the
  old Jetpack connection goes, and a check that the new blog ID is picked up.
- Report notes on PHP fatals scanning and Poseidon site cloning, which do not
  cover WordPress.com sites, and on `plugin-autoupdate-filter`.

## [0.1.0] - 2026-10-10

### Added
- Initial draft for evaluation. Not yet used for a real migration.
- `migration-audit` skill: read-only audit of a Pressable site that writes a
  report, a manifest and a per-site runbook.
- `migration-run` skill: walks the runbook, records progress and decisions.
- `migration-verify` skill: parity, site comparison, URL crawl, stragglers.
- `migration-dns` skill: registrar and zone audit, cutover, zone comparison.
- `scripts/checks.py`: the check catalogue. `scripts/runbook.py`: the steps.
- `scripts/wpcom_facts.py`: subscriber count from the public WordPress.com API.
- `scripts/p2_extract.py`: pulls migration-relevant sentences out of project P2 posts.
- `assets/`: quarantine (target) and freeze (source) mu-plugins. Runtime
  filters only; neither writes to the database.
