"""Runbook steps for a WordPress.com (Atomic) -> Pressable migration.

Each step: id, phase, title, actor (agent | human | both), when (function of the
manifest and the set of step IDs switched on by findings; None = always), body
(markdown; {placeholders} are filled from the manifest, so literal braces are
doubled), verify (how to know it worked).

Steps marked UNTESTED describe a procedure that has not yet been run end to
end. Treat them as the best current plan and correct them here after the first
real migration.

The order of this list is the order of the runbook.
"""
import re

PHASES = [
    ("decide", "1. Decisions and sign-off"),
    ("prep", "2. Prepare the Pressable site"),
    ("rehearse", "3. Rehearsal pull"),
    ("window", "4. Cutover window: final pull"),
    ("deploy", "5. Cutover window: switch deploys"),
    ("cut", "6. Cutover window: go live"),
    ("post", "7. After cutover"),
    ("decom", "8. Decommission"),
]

UNTESTED = "> UNTESTED: this procedure has not been run end to end yet. Correct it here after the first real migration.\n\n"

REMOTE = "T51_ARGS='{args}' {scripts}/wp_eval.sh pressable {pressable_id} {scripts}/reprint_remote.php"


def has(step_id):
    return lambda m, on: step_id in on


def remote(args):
    """A reprint_remote.php call. The JSON's own braces are doubled for format_map; {placeholders} inside it are kept."""
    held = re.sub(r"\{([a-z_]+)\}", "\x00\\1\x01", args)
    return REMOTE.replace("{args}", held.replace("{", "{{").replace("}", "}}").replace("\x00", "{").replace("\x01", "}"))


