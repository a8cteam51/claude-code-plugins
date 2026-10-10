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
    ("sync", "3. First sync"),
    ("verify", "4. Verify the copy"),
    ("platform", "5. Platform items"),
    ("rehearse", "6. Rehearsal"),
    ("cut", "7. Cutover"),
    ("post", "8. After cutover"),
    ("dns", "9. DNS zone move"),
    ("decom", "10. Decommission"),
    ("handover", "11. Handover (on partner acceptance)"),
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
         body="The window must cover: a write freeze on the live site, the final sync, checks, and the DNS change. "
              "Use the timing from the rehearsal (phase 6) once you have it. The audit's quiet-window finding, if present, is the starting point.",
         verify="Date, start time and expected length are recorded with `state.py decide cutover_window`."),

    # ------------------------------------------------------------------ prep
    dict(id="prep.dns-access", phase="prep", actor="human", title="Confirm registrar or DNS access", when=has("prep.dns-access"),
         body="For each domain the report marks **access required**: confirm who can log in to the registrar or DNS host, and "
              "that they will be available during the cutover window and the later name server change.\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} decide registrar_access.<apex-domain> confirmed\n```",
         verify="Re-run the audit build; the access finding drops from blocker to info."),
    dict(id="prep.woopayments", phase="prep", actor="human", title="Open the WooPayments account move", when=has("prep.woopayments"),
         body="Contact WooPayments support and ask to move the account from blog ID `{source_blog_id}` to the new site's blog ID "
              "(you will have it after step `prep.create-site`). Ask for: lead time, whether saved cards carry over, and where "
              "payment events go between cutover and the move.",
         verify="Support has confirmed a date at or before cutover. Recorded with `state.py decide woopayments_move`."),
    dict(id="prep.videopress", phase="prep", actor="human", title="Agree the VideoPress route", when=has("prep.videopress"),
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
         body="The report's Jetpack table lists each feature in use and whether a Business or Commerce plan includes it. For "
              "each one marked as an add-on or not included, find out whether the partner relies on it, then buy it, comp it or "
              "drop it. Comps follow the Team 51 handbook: partners pay by default, comps are case by case.",
         verify="Decision recorded with `state.py decide jetpack_gap`."),
    dict(id="prep.plugin-cleanup", phase="prep", actor="both", title="Clean up plugins the report flags", when=has("prep.plugin-cleanup"),
         body="For plugins flagged as unnecessary or disallowed on WordPress.com:\n\n"
              "- **Inactive on the source:** with the partner's agreement, delete them on the source now so they are never copied.\n"
              "- **Active on the source:** leave them. They are deactivated on the target after the final sync (step `post.plugin-cleanup`).\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'plugin delete <slug>' {domain}\n```",
         verify="`wp plugin list` on the source no longer shows the deleted plugins."),
    dict(id="prep.create-site", phase="prep", actor="both", title="Create the WordPress.com site (Team 51-owned), or choose an existing one", when=None,
         body=UNTESTED +
              "**New site (the normal case).**\n\n"
              "```bash\nteam51 wpcom:create-site {site_slug}\n```\n\n"
              "What this command does, from its source: creates a Team 51 agency site on WordPress.com, names it "
              "`{site_slug}-production`, rotates the admin password, installs Atlantis and registers the site with it.\n\n"
              "- It asks \"Would you like to deploy to the site from a GitHub repository?\" and the default is yes. **Answer no.** "
              "The repo is connected later, and only if the audit found the existing deploy current. Connecting now would deploy "
              "the repo onto the empty site before the copy arrives.\n"
              "- If it reports `site_already_exists`, a site with that name exists already (see below, or pick another name).\n"
              "- Atlantis being installed here does not matter: the sync replaces the database, and Atlantis is removed after the "
              "final sync.\n"
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
    dict(id="sync.source-exporter", phase="sync", actor="both", title="Make the source exportable", when=None,
         body=UNTESTED +
              "Two exporters exist. Which one the Migration Assistant accepts for a Pressable source is not yet confirmed.\n\n"
              "- **Jetpack's exporter** (no install; Jetpack 16.2+ on Pressable). Endpoint `https://{domain}/?reprint-api-jetpack`. "
              "The secret is created over the Jetpack connection (`POST /jetpack/v4/reprint/rotate-export-secret`) and the export "
              "window closes after one hour (`POST /jetpack/v4/reprint/enable-export` reopens it).\n"
              "- **Reprint plugin.** Install `reprint-exporter-wp.zip` from https://github.com/WordPress/reprint/releases on the "
              "source, then Tools → Reprint Server. Endpoint `https://{domain}/?reprint-api`.\n\n"
              "Follow whatever the Assistant's source step asks for.",
         verify="The Assistant's preflight step passes."),
    dict(id="sync.first", phase="sync", actor="human", title="Run the first sync in the Migration Assistant", when=None,
         body="Open the Migration Assistant for the target and run preflight, then migrate:\n\n"
              "{mc_assistant}\n\n"
              "Source URL: `https://{domain}/`. If preflight fails, read the message: redirects, TLS and storage warnings can be "
              "continued through; authentication failures cannot. Failures are also posted in `#reprint`.\n\n"
              "Note the start and end time of the migrate step.",
         verify="The Assistant reports the migration and cleanup steps complete. Record the duration: "
                "`state.py decide first_sync_minutes <n>`."),

    # ---------------------------------------------------------------- verify
    dict(id="verify.parity", phase="verify", actor="agent", title="Compare data between source and target", when=None,
         body="```bash\n{scripts}/wp_eval.sh pressable {domain} {scripts}/parity.php > {dir}/parity-source.json\n"
              "T51_ARGS='{{\"other_host\":\"{domain}\"}}' {scripts}/wp_eval.sh wpcom {target} {scripts}/parity.php > {dir}/parity-target.json\n"
              "python3 {scripts}/compare_parity.py {dir}/parity-source.json {dir}/parity-target.json\n```\n\n"
              "On a live source, small differences in recent rows are expected at this stage. Missing tables are not.",
         verify="No missing tables. Differences are explained by activity on the source since the sync."),
    dict(id="verify.jetpack", phase="verify", actor="agent", title="Check the target kept its own Jetpack connection", when=None,
         body="The source database, including the source's Jetpack options, is applied to the target. The WordPress.com cleanup "
              "step should restore the target's own connection. Confirm it did:\n\n"
              "```bash\nteam51 wpcom:run-site-wp-cli-command {target} 'option pluck jetpack_options id'\n```\n\n"
              "It must print the TARGET blog ID (`{target_blog_id}`), not the source's (`{source_blog_id}`).",
         verify="Blog ID matches the target. If it shows the source ID, stop and ask in `#reprint`: the two sites now claim one identity."),
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
              "For a visual comparison use the `site-launch-comparison` skill with the same two hosts.",
         verify="No URL that returns 200 on the source returns an error on the target. Redirect targets match apart from the host."),
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
    dict(id="platform.script", phase="platform", actor="agent", title="Start the post-sync script", when=None,
         body="Every sync REPLACES the target database, so any database change made on the target before the final sync is lost. "
              "Keep all such changes as commands in `{dir}/post-sync.sh` and run that file after every sync. File changes on the "
              "target survive re-syncs.\n\n"
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
    dict(id="platform.colophon", phase="platform", actor="agent", title="Remove the theme's Atlantis and colophon references", when=has("platform.colophon"),
         body="The active theme references Atlantis or its colophon. Removing the plugin without removing these breaks the footer. "
              "Follow the pattern of the recent `remove atlantis-dependent colophon` pull requests in `a8cteam51`, and add the "
              "standard footer credit if the partner's footer needs one.",
         verify="With Atlantis deactivated on the copy, the footer renders correctly."),
    dict(id="platform.deploy-connect", phase="platform", actor="agent", title="Connect WordPress.com GitHub Deployments", when=has("platform.deploy-connect"),
         body=UNTESTED +
              "The audit found the existing deploy connected and current, so connecting is safe.\n\n"
              "```bash\nteam51 wpcom:connect-site-repository {target} {repo_name} --branch {deploy_branch} --target_dir /wp-content/\n```\n\n"
              "This also creates the deployment webhook to OpsOasis. Note that the CLI creates the deployment as automatic: "
              "every push to the branch deploys. Without `--deploy` nothing is deployed until the next push. Deploy once on "
              "purpose and confirm the files on the target still match the repo.",
         verify="```bash\npython3 {scripts}/deploy_check.py drift --repo {repo} --rev <deployed sha> --host wpcom --site {target}\n```\nreports `clean`."),
    dict(id="platform.deploy-reconcile", phase="platform", actor="both", title="Reconcile server changes into the repo before connecting deploys", when=has("platform.deploy-reconcile"),
         body="Files on the server differ from the repo. Read `{dir}/deploy.json` for the list. Bring each real change into the "
              "repo through a pull request, deploy through the existing pipeline, and re-run the drift check until it is clean. "
              "Only then connect WordPress.com deploys (step `platform.deploy-connect`).",
         verify="`deploy_check.py drift` reports `clean`."),
    dict(id="platform.deploy-skip", phase="platform", actor="human", title="Leave deploys unconnected", when=has("platform.deploy-skip"),
         body="No deploy targets production, so connecting one risks overwriting files nobody has in git. Migrate the files as "
              "they are. Getting production code into a repo is a separate task; raise it if the partner wants it.",
         verify="No GitHub deployment is connected on the target."),

    # -------------------------------------------------------------- rehearse
    dict(id="sync.rehearse", phase="rehearse", actor="both", title="Rehearse the final sync and time it", when=None,
         body="Run the sync again from the Migration Assistant exactly as you will at cutover, then run `{dir}/post-sync.sh`, then "
              "the parity and URL checks. Time each part.\n\n{mc_assistant}",
         verify="The full sequence ran clean. Total minutes recorded with `state.py decide rehearsal_minutes <n>`: this is the freeze length."),
    dict(id="rehearse.mu-survives", phase="rehearse", actor="agent", title="Confirm target-side files survived the re-sync", when=None,
         body="```bash\n{scripts}/mu_plugin.sh status wpcom {target} t51-migration-quarantine.php\n```",
         verify="Still present. If it is gone, reinstall it and add the install to `post-sync.sh`."),
    dict(id="rehearse.ttl", phase="rehearse", actor="human", title="Lower DNS TTLs", when=None,
         body="At least 24 hours before cutover, lower the TTL on the site's A/CNAME records to 300 seconds in the current DNS host.",
         verify="`dig +noall +answer {domain}` shows the lower TTL."),

    # ------------------------------------------------------------------- cut
    dict(id="cut.go", phase="cut", actor="human", title="Go / no-go", when=None,
         body="Confirm: no open blockers; rehearsal clean; partner informed; registrar or DNS access available now; "
              "WooPayments move scheduled if applicable; someone available to roll back.",
         verify="Explicit go from the migration owner."),
    dict(id="cut.freeze", phase="cut", actor="agent", title="Freeze writes on the live site", when=None,
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
    dict(id="cut.final-sync", phase="cut", actor="human", title="Run the final sync", when=None,
         body="Run the sync in the Migration Assistant again.\n\n{mc_assistant}",
         verify="Migration and cleanup steps complete."),
    dict(id="cut.post-sync", phase="cut", actor="agent", title="Run the post-sync script", when=None,
         body="```bash\nbash {dir}/post-sync.sh\n```", verify="Exits 0."),
    dict(id="cut.parity", phase="cut", actor="agent", title="Prove parity", when=None,
         body="```bash\n{scripts}/wp_eval.sh pressable {domain} {scripts}/parity.php > {dir}/parity-source-final.json\n"
              "T51_ARGS='{{\"other_host\":\"{domain}\"}}' {scripts}/wp_eval.sh wpcom {target} {scripts}/parity.php > {dir}/parity-target-final.json\n"
              "python3 {scripts}/compare_parity.py {dir}/parity-source-final.json {dir}/parity-target-final.json\n```",
         verify="`RESULT: PARITY`. Any mismatch stops the cutover: unfreeze the source and investigate."),
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
    dict(id="cut.unquarantine", phase="cut", actor="agent", title="Remove the quarantine from the new site", when=None,
         body="Only once DNS resolves to the new site and the checks above pass.\n\n"
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
    dict(id="post.gateways", phase="post", actor="human", title="Place an order through each payment gateway", when=has("post.gateways"),
         body="One order per enabled gateway, then refund it. Check the order emails arrive. In each gateway's own dashboard, "
              "confirm webhook or callback deliveries are succeeding.",
         verify="Each order reaches the expected status and each gateway shows successful deliveries."),
    dict(id="post.woopayments", phase="post", actor="human", title="Complete the WooPayments account move", when=has("post.woopayments"),
         body="Confirm with WooPayments support that the account now belongs to blog ID `{target_blog_id}`. In wp-admin, "
              "Payments → Overview should show the existing account, not an onboarding prompt.",
         verify="A WooPayments test payment succeeds and appears in the account's transactions."),
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
    dict(id="post.atlantis", phase="post", actor="agent", title="Remove Atlantis from the new site", when=has("post.atlantis"),
         body="```bash\nteam51 wpcom:run-site-wp-cli-command {domain} 'plugin uninstall a8csp-atlantis --deactivate'\n```\n\n"
              "Drop any `A8CSP_ATLANTIS_*` constants that were carried over.",
         verify="`plugin list` does not show `a8csp-atlantis`. The footer renders correctly."),
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
         body="Blog Stats Merger (its own page): https://mc.a8c.com/merge-stats.php\n\n"
              "- Previous (source) blog ID: `{source_blog_id}`\n- Current (destination) blog ID: `{target_blog_id}`\n\n"
              "Click **Show existing merges for a blog** for the source first. Post IDs match because the database was copied, "
              "which is what the merge needs.",
         verify="The tool confirms the merge. Stats on the new site show history."),
    dict(id="post.subscribers", phase="post", actor="human", title="Migrate subscribers to the new blog ID", when=has("post.subscribers"),
         body="Blog Subscription Migration, a section of the Jetpack tools page: https://mc.a8c.com/jetpack-tools/\n\n"
              "(That page also contains the stats merger; use the separate link in the stats step for that.)\n\n"
              "- Source blog ID: `{source_blog_id}`\n- Destination blog ID: `{target_blog_id}`\n- Support reference: the Linear issue for this migration\n\n"
              "You get an email when it finishes.",
         verify="```bash\npython3 {scripts}/wpcom_facts.py {target_blog_id}\n```\nreports the subscriber count recorded in the audit."),
    dict(id="post.staging", phase="post", actor="both", title="Create a WordPress.com staging site", when=has("post.staging"),
         body=UNTESTED +
              "The Pressable development site is not migrated. A staging site is made from the new production site, so this can "
              "only happen after cutover.\n\n"
              "**With the Team 51 CLI:**\n\n"
              "```bash\nteam51 wpcom:clone-site {domain} --branch develop\n```\n\n"
              "From its source, this uses WordPress.com's own staging-site feature, then: sets the copy's environment type to "
              "`development`, rewrites URLs, rotates the admin password, installs SafetyNet as a mu-plugin (which deletes "
              "customers, orders and subscriptions on the copy and scrubs keys), and connects the production site's repo on the "
              "branch given, deploying it. `--skip-safety-net` leaves the copy unscrubbed. If production has no repo connected "
              "it asks whether to continue without one.\n\n"
              "**By hand:** Hosting → Staging site in the WordPress.com dashboard gives an unscrubbed copy with no deploy "
              "connected.\n\n"
              "OPEN QUESTIONS, ask before doing this on a store:\n"
              "- Is a scrubbed copy what this partner wants, given they are leaving Team 51?\n"
              "- WordPress.com can sync a staging site's database back to production. From a scrubbed copy that would delete "
              "real orders and customers. Is that sync blocked or guarded on SafetyNet copies?",
         verify="The staging site loads. If a branch was connected, a push to it deploys there. Production data is unchanged."),
    dict(id="post.stragglers", phase="post", actor="agent", title="Check the old site for writes after the freeze", when=None,
         body="Run once DNS has had time to propagate (at least the old TTL), and again a day later.\n\n"
              "```bash\nT51_ARGS='{{\"since\":\"<freeze time, UTC>\"}}' {scripts}/wp_eval.sh pressable {pressable_id} {scripts}/parity.php | python3 -c \"import json,sys;print(json.load(sys.stdin)['after_since'])\"\n```",
         verify="Every count is zero. Anything else is data on the old site only: port it by hand."),

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
    dict(id="decom.wait", phase="decom", actor="human", title="Wait before removing anything", when=None,
         body="Keep the Pressable site, frozen, for at least a week after cutover and until the straggler check has been zero "
              "twice and any zone move is complete.", verify="A week has passed with no issues."),
    dict(id="decom.deployhq", phase="decom", actor="human", title="Remove the DeployHQ project", when=None,
         body="Remove the DeployHQ servers and project for this site, and the DeployHQ webhook on the GitHub repo. Leave any "
              "project that serves a different site (for example a redesign) alone.",
         verify="`gh api repos/{repo}/hooks` shows no `deployhq.com` hook."),
    dict(id="decom.pressable", phase="decom", actor="human", title="Remove the Pressable sites", when=None,
         body="If the site had VideoPress content, do not start this until `post.videopress` is done: deleting or disconnecting "
              "the old site removes access to the original videos.\n\n"
              "Delete the production Pressable site (`{pressable_id}`) and the related sites the decisions say to delete. "
              "Delete the Pressable DNS zone only after name servers have moved.",
         verify="Sites no longer appear in `pressable_list_sites`."),
    dict(id="decom.records", phase="decom", actor="agent", title="Update records", when=None,
         body="Update the repo's GitHub custom properties (`site-url-production`, `wpcom-blog-id-production`) to the new blog ID, "
              "and any team site lists. Note the migration in the Linear issue with the old and new blog IDs.",
         verify="`gh api repos/{repo}/properties/values` shows the new blog ID."),

    # -------------------------------------------------------------- handover
    dict(id="handover.audit", phase="handover", actor="agent", title="Run the offboarding audit", when=None,
         body="When the partner accepts the site, run `/offboard-site-audit {domain}`. That command is not part of this plugin: it "
              "lives in `a8cteam51/ops-agent-skills` (`.claude/commands/offboard-site-audit.md`) and runs from a clone of that "
              "repo. It lists everything still tied to Team 51: site owner, plans, users, repo, deployments, licences.",
         verify="Its report exists and has been read."),
    dict(id="handover.transfer", phase="handover", actor="human", title="Transfer ownership and reconnect deploys", when=None,
         body="Transfer the WordPress.com site, the domain and the GitHub repo to the partner as the offboarding audit directs. "
              "Expect to redo: the GitHub Deployments connection (it is tied to the repo owner and the GitHub app installation), "
              "repo secrets, and branch protections. Remove the OpsOasis deployment webhook, `force-jetpack-sso`, and Team 51 users.",
         verify="The partner can deploy from their own repo and no Team 51 account has access."),
]


def build(manifest, switched_on):
    """Return the steps that apply, in order."""
    out = []
    for step in STEPS:
        cond = step.get("when")
        if cond is None or cond(manifest, switched_on):
            out.append(step)
    return out
