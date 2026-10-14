"""Runbook steps for a Pressable -> WordPress.com migration.

Each step: id, phase, title, actor (agent | human | both), when (function of the
manifest and the set of step IDs switched on by findings; None = always), body
(markdown; {placeholders} are filled from the manifest), verify (how to know it
worked).

Steps marked UNTESTED describe a procedure that has not yet been run end to
end. Treat them as the best current plan and correct them here after the first
real migration.

The order of this list is the order of the runbook.
"""

PHASES = [
    ("decide", "1. Decisions and sign-off"),
    ("prep", "2. Prepare"),
    ("platform", "3. Platform items (before the window)"),
    ("ready", "4. Get ready for cutover"),
    ("sync", "5. Cutover window: freeze and copy"),
    ("verify", "6. Cutover window: check the copy"),
    ("cut", "7. Cutover window: go live"),
    ("post", "8. After cutover"),
    ("dns", "9. DNS zone move"),
    ("staging", "10. Staging site"),
    ("decom", "11. Decommission"),
]

UNTESTED = "> UNTESTED: this procedure has not been run end to end yet. Correct it here after the first real migration.\n\n"


def has(step_id):
    return lambda m, on: step_id in on


def woo(m, on):
    return bool(((m.get("site") or {}).get("woocommerce") or {}).get("active"))


def pressable_dns(m, on):
    return any(z.get("dns_host") == "pressable" for z in m.get("dns") or [])