STEPS = [
    # ---------------------------------------------------------------- decide
    dict(id="decide.blockers", phase="decide", actor="human", title="Clear every blocker in the audit report", when=None,
         body="Open `REPORT.md`. Every item under **Blockers** must be resolved or explicitly accepted before the Pressable site is created.",
         verify="Re-running the build shows no open blockers, or each has a decision in `state.json`."),
    dict(id="decide.decisions", phase="decide", actor="human", title="Record the decisions the audit asks for", when=None,
         body="Each item under **Needs an answer** needs one:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} decide <key> \"<answer>\"\n```",
         verify="`state.json` has an entry under `decisions` for each."),
    dict(id="decide.window", phase="decide", actor="human", title="Agree the cutover window", when=None,
         body="The window holds the final pull, the checks, the deploy switch and the DNS change. The rehearsal (phase 3) gives "
              "real timings. Ask the partner, through the TAM, not to edit the site from the start of the window until they hear "
              "it has moved. The domain's DNS change is coordinated with whoever asked for the migration.",
         verify="Date and time recorded with `state.py decide cutover_window \"<when>\"`."),

    # ------------------------------------------------------------------ prep
    dict(id="prep.create-site", phase="prep", actor="both", title="Create the Pressable site, without a repository", when=None,
         body="Update the CLI first (`team51 --force-update list`): Pressable deploys changed recently.\n\n"
              "```bash\nteam51 pressable:create-site {site_name}\n```\n\n"
              "Answer **no** when it asks about a GitHub repository. With one, it connects Pressable's GitHub integration (or "
              "DeployHQ) and deploys straight away; here the integration is connected just before DNS (`deploy.connect`). "
              "The command installs Atlantis and marks the site managed.\n\n"
              "Record the new site:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} target --pressable-id <id> --domain <name>.mystagingwebsite.com\n"
              "python3 {scripts}/state.py --dir {dir} decide pressable_ips \"<ipAddressOne>, <ipAddressTwo>\"\n"
              "python3 {scripts}/build_audit.py --dir {dir}\n```\n\n"
              "The addresses come from `mcp__team51__pressable_get_site`; `cut.records` points the domain at them.",
         verify="`mcp__team51__pressable_get_site` returns the site; its temporary address answers 200."),
    dict(id="prep.collaborator", phase="prep", actor="agent", title="Add the partner as a Pressable collaborator", when=None,
         body="```bash\nteam51 pressable:create-site-collaborator {partner_collaborator} {pressable_id}\n```\n\n"
              "If the email is not recorded yet, ask the TAM and record it with `state.py decide partner_collaborator <email>`.",
         verify="`mcp__team51__pressable_list_collaborators` lists the email on the site."),
    dict(id="prep.php", phase="prep", actor="human", title="Match PHP {php_minor} on Pressable", when=None,
         body="MyPressable → the site → Settings → PHP version: `{php_minor}`.",
         verify="`probe` (next steps) reports PHP {php_minor}."),
    dict(id="prep.quarantine", phase="prep", actor="agent", title="Quarantine the Pressable site before anything is pulled", when=None,
         body="The pull brings the live site's Jetpack connection, mail settings and scheduled jobs. The quarantine mu-plugin keeps "
              "Jetpack offline, blocks email, cron and checkout, and noindexes the copy. It is a file, so the database import does "
              "not remove it. **Writes to the Pressable site.**\n\n"
              "```bash\n{scripts}/mu_plugin.sh install pressable {pressable_id} {assets}/t51-migration-quarantine.php\n```",
         verify="`{scripts}/mu_plugin.sh status pressable {pressable_id} t51-migration-quarantine.php` reports it present, and "
                "`curl -s https://{target}/wp-json/t51-migration/v1/quarantine` answers `active: true`."),
    dict(id="prep.atlantis-key", phase="prep", actor="both", title="Give Pressable the source's Atlantis encryption key",
         when=has("prep.atlantis-key"),
         body="Site creation wrote a new `A8CSP_ATLANTIS_ENCRYPTION_KEY` on Pressable. The pull brings the source's encrypted "
              "Atlantis data but not its wp-config, so with the new key the data reads as empty. The key is a secret: never print it.\n\n"
              "```bash\nprint_key='eval \"echo A8CSP_ATLANTIS_ENCRYPTION_KEY;\"'\n"
              "KEY=$(team51 wpcom:run-site-wp-cli-command {source_blog_id} \"$print_key\" -n --no-ansi </dev/null 2>&1 | grep -E '^[0-9a-f]{{64}}$')\n"
              "[ -n \"$KEY\" ] && team51 pressable:run-site-wp-cli-command \"config set A8CSP_ATLANTIS_ENCRYPTION_KEY $KEY --type=constant\" {pressable_id} -n --no-ansi </dev/null 2>&1 | grep -E '^(Success|Error)' | sed 's/ with the value.*//'\n"
              "unset KEY\n```\n\n"
              "In the other direction `config set` added a second, plain define after Atlantis's guarded one (2026-10-16), which a "
              "person then merged by hand over SFTP. Check the result the same way here.",
         verify="The fingerprints match (only a hash is printed):\n\n"
                "```bash\nfp='eval \"echo substr(hash(\\\"sha256\\\", A8CSP_ATLANTIS_ENCRYPTION_KEY), 0, 8);\"'\n"
                "team51 wpcom:run-site-wp-cli-command {source_blog_id} \"$fp\" -n --no-ansi </dev/null 2>&1 | tail -1\n"
                "team51 pressable:run-site-wp-cli-command \"$fp\" {pressable_id} -n --no-ansi </dev/null 2>&1 | tail -1\n```"),
    dict(id="prep.constants", phase="prep", actor="agent", title="Recreate the source's wp-config constants", when=has("prep.constants"),
         body="The report lists them. For each, read the value on the source and set it on Pressable in one shell line, the "
              "same way as the Atlantis key, without printing it. **Writes to the Pressable site.**",
         verify="`compare_sites.py` lists no constant missing on the target."),
    dict(id="prep.domain-account", phase="prep", actor="human", title="Find the WordPress.com account that holds the domain",
         when=has("prep.domain-account"),
         body="Store Admin, or the context-a8c `domains` provider (`get-domain-subscriptions` for {apex}). Whoever changes the "
              "DNS records in the window needs access to that account's domain management, or a Happiness Engineer does it.",
         verify="Account recorded: `state.py decide domain_account.{apex} <account>`."),
    dict(id="prep.zone-export", phase="prep", actor="human", title="Save a copy of the zone", when=has("prep.zone-export"),
         body="WordPress.com dashboard → Domains → {apex} → DNS records. Copy every record into `{dir}/zone-before.txt`. Only "
              "the apex and `www` change; this is the record of everything else, for checking afterwards.",
         verify="Every name in `dns-{apex}.json` appears in the file."),
    dict(id="prep.source-exporter", phase="prep", actor="human", title="Make the live site's Reprint exporter ready", when=None,
         body=UNTESTED +
              "The pull authenticates with a key pair made on Pressable (`rehearse.setup`). The live site has to accept its public "
              "key, called the Migration Token. Two ways, both a **write on the live site**, so get a yes first:\n\n"
              "1. **Reprint plugin** (simplest): install **Reprint** from WordPress.org on the live site and open **Tools → Reprint "
              "Server**. Its form takes the token.\n"
              "2. **Jetpack's built-in exporter**: Jetpack on Atomic ships Reprint; its token goes in through "
              "`POST jetpack/v4/reprint/install-public-key` with an administrator's Jetpack token. More moving parts; use it only if "
              "the plugin cannot be installed.\n\n"
              "The freeze mu-plugin lets both through (it exempts `?reprint-api-jetpack`, and the plugin answers before it runs).",
         verify="**Tools → Reprint Server** shows the form for a Migration Token."),
    dict(id="prep.opsoasis", phase="prep", actor="human", title="Tell Team 51 monitoring a migration is under way", when=None,
         body=UNTESTED +
              "OpsOasis watches the old blog ID and will watch the new site. Until the old site is gone, expect a Jetpack alert for "
              "the old blog ID after cutover, and a \"Production site added\" notice for the new one. Add a "
              "`site_health_monitor.known_issues` row for blog `{source_blog_id}` before cutover, and tell `#team51-pub-support`.",
         verify="The row exists. Recorded with `state.py decide opsoasis_prepared yes`."),

    # -------------------------------------------------------------- rehearse
    dict(id="rehearse.probe", phase="rehearse", actor="agent", title="Probe the Pressable site and test a background run", when=None,
         body=UNTESTED +
              "Read-only first: PHP, shell functions, extensions, writable places outside the web root, table prefix.\n\n"
              "```bash\n" + remote('{"action":"probe","work":"{work}"}') + "\n```\n\n"
              "Needs `exec` in `shell_functions`, `/tmp` writable and outside the web root, and table prefix `{source_prefix}` "
              "(the source's). Probed on another Pressable site (2026-11-17): all present, `max_execution_time` 0.\n\n"
              "Then check a background process outlives the WP-CLI call (**writes a small file in {work}**):\n\n"
              "```bash\n" + remote('{"action":"bgtest","work":"{work}"}') + "\n"
              "sleep 60; " + remote('{"action":"probe","work":"{work}"}') + " | python3 -c 'import json,sys; print(json.load(sys.stdin).get(\"bgtest\"))'\n```",
         verify="`bgtest.last` is close to `now` a minute after starting, so background runs survive and `/tmp` persists. If not, "
                "the pull runs in the foreground (resumable, re-run until it finishes) or on a laptop; record which."),
    dict(id="rehearse.setup", phase="rehearse", actor="both", title="Install the Reprint client on Pressable and authorize it", when=None,
         body=UNTESTED +
              "**Writes to the Pressable site** (the work directory only): downloads `reprint.phar` and makes a key pair. The "
              "private key stays in `{work}`.\n\n"
              "```bash\n" + remote('{"action":"setup","work":"{work}","source":"https://{domain}"}') + "\n```\n\n"
              "It prints a **Migration Token** (a public key). A person pastes it into **Tools → Reprint Server** on the live site "
              "and chooses **Authorize client**.",
         verify="The live site's Reprint screen lists the token as authorized, and the first pull below gets past preflight."),
    dict(id="rehearse.files", phase="rehearse", actor="agent", title="Pull wp-content onto Pressable", when=None,
         body=UNTESTED +
              "Only wp-content, without WordPress.com's platform plugins or the freeze file. **Writes to the work directory.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"files","source":"https://{domain}","new_site_url":"https://{target}","exclude":["{source_content_dir}/mu-plugins/t51-migration-freeze.php"]}') + "\n"
              + remote('{"action":"status","work":"{work}"}') + "\n```\n\n"
              "Repeat `status` until `files.exit` is 0. On a failure, run the same `run` again: Reprint resumes. Note the time it "
              "took; the window's final pull repeats this.",
         verify="`status` shows `files.exit` 0 and a `pulled_wp_content` path."),
    dict(id="rehearse.place", phase="rehearse", actor="agent", title="Put the pulled wp-content in place", when=None,
         body=UNTESTED +
              "Look first:\n\n```bash\n" + remote('{"action":"place","work":"{work}","dry_run":true}') + "\n```\n\n"
              "It skips platform files of both hosts, caches and the migration mu-plugins, and lists any file it would overwrite. "
              "On a new site the overwrites are only what create-site installed (Atlantis). Then, **writing to wp-content**:\n\n"
              "```bash\n" + remote('{"action":"place","work":"{work}"}') + "\n```",
         verify="`by_top_level` covers plugins, themes, mu-plugins and uploads, and `overwrites` holds nothing unexpected."),
    dict(id="rehearse.db", phase="rehearse", actor="agent", title="Pull the database into Pressable", when=None,
         body=UNTESTED +
              "Replaces this site's tables with the live site's and rewrites `https://{domain}` to `https://{target}`. The "
              "quarantine (a file) stays in force. **Replaces the Pressable database.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"db","source":"https://{domain}","new_site_url":"https://{target}"}') + "\n"
              + remote('{"action":"status","work":"{work}"}') + "\n```\n\n"
              "If anything fails, check the flags against the installed client: `" + remote('{"action":"help","work":"{work}","command":"pull-db"}') + "`.",
         verify="`db.exit` is 0, and `wp option get home` on Pressable returns `https://{target}`."),
    dict(id="rehearse.plugins", phase="rehearse", actor="agent", title="Install what WordPress.com supplied itself", when=None,
         body=UNTESTED +
              "```bash\n{scripts}/wp_eval.sh pressable {pressable_id} {scripts}/site_audit.php > {dir}/site-target.json\n"
              "python3 {scripts}/compare_sites.py {dir}/site.json {dir}/site-target.json\n```\n\n"
              "For each plugin missing on the target that was active on the source (Jetpack, Akismet, Jetpack Boost and the like), "
              "install the current stable release and activate it: "
              "`team51 pressable:run-site-wp-cli-command 'plugin install <slug> --activate' {pressable_id}`. Leave out plugins the "
              "report says are unused (an empty VideoPress, for example). **Writes to the Pressable site.**",
         verify="`compare_sites.py` reports no missing active plugin, no WordPress.com platform files, and the same theme."),
    dict(id="rehearse.web-root", phase="rehearse", actor="human", title="Copy files served from outside wp-content", when=has("rehearse.web-root"),
         body="The report lists them. The pull takes wp-content only; copy these to the same paths on Pressable over SFTP.",
         verify="Each listed URL answers the same on `{target}` as on `{domain}`."),
    dict(id="rehearse.verify", phase="rehearse", actor="agent", title="Check the rehearsal copy", when=None,
         body="Run the `wpcom-to-pressable-verify` skill at checkpoint `rehearsal`: parity, site comparison, URLs, front end and "
              "the database diff. On a live source, small differences in recent rows are expected until the window.",
         verify="No missing tables, plugins or theme; no missing assets or new errors on the front end."),
    dict(id="rehearse.human", phase="rehearse", actor="human", title="Look at the copy as a visitor and as an admin", when=None,
         body="Open `https://{target}`: the pages the partner cares about, forms (they will not send mail under quarantine), and "
              "wp-admin through MyPressable's login. The quarantine banner is expected.",
         verify="A person signs off the copy. Recorded with `state.py done rehearse.human \"<who>\"`."),

    # ---------------------------------------------------------------- window
    dict(id="window.freeze", phase="window", actor="agent", title="Freeze the live site", when=has("window.freeze"),
         body=UNTESTED +
              "**Writes to the live site.** Refuses writes from visitors; administrators, Jetpack and the Reprint exporter still work. "
              "It acts only on Atomic, and the pull leaves the file out.\n\n"
              "```bash\nT51_FREEZE_MODE=frozen {scripts}/mu_plugin.sh install wpcom {source_blog_id} {assets}/t51-migration-freeze.php\n```\n\n"
              "Note the time (UTC): the straggler check counts from it.",
         verify="`curl -s https://{domain}/wp-json/t51-migration/v1/freeze` answers `active: true`."),
    dict(id="window.start", phase="window", actor="human", title="Start the window", when=None,
         body="Tell the partner (through the TAM) the window has started and not to edit. Note the time (UTC) for the straggler check:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} decide window_started \"$(date -u '+%Y-%m-%d %H:%M:%S')\"\n```",
         verify="The time is recorded."),
    dict(id="window.pull", phase="window", actor="agent", title="Final pull: files, then database", when=None,
         body=UNTESTED +
              "Same commands as the rehearsal, with the same work directory, so only changes come down. **Replaces the Pressable "
              "database.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"files","source":"https://{domain}","new_site_url":"https://{target}","exclude":["{source_content_dir}/mu-plugins/t51-migration-freeze.php"]}') + "\n"
              "# when files.exit is 0:\n"
              + remote('{"action":"place","work":"{work}"}') + "\n"
              + remote('{"action":"run","work":"{work}","step":"db","source":"https://{domain}","new_site_url":"https://{target}"}') + "\n"
              + remote('{"action":"status","work":"{work}"}') + "\n```\n\n"
              "The database import replaces the tables, so anything installed or changed on Pressable since the rehearsal's import "
              "that lives in the database (plugin activation, options) is lost. Re-run `rehearse.plugins`' activation.",
         verify="Both exits are 0 and `compare_sites.py` matches the rehearsal result."),
    dict(id="window.verify", phase="window", actor="agent", title="Check the final copy: the go-live gate", when=None,
         body="Run the `wpcom-to-pressable-verify` skill at checkpoint `final`. The database diff must report NO GAPS, or each "
              "gap must be explained and recorded.",
         verify="Go: `db_diff.py` exits 0 or every gap is recorded. No-go: remove the freeze, tell the partner, stop."),

    # ---------------------------------------------------------------- deploy
    dict(id="deploy.wpcom-disconnect", phase="deploy", actor="human", title="Disconnect WordPress.com GitHub Deployments",
         when=has("deploy.wpcom-disconnect"),
         body="WordPress.com dashboard → the site → Deployments: disconnect `{repo}`. This comes before the allowlist: WordPress.com "
              "deployments ignore its `!` lines and copy nothing.",
         verify="No deployment is listed for the site."),
    dict(id="deploy.prepare", phase="deploy", actor="agent", title="Write the Pressable allowlist into .deployignore", when=None,
         body="Pressable's GitHub integration deletes every file on the site the repo lacks, unless `.deployignore` protects it. "
              "This command reads the Pressable site's files (after the final pull, so it sees every plugin and upload), writes the "
              "`# BEGIN Pressable deploy allowlist` block as the last thing in the file, removes `!` lines outside it, saves a "
              "snapshot of wp-content and opens a PR into `{branch}`:\n\n"
              "```bash\nteam51 pressable:prepare-site-repository {pressable_id} --repository={repo_name} --branch={branch}\n```\n\n"
              "Review and merge the PR (squash).",
         verify="`team51 pressable:prepare-site-repository {pressable_id} --repository={repo_name} --branch={branch} --check` reports "
                "the file current."),
    dict(id="deploy.connect", phase="deploy", actor="agent", title="Connect Pressable's GitHub integration", when=None,
         body="It refuses an unsafe first deploy, shows what the deploy would delete, saves a snapshot and waits for the deploy. "
              "**Deploys to the Pressable site.**\n\n"
              "```bash\nteam51 pressable:connect-site-repository {pressable_id} {repo_name} --branch={branch}\n```",
         verify="`team51 pressable:list-site-git-deploys {pressable_id}` shows a finished deploy, and `compare_sites.py` still "
                "matches."),

    # -------------------------------------------------------------------- cut
    dict(id="cut.add-domain", phase="cut", actor="both", title="Add {domain} to the Pressable site", when=None,
         body=UNTESTED +
              "Pressable and WordPress.com are both WP Cloud. A domain attached to the Atomic site is expected to need an "
              "`atomic-domain-…` TXT record before Pressable accepts it; `choice.{apex}` already has one for its Pressable site in "
              "this zone.\n\n"
              "```bash\nteam51 pressable:add-site-domain {pressable_id} {domain}\nteam51 pressable:add-site-domain {pressable_id} www.{domain}\n```\n\n"
              "If it asks for verification, add the TXT values it shows in the WordPress.com zone and retry. Do not set primary yet.",
         verify="`mcp__team51__pressable_list_site_domains` lists both."),
    dict(id="cut.detach-domain", phase="cut", actor="human", title="Detach the domain from the WordPress.com site", when=None,
         body=UNTESTED +
              "WordPress.com dashboard → Domains → {apex}: disconnect it from the site, keeping it as a registration on the "
              "account. The Atomic site falls back to its own address. **The live site stops answering on {domain} here** until the "
              "next step's records are in, so do the two together.",
         verify="The domain's page shows no site attached, and its DNS records are editable."),
    dict(id="cut.records", phase="cut", actor="human", title="Point the apex and www at Pressable", when=None,
         body=UNTESTED +
              "In the WordPress.com zone for {apex}, change only the site's records:\n\n"
              "- apex `A` → `{pressable_ips}` (the Pressable site's addresses)\n"
              "- `www` → `CNAME {apex}`\n\n"
              "Leave MX, SPF, DKIM, DMARC, verification records, `choice.` and its TXT exactly as they are. Then set the "
              "domain primary on Pressable:\n\n"
              "```bash\nteam51 pressable:add-site-domain {pressable_id} {domain} --primary\n```",
         verify="```bash\nfor r in 1.1.1.1 8.8.8.8 9.9.9.9; do echo \"$r: $(dig +short {apex} @$r | tr '\\n' ' ') | www: $(dig +short www.{apex} @$r | tr '\\n' ' ')\"; done\n"
                "curl -sL https://{domain}/.well-known/hosting-provider; echo; curl -sI https://{domain} | head -5\n```\n\n"
                "Pressable's addresses from every resolver, a valid certificate, and `wp option get home` on Pressable returns "
                "`https://{domain}`. If it still holds the temporary address, run `wp search-replace https://{target} https://{domain} --all-tables` there."),
    dict(id="cut.jetpack", phase="cut", actor="both", title="Replace the copied Jetpack connection with a new one", when=None,
         body=UNTESTED +
              "The copy still holds the live site's connection tokens; the quarantine has kept Jetpack offline. Delete them, then "
              "connect afresh. **Writes to the Pressable site.**\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'option delete jetpack_options jetpack_private_options' {pressable_id}\n"
              "{scripts}/mu_plugin.sh remove pressable {pressable_id} t51-migration-quarantine.php\n```\n\n"
              "Then a person connects Jetpack in wp-admin as the Team 51 account, and records the new blog ID:\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} target --blog-id <new blog ID>\npython3 {scripts}/build_audit.py --dir {dir}\n```\n\n"
              "Never reconnect the old WordPress.com site, and never use Jetpack's \"migrate\" identity-crisis option on Pressable: "
              "the old blog ID stays with the old site.",
         verify="The Jetpack debug tool (`https://jptools.wordpress.com/debug/?url={domain}`) shows a healthy connection on a new "
                "blog ID, and the quarantine is gone (`mu_plugin.sh status`)."),
    dict(id="cut.smoke", phase="cut", actor="human", title="Smoke test the live site", when=None,
         body="Home page, key pages, a form submission (it now sends mail), wp-admin login, and the front-end check against the "
              "pre-window baseline (verify skill, checkpoint `live`).",
         verify="A person signs off. Tell the partner the site has moved."),

    # ------------------------------------------------------------------- post
    dict(id="post.stragglers", phase="post", actor="agent", title="Check nothing was written to the old site in the window", when=None,
         body="The old site is still live at its WordPress.com address. Count rows written since the window started:\n\n"
              "```bash\nT51_ARGS='{{\"since\":\"{window_started}\"}}' {scripts}/wp_eval.sh wpcom {source_blog_id} {scripts}/parity.php \\\n"
              "  | python3 -c \"import json,sys; print(json.load(sys.stdin)['after_since'])\"\n```",
         verify="All counts zero, or each row copied across by hand."),
    dict(id="post.subscribers", phase="post", actor="human", title="Migrate subscribers to the new blog ID", when=has("post.subscribers"),
         body="Blog Subscription Migration, on https://mc.a8c.com/jetpack-tools/\n\n- Source blog ID: `{source_blog_id}`\n"
              "- Destination blog ID: `{target_blog_id}`\n- Support reference: the Linear issue",
         verify="`python3 {scripts}/wpcom_facts.py {target_blog_id}` reports the audit's subscriber count."),
    dict(id="post.stats", phase="post", actor="human", title="Merge stats into the new blog ID", when=has("post.stats"),
         body="https://mc.a8c.com/merge-stats.php — previous blog `{source_blog_id}`, current blog `{target_blog_id}`.",
         verify="**Show existing merges** lists `report_blog_id` = `{target_blog_id}` and `include_blog_id` = `{source_blog_id}`."),
    dict(id="post.jetpack-products", phase="post", actor="human", title="Move or let go of paid Jetpack products", when=has("post.jetpack-products"),
         body="As decided in the audit: apply a licence on the new connection, or note that the product lapses with the old site.",
         verify="The decision is carried out and recorded."),
    dict(id="post.videopress", phase="post", actor="human", title="Move VideoPress videos", when=has("post.videopress"),
         body="With the VideoPress team, as agreed. The old site is not deleted until every video plays on the new one.",
         verify="Every video plays on {domain}."),
    dict(id="post.woopayments", phase="post", actor="human", title="Re-link WooPayments", when=has("post.woopayments"),
         body="The WooPayments team switches the existing account to blog `{target_blog_id}`. Nobody onboards afresh.",
         verify="Payments settings show the original account."),
    dict(id="post.monitoring", phase="post", actor="agent", title="Check Team 51 monitoring picked up the new site", when=None,
         body="Atlantis active and reporting, Jetpack Monitor on with the OpsOasis webhook "
              "(`team51 jetpack-monitor:register-webhook`), PHP fatals scanning covering the Pressable site.",
         verify="The next daily health check lists the site without problems."),

    # ------------------------------------------------------------------ decom
    dict(id="decom.wait", phase="decom", actor="human", title="Keep the old site for an agreed period", when=None,
         body="Two weeks is usual. The old WordPress.com site stays as it is (frozen, if it was) so anything missed can be recovered.",
         verify="The date is agreed and recorded with `state.py decide decommission_after <date>`."),
    dict(id="decom.reprint", phase="decom", actor="agent", title="Remove the Reprint client and access", when=None,
         body="**Deletes the work directory on Pressable** (private key, state and downloaded copy):\n\n"
              "```bash\n" + remote('{"action":"cleanup","work":"{work}"}') + "\n```\n\n"
              "On the old site, remove the Migration Token in **Tools → Reprint Server** and delete the Reprint plugin.",
         verify="`probe` with the same work directory reports it does not exist."),
    dict(id="decom.plan", phase="decom", actor="human", title="Cancel the WordPress.com plan, keep the domain", when=None,
         body="After the agreed period: cancel the old site's plan, keep the domain registration (and any email product on it). "
              "Check the domain's renewal is not tied to the plan being cancelled.",
         verify="The plan is cancelled; the domain still resolves to Pressable and mail works."),
    dict(id="decom.opsoasis", phase="decom", actor="human", title="Tidy Team 51 monitoring", when=None,
         body="Remove the `known_issues` row for blog `{source_blog_id}` once the old site is gone.",
         verify="`wp opsoasis doctor` is clean."),
]


def build(manifest, switched_on):
    return [s for s in STEPS if s["when"] is None or s["when"](manifest, switched_on)]