STEPS = [
    # ---------------------------------------------------------------- decide
    dict(id="decide.blockers", phase="decide", actor="human", title="Clear every blocker in the audit report", when=None,
         body="Open `REPORT.md`. Every item under **Blockers** must be resolved or explicitly accepted by whoever owns the "
              "migration. Do not create the target site while a blocker is open.",
         verify="`REPORT.md` shows no open blockers after re-running the audit, or each has a recorded decision in `state.json`."),
    dict(id="decide.decisions", phase="decide", actor="human", title="Record the decisions the audit asks for", when=None,
         body="Each item under **Needs an answer** in the report needs one. If the report lists none, mark this step done. "
              "Record each answer:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} decide <key> \"<answer>\"\n```",
         verify="`state.json` has an entry under `decisions` for each."),
    dict(id="decide.window", phase="decide", actor="human", title="Agree the cutover window with the partner", when=None,
         body="The copy runs ONCE, inside this window, and cannot be repeated against the same target. The window covers: a "
              "write freeze on the live site, the copy, the checks and the database diff, and the DNS change. Keep it as short "
              "as possible and in the quietest hours (the audit's quiet-window finding, if present, is the starting point).\n\n"
              "Agree with the partner: no publishing or editing from the start of the window until they hear the site has moved; "
              "on a store, no orders during the window (the freeze closes checkout).",
         verify="Date, start time and expected length are recorded with `state.py decide cutover_window`."),

    # ------------------------------------------------------------------ prep
    dict(id="prep.dns-access", phase="prep", actor="human", title="Confirm registrar or DNS access", when=has("prep.dns-access"),
         body="For each domain the report marks **access required**: confirm who can log in to the registrar or DNS host, and "
              "that they will be available during the cutover window and the later name server change.\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} decide registrar_access.<apex-domain> confirmed\n```",
         verify="Re-run the audit build; the access finding drops from blocker to info."),
    dict(id="prep.woopayments", phase="prep", actor="human", title="Line up the WooPayments re-link", when=has("prep.woopayments"),
         body=UNTESTED +
              "WooPayments is a Stripe account linked to the site's blog ID through the Jetpack connection. The Stripe account, "
              "its balance, payout details and history survive the move. The link does not: on the new blog ID WooPayments "
              "behaves as if there were no account and offers to set one up.\n\n"
              "**Nobody clicks \"finish setup\" or onboards on the new site.** That creates a second Stripe account and orphans "
              "the real one.\n\n"
              "1. Note the store's live Stripe account ID (`acct_…`): it is in the report's WooPayments finding, or in the "
              "store's Payments settings. Source blog ID: `{source_blog_id}`.\n"
              "2. Open a request in `#woosupport` (it has a WooPayments Request form), copying `#a4a-ask`. Say the site is moving "
              "from Pressable to WordPress.com and will get a new blog ID, and ask for the account to be switched to it with "
              "the MC Switch Blog Tool once the new site exists. Ask what they need and how much notice. For a batch of stores, "
              "ask once for all of them.\n"
              "3. Tell them if the store has subscriptions or saved cards (the report says); those may need extra handling.\n"
              "4. Check who owns the Jetpack connection on the source (in the report). The same WordPress.com user should own it "
              "on the new site, or the switch can be refused.",
         verify="The WooPayments team has confirmed they will switch the account at cutover. Recorded with `state.py decide woopayments_relink`."),
    dict(id="prep.videopress", phase="prep", actor="human", title="Line up the VideoPress move", when=has("prep.videopress"),
         body=UNTESTED +
              "VideoPress storage is bound to the source blog ID (`{source_blog_id}`). After the move the videos are orphaned on the "
              "new blog ID and play as \"private\". There is no bulk transfer tool (Linear VIDP-93, internal issue "
              "Automattic/videopress#1036).\n\n"
              "1. Get the list: `manifest.json` → `site.videopress.videos` has each video's attachment ID, title and GUID. MC File "
              "Tools → List Blog Videos for blog `{source_blog_id}` shows the same from the VideoPress side and has "
              "**Download All Videos** (a `.tar`; the link lasts 7 days).\n"
              "2. Post in `#videopress` with both blog IDs and the video count, referencing VIDP-93, and ask what they can do.\n"
              "3. Choose a route:\n"
              "   - **A few videos:** move each with https://mc.a8c.com/tools/video-move/ (one video at a time).\n"
              "   - **Many videos:** keep them serving from the old blog ID with a complimentary VideoPress plan on it, download "
              "them all, re-upload on the new site, and re-point each block and embed. Re-uploads get new GUIDs; old blocks do not heal.\n"
              "4. Confirm the new site's plan includes VideoPress storage, or re-uploads count against site storage.",
         verify="Route recorded with `state.py decide videopress_route`. If the old blog ID needs a plan to keep videos serving, it is in place before cutover."),
    dict(id="prep.plan", phase="prep", actor="human", title="Confirm the target plan covers the Jetpack features in use", when=has("prep.plan"),
         body="The report's Jetpack table lists each feature in use and whether a Business or Commerce plan includes it. The "
              "ones marked as an add-on are the gap. For each, check whether the paid tier is really in use, then arrange the "
              "extra comp or purchase against the new blog ID so it is in place at cutover. A comp on the old blog ID does not "
              "follow the site.",
         verify="What was arranged is recorded with `state.py decide jetpack_gap`."),
    dict(id="prep.plugin-cleanup", phase="prep", actor="both", title="Clean up plugins the report flags", when=has("prep.plugin-cleanup"),
         body="For plugins flagged as unnecessary or disallowed on WordPress.com:\n\n"
              "- **Inactive on the source:** with the partner's agreement, delete them on the source now so they are never copied.\n"
              "- **Active on the source:** leave them. They are deactivated on the target after cutover (step `post.plugin-cleanup`).\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'plugin delete <slug>' {domain}\n```",
         verify="`wp plugin list` on the source no longer shows the deleted plugins."),
    dict(id="prep.create-site", phase="prep", actor="both", title="Create the WordPress.com site (Team 51-owned), or choose an existing one", when=None,
         body=UNTESTED +
              "**New site (the normal case).**\n\n"
              "```bash\nteam51 wpcom:create-site {site_slug}\n```\n\n"
              "What this command does: creates a Team 51 agency site on WordPress.com at `{site_slug}.wpcomstaging.com`, names "
              "it `{site_slug}-production`, rotates the admin password and installs Atlantis. It prints the new blog ID "
              "(\"provisioned as WPCOM site …\").\n\n"
              "- **The name has no dashes.** The CLI strips them itself. `mcp__team51__wpcom_create_site` does not: given a "
              "name with a dash, the server answers \"A site with this name already exists\" although no such site exists. "
              "Use the CLI, or pass the name exactly as written above.\n"
              "- It asks \"Would you like to deploy to the site from a GitHub repository?\" and the default is yes. **Answer no.** "
              "The repo is connected later, and only if the audit found the existing deploy current. Connecting now would deploy "
              "the repo onto the empty site before the copy arrives.\n"
              "- If it reports `site_already_exists` for a name without dashes, a site with that name does exist (see below, or "
              "pick another name).\n"
              "- Atlantis is installed here and stays: the migrated site remains a Team 51-managed site. The sync replaces the "
              "database, so its settings afterwards are the source's; step `post.atlantis` checks it.\n"
              "- Do NOT use `wpcom:clone-site` for this. That makes a staging copy of an existing WordPress.com site and scrubs it.\n\n"
              "**An existing WordPress.com site.** If the report lists one for this partner and it is to be the target, it can be "
              "used: the sync replaces its database, but files already on it are kept, so leftovers from earlier work stay. "
              "Prefer a new site unless there is a reason (a plan or domain already attached). If reusing, look at what is on it "
              "first and say so in the notes.\n\n"
              "Either way, record the target, then rebuild so every later command has it:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} target --domain <target>.wpcomstaging.com --blog-id <id>\n"
              "python3 {scripts}/build_audit.py --dir {dir}\n```",
         verify="`team51 wpcom:run-site-wp-cli-command <target> 'option get home'` returns the temporary URL. No GitHub deployment is "
                "connected yet. SafetyNet is not installed: `plugin list` and `wp-content/mu-plugins` show no `safety-net`."),
    dict(id="prep.php", phase="prep", actor="human", title="Match the PHP version", when=None,
         body="Set the target's PHP version to `{php_minor}` (the source's) in the WordPress.com hosting settings.",
         verify="`team51 wpcom:run-site-wp-cli-command {target} 'eval \"echo PHP_VERSION;\"'` starts with `{php_minor}`."),
    dict(id="prep.quarantine", phase="prep", actor="agent", title="Install the quarantine mu-plugin on the target", when=None,
         body=UNTESTED +
              "The copy will hold live gateway settings, webhooks, scheduled jobs and customer email triggers. The quarantine "
              "mu-plugin stops them at runtime and writes nothing to the database, so removing it restores normal behaviour.\n\n"
              "```bash\n{scripts}/mu_plugin.sh install wpcom {target} {assets}/t51-migration-quarantine.php\n```\n\n"
              "Never use SafetyNet for this: it deletes and scrubs data.",
         verify="`{scripts}/mu_plugin.sh status wpcom {target} t51-migration-quarantine.php` reports the file present. The target's "
                "front end shows the quarantine banner to logged-in administrators."),

    # ------------------------------------------------------------------ sync
    dict(id="sync.source-exporter", phase="ready", actor="both", title="Install the Reprint exporter on the source and add the key", when=None,
         body="The Migration Assistant needs the Reprint exporter plugin on the source site. (Jetpack's built-in exporter is "
              "not what the Assistant asks for.)\n\n"
              "1. Install and activate the plugin on the source:\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'plugin install https://github.com/WordPress/reprint/releases/latest/download/reprint-exporter-wp.zip --activate' {domain}\n```\n\n"
              "2. Open the Migration Assistant for the target and go to step 2, \"Connect source site\":\n\n"
              "{mc_assistant}\n\n"
              "3. Enter the source URL. The Assistant turns it into the export address, `https://{domain}/?site-export-api`, and "
              "shows a **public key**.\n"
              "4. Copy the public key into the plugin's settings on the source site (the Assistant links to them) and save. "
              "**Leave push access off.**\n"
              "5. Back in the Assistant, click **Next**.\n\n"
              "Do this before the window, and do NOT start the migration yet.\n\n"
              "This adds a plugin to the live site, so it is a change to the source: confirm before installing. The plugin is "
              "copied to the new site with everything else and is removed there after cutover (step `post.plugin-cleanup`).",
         verify="`plugin list` on the source shows `reprint-exporter-wp` active, and the Assistant has moved past step 2 "
                "without starting the migration."),
    dict(id="cut.go", phase="sync", actor="human", title="Go / no-go", when=None,
         body="Confirm: no open blockers; TTL lowered at least a day ago; Reprint exporter installed and the Assistant past "
              "step 2; partner informed of the content freeze; registrar or DNS access available now; WooPayments re-link "
              "scheduled if applicable; time left in the window for the checks; someone available to roll back.\n\n"
              "There is one copy. If anything before the DNS change fails, the rollback is to unfreeze the source and stop: "
              "the live site has not changed.",
         verify="Explicit go from the migration owner."),
    dict(id="cut.frontend-baseline", phase="sync", actor="agent", title="Snapshot what visitors see on the live site", when=None,
         body="What visitors see on the live site now, to compare the copy and later the live WordPress.com site against. "
              "Needs Node 20+ and Google Chrome; `npm ci --prefix {scripts}/frontend` once. Pick the sample before the window "
              "(add any page that matters to the partner: a form, a landing page, a product) and keep it.\n\n"
              "```bash\nnode {scripts}/frontend/sample.mjs https://{domain} --out {dir}/frontend-paths.txt   # once, before the window\n"
              "node {scripts}/frontend/snapshot.mjs https://{domain} --paths {dir}/frontend-paths.txt --out {dir}/frontend/baseline\n```",
         verify="`frontend/baseline/snapshot.json` exists and every sampled path loaded."),
    dict(id="cut.freeze", phase="sync", actor="agent", title="Freeze writes on the live site", when=None,
         body=UNTESTED +
              "Install the freeze mu-plugin on the SOURCE. It keeps pages browsable but refuses checkout, forms, comments, "
              "registration and non-administrator logins, and pauses scheduled jobs. Start in `drain` mode so payment callbacks "
              "for orders already in flight can still land, wait a few minutes, then switch to `frozen`.\n\n"
              "```bash\nT51_FREEZE_MODE=drain  {scripts}/mu_plugin.sh install pressable {domain} {assets}/t51-migration-freeze.php\n"
              "# wait 5-10 minutes on a store; no wait needed on a content site\n"
              "T51_FREEZE_MODE=frozen {scripts}/mu_plugin.sh install pressable {domain} {assets}/t51-migration-freeze.php\n"
              "date -u '+%Y-%m-%d %H:%M:%S'   # record this as the freeze time\n```\n\n"
              "Do not use host maintenance mode unless it has been shown not to block Reprint's export.",
         verify="A logged-out test: the site loads, a comment or checkout attempt is refused. Freeze time recorded: "
                "`state.py decide freeze_time \"<UTC time>\"`."),
    dict(id="sync.first", phase="sync", actor="human", title="Run the copy in the Migration Assistant (once)", when=None,
         body="With the source frozen, open the Migration Assistant for the target and run preflight, then migrate. This is "
              "the only copy: it cannot be re-run against this target.\n\n"
              "{mc_assistant}\n\n"
              "Source URL: `https://{domain}/`. If preflight fails, read the message: redirects, TLS and storage warnings can be "
              "continued through; authentication failures cannot. Failures are also posted in `#reprint`.\n\n"
              "Note the start and end time of the migrate step.",
         verify="The Assistant reports the migration and cleanup steps complete. Record the duration: "
                "`state.py decide copy_minutes <n>`. Then step `sync.cleanup`: the Assistant saying complete is not enough."),
    dict(id="sync.cleanup", phase="sync", actor="human", title="Confirm the WordPress.com cleanup really finished", when=None,
         body=UNTESTED +
              "On the test migration (2026-10-13) the Assistant reported the migration complete and clean, but the cleanup had "
              "not finished: Blog RC for the new site still showed the migration in progress with a **Complete Migration** "
              "button, the cleanup ran twice, and its \"jp sync fix\" removed the `a8cteam51` user and the connection owner's "
              "token part way through.\n\n"
              "1. Open Blog RC for blog `{target_blog_id}`.\n"
              "2. If it still shows the migration in progress, push **Enqueue post migration cleanup job** and wait for it to "
              "finish (about a minute). Its log entries are \"migration cleanup started/completed\", then \"jp sync fix\". "
              "On the test, the re-run finished cleanly in under a minute and removed nobody.\n"
              "3. Check the cleanup did not remove the connection owner: in the Jetpack debug tool "
              "(https://jptools.wordpress.com/debug/?url=https://{target}#section_connected_admins) the connection owner is "
              "connected, and `a8cteam51` is still an administrator.\n"
              "4. Only then, if the button is still offered, click **Complete Migration**. (On the test it was clicked before "
              "the cleanup was re-run; whether the order matters is not known.)\n\n"
              "Never disconnect or reconnect Jetpack on either site to fix anything found here. See step `verify.jetpack`.",
         verify="Blog RC shows the migration complete, the latest cleanup and jp sync fix log entries show no user or token "
                "removed, and the connection owner is connected. Recorded with `state.py decide cleanup_checked yes`."),

    # ---------------------------------------------------------------- verify
    dict(id="cut.post-sync", phase="sync", actor="agent", title="Run the post-sync script", when=None,
         body="```bash\nbash {dir}/post-sync.sh\n```", verify="Exits 0."),
    dict(id="verify.parity", phase="verify", actor="agent", title="Compare data between source and target", when=None,
         body="```bash\n{scripts}/wp_eval.sh pressable {domain} {scripts}/parity.php > {dir}/parity-source.json\n"
              "T51_ARGS='{{\"other_host\":\"{domain}\"}}' {scripts}/wp_eval.sh wpcom {target} {scripts}/parity.php > {dir}/parity-target.json\n"
              "python3 {scripts}/compare_parity.py {dir}/parity-source.json {dir}/parity-target.json\n```\n\n"
              "A quick count comparison. The source is frozen, so there should be no differences; `verify.db-diff` finds "
              "the exact rows if there are.",
         verify="`RESULT: PARITY`, or every difference is accounted for by `verify.db-diff`."),
    dict(id="verify.jetpack", phase="verify", actor="both", title="Check the new site's Jetpack connection is healthy", when=None,
         body=UNTESTED +
              "The copy brings the source's `jetpack_options` across, and the cleanup does not rewrite them: on the test "
              "migration the new site's `jetpack_options['id']` still held the SOURCE blog ID (`{source_blog_id}`) after two "
              "cleanup runs, while WordPress.com and the site's stored connection token both held the new one "
              "(`{target_blog_id}`). That on its own did not stop the site working, and it is not a reason to stop the migration. "
              "The explanation given (from another agent, not confirmed by the Jetpack or Reprint teams): on WordPress.com the "
              "connection tokens are kept outside the site database, in Atomic Persistent Data, and those decide the site's "
              "identity, not the local option.\n\n"
              "**Never disconnect or reconnect Jetpack on either site.** A reconnect on the new site while its local option "
              "still holds the source's ID could register it under the source's blog ID, which would create a real identity "
              "clash and put the live site's connection at risk.\n\n"
              "1. Record the local value, for the record only:\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {target} 'option pluck jetpack_options id'\n```\n\n"
              "   (Also visible in https://mc.a8c.com/automated-transfer/site-options-lookup.php?blog-id={target_blog_id}.)\n"
              "2. Repair the connection in the Jetpack debug tool. The copy replaced the database, so this is needed now.\n\n"
              "   1. Open the connection health section and click **Restore User Connection**:\n\n"
              "      https://jptools.wordpress.com/debug/?url=https://{target}#async_section_connection_health\n\n"
              "   2. On the same page, go to the **Full Sync** section and click **Schedule Sync**.\n"
              "3. Check what actually matters, in the debug tool: connected, connection owner connected, no warnings and no "
              "identity-crisis flag, on blog ID `{target_blog_id}`.\n"
              "4. After the next checksum run (it can take hours), check the site's stickers "
              "(`mcp__team51__wpcom_list_site_stickers` for `{target_blog_id}`). `out-of-sync-posts` (\"Didn't pass the Site "
              "Tester checksum test\") means Jetpack Sync and WordPress.com disagree about content. On the test it appeared the "
              "morning after the copy and cleared after a full sync and a re-run of the cleanup job (step `sync.cleanup`). It may "
              "only show after cutover; step `post.jetpack-resync` checks again. "
              "`site-migration-complete` should be present.",
         verify="The debug tool shows a healthy connection with the owner connected and no warnings, and `out-of-sync-posts` "
                "is absent after a checksum run. If the connection is unhealthy, or `out-of-sync-posts` survives a full sync "
                "and a cleanup re-run, ask in `#reprint` with both blog IDs and the local `jetpack_options['id']`; change "
                "nothing on either site meanwhile."),
    dict(id="verify.host-files", phase="verify", actor="agent", title="Check Pressable host files did not land on the target", when=has("verify.host-files"),
         body="```bash\n{scripts}/wp_eval.sh wpcom {target} {scripts}/site_audit.php > {dir}/site-target.json\n"
              "python3 -c \"import json;d=json.load(open('{dir}/site-target.json'));print(d['host_files'], d['dropins'], d['mu_plugins'])\"\n```",
         verify="No `pcm-*` or `pressable-*` files. `object-cache.php` and `advanced-cache.php`, if present, are the target host's own."),
    dict(id="verify.plugins", phase="verify", actor="agent", title="Compare plugins, theme and versions with the manifest", when=None,
         body="```bash\npython3 {scripts}/compare_sites.py {dir}/site.json {dir}/site-target.json\n```\n\n"
              "(Produce `site-target.json` as in `verify.host-files` if it does not exist.)",
         verify="Same active theme and the same active plugins at the same versions, apart from host plugins."),
    dict(id="verify.urls", phase="verify", actor="agent", title="Crawl the copy and compare responses", when=None,
         body="```bash\npython3 {scripts}/url_check.py https://{domain} https://{target} --limit 150 > {dir}/url-check.txt\n```\n\n"
              "What visitors see is compared in `verify.frontend`.",
         verify="No URL that returns 200 on the source returns an error on the target. Redirect targets match apart from the host."),
    dict(id="verify.frontend", phase="verify", actor="agent", title="Compare what visitors see on the copy with the live site", when=None,
         body="Same sample of pages, desktop and mobile, logged out, against the baseline taken at the start of the window. "
              "Compares status, console errors, failed requests, missing stylesheets and scripts, fonts, key computed styles, "
              "layout, broken images and screenshots; only differences count.\n\n"
              "```bash\nnode {scripts}/frontend/snapshot.mjs https://{target} --paths {dir}/frontend-paths.txt --out {dir}/frontend/target\n"
              "node {scripts}/frontend/compare.mjs {dir}/frontend/baseline {dir}/frontend/target --out {dir}/frontend/REPORT.md\n```\n\n"
              "The snapshots bypass the system proxy on purpose: through the Automattic proxy, WordPress.com shows its admin "
              "and debug bars to logged-out visitors, and every page would differ.",
         verify="`RESULT: MATCH`, or every issue in `frontend/REPORT.md` is explained. Missing stylesheets or scripts, failed "
                "fonts, new console errors and requests to the old host are migration problems. The source is frozen, so content "
                "differences are too: check them in `verify.db-diff`. Look at the `.diff.png` images for pages over the pixel "
                "threshold."),
    dict(id="verify.subscriptions-staging", phase="verify", actor="agent", title="Confirm Subscriptions is in staging mode on the copy", when=has("verify.subscriptions-staging"),
         body="WooCommerce Subscriptions should detect the changed URL and pause automatic payments on the copy.\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {target} 'eval \"echo class_exists(\\\"WCS_Staging\\\") && WCS_Staging::is_duplicate_site() ? \\\"staging\\\" : \\\"LIVE\\\";\"'\n```",
         verify="Prints `staging`. If it prints `LIVE`, renewals could run on the copy: keep the quarantine on and investigate."),
    dict(id="verify.endpoints", phase="verify", actor="both", title="Smoke-test custom endpoints on the copy", when=has("verify.endpoints"),
         body="For each REST namespace the report lists as custom, request its index on both hosts and compare:\n\n"
              "```bash\ncurl -s -o /dev/null -w '%{{http_code}}\\n' https://{domain}/wp-json/<namespace>\n"
              "curl -s -o /dev/null -w '%{{http_code}}\\n' https://{target}/wp-json/<namespace>\n```",
         verify="Same status codes on both."),
    dict(id="verify.human", phase="verify", actor="human", title="Look at the copy", when=None,
         body="Browse the temporary URL: home page, a few inner pages, wp-admin, the editor. For a store: product, cart, and the "
              "checkout page (it will refuse payment while quarantined; that is expected).",
         verify="Nothing looks broken. Anything odd is written down before moving on."),

    # -------------------------------------------------------------- platform
    dict(id="verify.db-diff", phase="verify", actor="agent", title="Diff the databases: the go-live gate", when=None,
         body=UNTESTED +
              "Row-by-row comparison of every table on both sides (read-only). Host names are treated as equal, so the URL "
              "rewrite by the copy does not count. Takes a couple of minutes.\n\n"
              "```bash\npython3 {scripts}/db_diff.py --source {domain} --target {target} --hosts {domain},{target} --out {dir}/db-diff --sql\n```\n\n"
              "`{dir}/db-diff/DIFF.md` lists:\n\n"
              "- **Gaps:** rows on the source that are missing or different on the target. With the source frozen before the "
              "copy there should be none. Each one is data that would be lost: an order, a comment, a page, a setting.\n"
              "- **Target-only and platform differences:** options, caches, queues and tables WordPress.com adds or changes. "
              "Not gaps.\n\n"
              "Resolve every gap before the DNS change, or record why it can wait:\n\n"
              "- A few posts, pages, comments or settings: recreate them on the target by hand.\n"
              "- More, or orders: `{dir}/db-diff/delta.sql` holds each gap row from the source as a REPLACE statement. A "
              "developer reviews it and applies what is needed to the target database; this plugin does not apply it.\n\n"
              "Then run the diff again.",
         verify="`RESULT: NO GAPS`, or each remaining gap is resolved or recorded with `state.py decide db_gaps \"<what and why>\"`. "
                "This is the go-live gate: with gaps unexplained, unfreeze the source and stop."),
    dict(id="platform.script", phase="platform", actor="agent", title="Start the post-sync script", when=None,
         body="The copy REPLACES the target database, so a database change made on the target before the window is lost. "
              "Keep each one as a command in `{dir}/post-sync.sh`; it runs once, straight after the copy. File changes made "
              "on the target now (wp-config, mu-plugins, deployed code) are kept.\n\n"
              "Start the file with the steps below that apply, and add to it as you go.",
         verify="`{dir}/post-sync.sh` exists and running it twice gives the same result."),
    dict(id="platform.constants", phase="platform", actor="both", title="Carry over wp-config constants", when=has("platform.constants"),
         body=UNTESTED +
              "wp-config.php is not copied. For each constant in the report decide: carry over, replace, or drop. Read values from "
              "the source when needed (do not paste secrets into chat or the report):\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'config get <NAME>' {domain}\n```\n\n"
              "On the target, set what is needed. If WordPress.com does not allow the constant in wp-config, define it in a small "
              "mu-plugin instead.\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {target} 'config set <NAME> <value> --type=constant'\n```",
         verify="`config get <NAME>` on the target returns the expected value for each constant carried over."),
    dict(id="platform.root-files", phase="platform", actor="both", title="Carry over files outside wp-content", when=has("platform.root-files"),
         body=UNTESTED +
              "Only wp-content is copied. For each file the report lists (for example `custom-redirects.php`), read it on the "
              "source and recreate its behaviour on the target: the same file if the platform supports it, otherwise a mu-plugin "
              "or a redirect plugin.",
         verify="Each redirect or behaviour from the file works on the temporary URL."),
    dict(id="platform.custom-code", phase="platform", actor="agent", title="Review custom code for Pressable-specific logic", when=has("platform.custom-code"),
         body="Search the site's repo and mu-plugins, and any database-stored snippets, for host-specific code:\n\n"
              "```bash\ngrep -rnI -i -E 'IS_PRESSABLE|pressable|batcache|pcm_|edge.?cache|mystagingwebsite|openhostingservice' .\n```",
         verify="Each hit is either harmless or has a change planned."),
    dict(id="platform.deploy-connect", phase="platform", actor="agent", title="Connect WordPress.com GitHub Deployments", when=has("platform.deploy-connect"),
         body=UNTESTED +
              "The audit found the existing deploy connected and current, so connecting is safe.\n\n"
              "```bash\nteam51 wpcom:connect-site-repository {target} {repo_name} --branch {deploy_branch} --target_dir /wp-content/\n```\n\n"
              "This also creates the deployment webhook to OpsOasis, which needs its secret stored there under the new blog ID "
              "(`mcp__team51__wpcom_list_deployment_webhooks` shows the webhook; `wpcom_sync_deployment_webhook_secret` stores "
              "the secret if the CLI did not). Note that the CLI creates the deployment as automatic: "
              "every push to the branch deploys. Without `--deploy` nothing is deployed until the next push. Deploy once on "
              "purpose and confirm the files on the target still match the repo.\n\n"
              "This connection, on the repo's default branch, is also what lets OpsOasis move the repo's "
              "`wpcom-blog-id-production` property to the new blog ID overnight.",
         verify="```bash\npython3 {scripts}/deploy_check.py drift --repo {repo} --rev <deployed sha> --host wpcom --site {target}\n```\nreports `clean`."),
    dict(id="platform.deploy-reconcile", phase="platform", actor="both", title="Reconcile server changes into the repo before connecting deploys", when=has("platform.deploy-reconcile"),
         body="Files on the server differ from the repo. Read `{dir}/deploy.json` for the list. Bring each real change into the "
              "repo through a pull request, deploy through the existing pipeline, and re-run the drift check until it is clean. "
              "Only then connect WordPress.com deploys (step `platform.deploy-connect`).",
         verify="`deploy_check.py drift` reports `clean`."),
    dict(id="platform.deploy-skip", phase="platform", actor="human", title="Leave deploys unconnected", when=has("platform.deploy-skip"),
         body="No deploy targets production, so connecting one risks overwriting files nobody has in git. Migrate the files as "
              "they are. Getting production code into a repo is a separate task; raise it if the partner wants it.\n\n"
              "With no deployment connected, OpsOasis cannot match the repo to the new site: the repo's blog ID and site URL "
              "properties keep the old values until they are set by hand (step `decom.records`), and deployments are not "
              "announced.",
         verify="No GitHub deployment is connected on the target."),

    # ----------------------------------------------------------------- ready
    dict(id="rehearse.opsoasis", phase="ready", actor="human", title="Prepare Team 51 monitoring for the cutover", when=None,
         body=UNTESTED +
              "OpsOasis watches both copies of the site and treats a blog ID that disappears as an outage. In OpsOasis "
              "settings, before cutover:\n\n"
              "- Add a `site_health_monitor.known_issues` row for the OLD blog ID (`{source_blog_id}`). It stops the daily health "
              "check reporting \"Jetpack disconnected\" when the old connection goes.\n"
              "- Add the Pressable site ID (`{pressable_id}`) to `php_fatals.excluded_sites`. Otherwise the old copy keeps filing "
              "issues in the repo for as long as it exists.\n"
              "- If the old blog ID has a row in `site_exclusions.wpcom_sites` or `known_issues` that should carry on, add the "
              "same row for the new blog ID (`{target_blog_id}`). Rows are per blog ID and do not follow the site.\n"
              "- Tell whoever watches the Jetpack connection alerts and `#team51-pub-support` that a migration is in progress.\n\n"
              "Expect, and ignore, until the old site is gone: a \"Production site added\" notice for the new blog ID, and one "
              "outage alerting twice because both copies are monitored.",
         verify="Both rows exist. Recorded with `state.py decide opsoasis_prepared yes`."),
    dict(id="rehearse.ttl", phase="ready", actor="human", title="Lower DNS TTLs", when=None,
         body="At least 24 hours before the window (longer than the current TTL), lower the TTL on the site's A/CNAME records "
              "to 300 seconds in the current DNS host. This keeps the time visitors still reach the old site after the switch "
              "to minutes.",
         verify="`dig +noall +answer {domain}` shows the lower TTL."),

    # ------------------------------------------------------------------- cut
    dict(id="cut.domain", phase="cut", actor="both", title="Attach the domain to the WordPress.com site and make it primary", when=None,
         body=UNTESTED +
              "In the WordPress.com dashboard for the target: add `{domain}` (and `www`) as a connected domain and set it as "
              "primary. Then rewrite the temporary URL in content:\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {target} \"search-replace '//{target}' '//{domain}' --all-tables-with-prefix --precise --skip-columns=guid --report-changed-only\"\n"
              "team51 wpcom:run-site-wp-cli-command {target} 'cache flush'\n```",
         verify="`option get home` and `option get siteurl` on the target return `https://{domain}`. The parity script's "
                "`other_host_references` for the temporary host is zero."),
    dict(id="cut.dns", phase="cut", actor="human", title="Point the site records at WordPress.com", when=None,
         body="In the CURRENT DNS host, change only the site's own records (apex and `www`) to the values WordPress.com shows for "
              "the connected domain. Leave name servers and every other record alone; the zone move is a separate, later phase.\n\n"
              "Rollback is changing these records back.",
         verify="```bash\ndig +short {domain} @1.1.1.1\ndig +short www.{domain} @8.8.8.8\n```\nreturn the WordPress.com values. "
                "`curl -sI https://{domain}` shows a valid certificate and a response from the new site."),
    dict(id="cut.jetpack-host", phase="cut", actor="agent", title="Confirm the new site reports the production domain through Jetpack", when=None,
         body=UNTESTED +
              "Order matters. The Jetpack connection monitor forgives a blog ID change only if the new site already reports "
              "the production domain when the old connection disappears. Otherwise the old blog ID becomes an `@here` "
              "\"Production site removed\" alert.\n\n"
              "```bash\ncurl -s 'https://public-api.wordpress.com/rest/v1.1/sites/{target_blog_id}?fields=ID,URL'\n```\n\n"
              "Until this shows the production domain, do NOT disconnect Jetpack on the Pressable site, remove its domain or "
              "delete it. The old site stays connected and frozen; it is only removed in the decommission phase.",
         verify="`URL` is `https://{domain}`. If it still shows the temporary address after ten minutes, check the Jetpack "
                "connection on the new site before going further."),
    dict(id="cut.unquarantine", phase="cut", actor="agent", title="Remove the quarantine from the new site", when=None,
         body="Only once DNS resolves to the new site and the checks above pass. The quarantine never lifts by itself: until "
              "this file is removed the live site sends no email, runs no scheduled jobs and takes no payments.\n\n"
              "```bash\n{scripts}/mu_plugin.sh remove wpcom {domain} t51-migration-quarantine.php\n```",
         verify="Status reports the file absent. Scheduled jobs run; a test email arrives."),
    dict(id="cut.leave-frozen", phase="cut", actor="human", title="Leave the old site frozen", when=None,
         body="Do NOT remove the freeze from the Pressable site. Visitors whose DNS has not updated still reach it; frozen, they "
              "cannot create data that would be lost.",
         verify="The freeze mu-plugin is still installed on the source."),

    # ------------------------------------------------------------------ post
    dict(id="post.smoke", phase="post", actor="both", title="Smoke-test the live site", when=None,
         body="Home page, inner pages, search, a form submission, login, wp-admin, the editor, media upload.",
         verify="All work on `https://{domain}`."),
    dict(id="post.jetpack-resync", phase="post", actor="human", title="Restore the Jetpack connection and schedule a full sync", when=None,
         body="The domain has just changed. Repair the connection again in the "
              "Jetpack debug tool so WordPress.com holds the new site's current content and address. Do this before the "
              "WooPayments, stats and subscriber steps, which all go through the connection. As in step `verify.jetpack`: "
              "the local `jetpack_options['id']` may still hold the source's blog ID, and nobody disconnects or reconnects "
              "Jetpack to change it.\n\n"
              "1. Open the connection health section of the Jetpack debug tool for the new site and click **Restore User Connection**:\n\n   https://jptools.wordpress.com/debug/?url=https://{domain}#async_section_connection_health\n\n2. On the same page, go to the **Full Sync** section and click **Schedule Sync**.",
         verify="The connection health section reports no problems for `https://{domain}` on blog ID `{target_blog_id}`, and "
                "the Full Sync section shows the sync scheduled or complete. After the next checksum run, `out-of-sync-posts` is "
                "not among the site's stickers."),
    dict(id="post.frontend", phase="post", actor="agent", title="Compare the live site with the pre-cutover baseline", when=None,
         body="Once DNS resolves to WordPress.com and the quarantine is removed:\n\n"
              "```bash\nnode {scripts}/frontend/snapshot.mjs https://{domain} --paths {dir}/frontend-paths.txt --out {dir}/frontend/live\n"
              "node {scripts}/frontend/compare.mjs {dir}/frontend/baseline {dir}/frontend/live --out {dir}/frontend/REPORT-live.md\n```\n\n"
              "Run it from a network that already resolves the domain to WordPress.com (check with `dig`), or the 'live' "
              "snapshot is of the old site.",
         verify="`RESULT: MATCH`, or each issue is explained. The source was frozen from the baseline onward, so any content "
                "difference here is a real problem."),
    dict(id="post.gateways", phase="post", actor="human", title="Place an order through each payment gateway", when=has("post.gateways"),
         body="One order per enabled gateway, then refund it. Check the order emails arrive. In each gateway's own dashboard, "
              "confirm webhook or callback deliveries are succeeding.",
         verify="Each order reaches the expected status and each gateway shows successful deliveries."),
    dict(id="post.woopayments", phase="post", actor="human", title="Get WooPayments re-linked and prove it", when=has("post.woopayments"),
         body=UNTESTED +
              "Until this is done the new site cannot take WooPayments payments, so do it straight after cutover with another "
              "gateway live in the meantime if there is one.\n\n"
              "1. Confirm the new site's Jetpack connection is healthy and owned by the expected WordPress.com user.\n"
              "2. Ask the WooPayments team (the `#woosupport` thread from `prep.woopayments`) to switch the account from blog ID "
              "`{source_blog_id}` to `{target_blog_id}`. Give them the Stripe account ID.\n"
              "3. Do not onboard or click \"finish setup\" while waiting.\n"
              "4. Afterwards, in wp-admin → Payments: the existing account, its balance, pending payouts and transaction "
              "history are all there, and payout bank details are unchanged.\n"
              "5. Make a small live payment and refund it. Check Apple Pay and Google Pay still appear at checkout.",
         verify="Payments → Overview shows the existing account, not a setup prompt. The test payment appears in that account's "
                "transactions and the refund succeeds."),
    dict(id="post.subscriptions", phase="post", actor="human", title="Confirm Subscriptions is back in live mode", when=has("post.subscriptions"),
         body="With the real domain restored, WooCommerce Subscriptions should leave staging mode by itself. Check "
              "WooCommerce → Status, and that the next renewals are scheduled.",
         verify="No staging-mode notice. Upcoming renewal actions exist in Scheduled Actions."),
    dict(id="post.webhooks", phase="post", actor="agent", title="Check WooCommerce webhooks are delivering", when=has("post.webhooks"),
         body="```bash\nteam51 wpcom:run-site-wp-cli-command {domain} 'wc webhook list --user=1 --fields=id,name,status,topic,delivery_url'\n```",
         verify="Active webhooks are still active and their recent deliveries (WooCommerce → Status → Logs) succeed."),
    dict(id="post.integrations", phase="post", actor="human", title="Confirm external integrations still work", when=has("post.integrations"),
         body="For each integration the partner named (anything using REST API keys or application passwords), trigger it or "
              "ask its owner to confirm.", verify="Each one confirmed."),
    dict(id="post.email", phase="post", actor="both", title="Send test emails", when=has("post.email"),
         body="Trigger a password reset and, for a store, an order email. Check they arrive and are not marked as spam.",
         verify="Both arrive in an inbox."),
    dict(id="post.cron", phase="post", actor="agent", title="Check scheduled events are running", when=has("post.cron"),
         body="```bash\nteam51 wpcom:run-site-wp-cli-command {domain} 'cron event list --fields=hook,next_run_relative --format=csv'\n```",
         verify="Custom hooks from the report are scheduled, and none is overdue by more than its interval."),
    dict(id="post.plugin-cleanup", phase="post", actor="agent", title="Deactivate plugins that should not run on WordPress.com", when=has("prep.plugin-cleanup"),
         body="For each active plugin the report flagged and the partner agreed to drop:\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {domain} 'plugin deactivate <slug>'\n```",
         verify="Site still works; `plugin list --status=active` no longer shows them."),
    dict(id="post.atlantis", phase="post", actor="agent", title="Confirm Atlantis is working on the new site", when=None,
         body=UNTESTED +
              "Atlantis stays: the site is still Team 51-managed. Its plugin files come from site creation and its settings "
              "from the copied database, so check the two agree.\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {domain} 'plugin list --name=a8csp-atlantis --fields=name,status,version'\n"
              "team51 wpcom:run-site-wp-cli-command {domain} 'option get a8csp_atlantis_autoupdate_settings_url'\n```\n\n"
              "`mcp__team51__wpcom_get_atlantis_status` reports the same from the Team 51 side. If the source ran the older "
              "`plugin-autoupdate-filter` (the report says), it came across too: it works, but stops all updates whenever "
              "its settings server errors, so say so in the notes.",
         verify="Atlantis is active, the settings address is set, and the status tool reports a healthy settings fetch. The "
                "footer renders correctly."),
    dict(id="post.videopress", phase="post", actor="both", title="Move or re-upload VideoPress videos and check playback", when=has("post.videopress"),
         body=UNTESTED +
              "Carry out the route agreed in `prep.videopress`, now that the new blog ID (`{target_blog_id}`) is live.\n\n"
              "- Moving individually: https://mc.a8c.com/tools/video-move/ for each GUID in `manifest.json` → `site.videopress.videos`.\n"
              "- Re-uploading: upload each file on the new site, then replace the old GUID in every post that uses it. Find them with:\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {domain} \"db search '<old guid>' --all-tables-with-prefix\"\n```\n\n"
              "Until every video plays from the new site, the old Pressable site must stay connected and undeleted: originals and "
              "downloads depend on it.",
         verify="Open each post that embeds a video, logged out, and play it. None reports \"The video is private\". "
                "Record with `state.py decide videopress_done yes`; decommission waits on this."),
    dict(id="post.stats", phase="post", actor="human", title="Merge stats into the new blog ID", when=has("post.stats"),
         body="Done on every migrated site.\n\n"
              "Blog Stats Merger (its own page): https://mc.a8c.com/merge-stats.php\n\n"
              "- Previous (source) blog ID: `{source_blog_id}`\n- Current (destination) blog ID: `{target_blog_id}`\n\n"
              "Click **Show existing merges for a blog** for the source first. Post IDs match because the database was copied, "
              "which is what the merge needs.",
         verify="The tool confirms the merge. Stats on the new site show history."),
    dict(id="post.subscribers", phase="post", actor="human", title="Migrate subscribers to the new blog ID", when=has("post.subscribers"),
         body="Done on every migrated site, including one that reports no subscribers: the count can lag.\n\n"
              "Blog Subscription Migration, a section of the Jetpack tools page: https://mc.a8c.com/jetpack-tools/\n\n"
              "(That page also contains the stats merger; use the separate link in the stats step for that.)\n\n"
              "- Source blog ID: `{source_blog_id}`\n- Destination blog ID: `{target_blog_id}`\n- Support reference: the Linear issue for this migration\n\n"
              "You get an email when it finishes.",
         verify="```bash\npython3 {scripts}/wpcom_facts.py {target_blog_id}\n```\nreports the subscriber count recorded in the audit."),
    dict(id="post.stragglers", phase="post", actor="agent", title="Check the old site for writes after the freeze", when=None,
         body="Run once DNS has had time to propagate (at least the old TTL), and again a day later.\n\n"
              "```bash\nT51_ARGS='{{\"since\":\"<freeze time, UTC>\"}}' {scripts}/wp_eval.sh pressable {pressable_id} {scripts}/parity.php | python3 -c \"import json,sys;print(json.load(sys.stdin)['after_since'])\"\n```",
         verify="Every count is zero. Anything else is data on the old site only: find the rows with `db_diff.py` (source by "
                "Pressable ID `{pressable_id}`, target `{domain}`) and port them."),

    # ------------------------------------------------------------------- dns
    dict(id="dns.export", phase="dns", actor="both", title="Export the full zone from Pressable", when=pressable_dns,
         body="The audit's DNS records are guesses at common names, not the full zone. Get every record from Pressable "
              "(API: `GET /zones/{{zone_id}}/records`, or the DNS tab of the Pressable dashboard) and save it as "
              "`{dir}/zone-export.json` or a BIND file. The zone IDs are on the records from `pressable_list_site_domains`.",
         verify="The export contains every name in the audit's DNS findings, plus any DKIM selectors."),
    dict(id="dns.zone-move", phase="dns", actor="human", title="Recreate the zone in WordPress.com DNS and switch name servers", when=pressable_dns,
         body=UNTESTED +
              "1. In the WordPress.com dashboard, Domains → the domain → DNS records → menu → **Import BIND file**. It imports A, "
              "AAAA, CNAME, MX, SRV, TXT and NS, and errors on conflicts with existing records.\n"
              "2. Compare the new zone with the old before touching name servers:\n\n"
              "```bash\npython3 {scripts}/dns_compare.py {apex} --old ns1.openhostingservice.com --new ns1.wordpress.com --names-from {dir}\n```\n\n"
              "3. When they match, change the name servers at the registrar to WordPress.com's. For third-party registrars this "
              "is the partner's login.",
         verify="`dns_compare.py` reports no differences. After the switch, `dig NS {apex}` returns WordPress.com name servers and "
                "the partner confirms email is flowing."),

    # ----------------------------------------------------------------- decom
    dict(id="staging.create", phase="staging", actor="both", title="Create a WordPress.com staging site", when=None,
         body=UNTESTED +
              "Do this last: after cutover, after the after-cutover steps, and after every DNS change including the zone move. "
              "The staging site is a copy of the new production site, so anything unfinished there is copied too. A Pressable "
              "development site is not migrated; this replaces it.\n\n"
              "```bash\nteam51 wpcom:clone-site {domain} --branch develop\n```\n\n"
              "From its source, this uses WordPress.com's own staging-site feature, then: sets the copy's environment type to "
              "`development`, rewrites URLs, rotates the admin password, installs SafetyNet as a mu-plugin on the copy (which "
              "deletes customers, orders and subscriptions there and scrubs keys), and connects the production site's repo on "
              "the branch given, deploying it. If production has no repo connected it asks whether to continue without one; "
              "leave `--branch` off in that case.\n\n"
              "SafetyNet runs on the staging copy only. It is never installed on the production site.\n\n"
              "TO CONFIRM (being clarified, check before running this on a store):\n"
              "- That SafetyNet on the staging copy is wanted here. `--skip-safety-net` leaves the copy unscrubbed.\n"
              "- WordPress.com can sync a staging site's database back to production. From a scrubbed copy that would delete "
              "real orders and customers. Until it is confirmed that this sync is blocked on SafetyNet copies, nobody syncs "
              "staging to production.",
         verify="The staging site loads and `plugin list` on production does not show SafetyNet. If a branch was connected, a "
                "push to it deploys to staging. Order and customer counts on production are unchanged."),
    dict(id="decom.wait", phase="decom", actor="human", title="Wait before removing anything", when=None,
         body="Keep the Pressable site, frozen, for at least a week after cutover and until the straggler check has been zero "
              "twice and any zone move is complete.", verify="A week has passed with no issues."),
    dict(id="decom.managed", phase="decom", actor="agent", title="Confirm the new site is being managed", when=None,
         body=UNTESTED +
              "After one full day on the production domain (OpsOasis runs its repo map at 03:00 UTC and its health check at "
              "16:00 UTC), check the new blog ID (`{target_blog_id}`) has been picked up:\n\n"
              "- **Jetpack Monitor:** the Monitor module is on and the down-webhook is registered. OpsOasis does both itself. If "
              "not, the host is matched by an ignore pattern or enrolment is off.\n"
              "- **Repo properties:**\n\n"
              "```bash\ngh api repos/{repo}/properties/values\n```\n\n"
              "  `wpcom-blog-id-production` should hold `{target_blog_id}` and `site-url-production` the domain. They follow "
              "the site only when a WordPress.com deployment is connected on the repo's default branch. If the old blog ID is "
              "still there, set them by hand in step `decom.records`.\n"
              "- **Deployments:** a deploy is announced in the daily deployment thread.\n"
              "- **Connection monitor:** no alert was raised for the old blog ID.\n\n"
              "Two things do not carry over, and the report says so: PHP fatals scanning only covers Pressable sites, and "
              "Poseidon's site clone and capture needs a Pressable site behind the production URL.",
         verify="Each of the four checks passes, or the gap is noted in the Linear issue."),
    dict(id="decom.deployhq", phase="decom", actor="human", title="Check DeployHQ before the Pressable site is deleted", when=None,
         body="Deleting a Pressable site makes OpsOasis delete that site's DeployHQ servers automatically, and the whole project "
              "if that leaves it empty. There is no opt-out. So before deleting:\n\n"
              "- Note the project, its servers and the last deployed revision in the Linear issue, in case they are needed.\n"
              "- A project that also serves another site (for example a redesign) keeps its other servers and survives.\n"
              "- If anything still has to deploy to the new site through DeployHQ, its server must already be in the project.\n\n"
              "The DeployHQ webhook on the GitHub repo is not removed automatically. Remove it once the project is gone.",
         verify="After the Pressable site is deleted, `gh api repos/{repo}/hooks` shows no `deployhq.com` hook."),
    dict(id="decom.pressable", phase="decom", actor="human", title="Remove the Pressable sites", when=None,
         body="Not before all of these are true:\n\n"
              "- stats are merged and subscribers migrated (both read from the old blog ID);\n"
              "- any WooPayments re-link is finished;\n"
              "- if the site had VideoPress content, `post.videopress` is done: deleting or disconnecting the old site removes "
              "access to the original videos;\n"
              "- step `cut.jetpack-host` passed, so the old connection can go quietly.\n\n"
              "Delete the production Pressable site (`{pressable_id}`), the development and staging sites the report lists, and "
              "any Poseidon staging clones of it (nothing removes those automatically). "
              "Delete the Pressable DNS zone only after name servers have moved.",
         verify="Sites no longer appear in `pressable_list_sites`. No `@here` alert followed."),
    dict(id="decom.records", phase="decom", actor="agent", title="Update records", when=None,
         body="If step `decom.managed` found the repo's properties still on the old blog ID, set them:\n\n"
              "```bash\ngh api -X PATCH repos/{repo}/properties/values -f 'properties[][property_name]=wpcom-blog-id-production' -f 'properties[][value]={target_blog_id}'\n```\n\n"
              "OpsOasis never clears a stale value, and it is what Zendesk issue filing and Poseidon read. Update any team "
              "site lists, and note the migration in the Linear issue with the old and new blog IDs.",
         verify="`gh api repos/{repo}/properties/values` shows the new blog ID."),
    dict(id="decom.opsoasis", phase="decom", actor="human", title="Tidy Team 51 monitoring settings", when=None,
         body="In OpsOasis, once the old site is gone and one health check has run clean:\n\n"
              "- Remove the `known_issues` row for the old blog ID (`{source_blog_id}`).\n"
              "- Remove the Pressable site ID (`{pressable_id}`) from `php_fatals.excluded_sites` and `allowed_sites`.\n"
              "- Delete the option `a8csp_opsoasis_php_fatals_last_seen_{pressable_id}`. Nothing else removes it.\n"
              "- If the old site had a WordPress.com deployment secret row, delete it with "
              "`a8csp_opsoasis_delete_encrypted_option()`, never `delete_option()`.\n\n"
              "The health baseline, site-hosts index and repo index correct themselves.",
         verify="`wp opsoasis doctor` is clean."),
]


def build(manifest, switched_on):
    """Return the steps that apply, in phase order (stable within a phase)."""
    order = {p: i for i, (p, _) in enumerate(PHASES)}
    out = []
    for step in sorted(STEPS, key=lambda st: order[st["phase"]]):
        cond = step.get("when")
        if cond is None or cond(manifest, switched_on):
            out.append(step)
    return out
