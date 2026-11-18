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
              "Atlantis writes its key as one guarded line, `if ( ! defined( '…' ) ) {{ define( … ); }}`, which `config set` does "
              "not recognise: on its own it adds a plain define AFTER that line, and the guarded one wins (2026-10-16, fixed then "
              "by hand over SFTP). Anchoring the new define before the guarded line makes it win instead; the guarded line is "
              "then skipped and can stay. UNTESTED in this form:\n\n"
              "```bash\nKEY=$(team51 wpcom:run-site-wp-cli-command {source_blog_id} \"$print_key\" -n --no-ansi </dev/null 2>&1 | grep -E '^[0-9a-f]{{64}}$')\n"
              "[ -n \"$KEY\" ] && team51 pressable:run-site-wp-cli-command \"config set A8CSP_ATLANTIS_ENCRYPTION_KEY $KEY --type=constant --anchor=\\\"if ( ! defined( 'A8CSP_ATLANTIS_ENCRYPTION_KEY' ) )\\\" --placement=before\" {pressable_id} -n --no-ansi </dev/null 2>&1 | grep -E '^(Success|Error)' | sed 's/ with the value.*//'\n"
              "unset KEY\n```\n\n"
              "Use this second command instead of the `config set` above.",
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
         body="WordPress.com's DNS screen (Domains → {apex} → DNS records) has no export, and DNS cannot list a zone. A person "
              "lists the names from that screen (screenshots work; long names overflow into the value column), one per line, "
              "into `{dir}/zone-names.txt`. The script then reads every value from the name server, so a misread name shows up "
              "as missing rather than wrong:\n\n"
              "```bash\npython3 {scripts}/zone_snapshot.py {apex} --names {dir}/zone-names.txt --out {dir}/zone-before.txt\n```\n\n"
              "Only the apex (and `www`, if it has its own record) change; this is the record of everything else.",
         verify="The script reports no names without an answer, and every name in `dns-{apex}.json` is in the file."),
    dict(id="prep.source-exporter", phase="prep", actor="human", title="Make the live site's Reprint exporter ready", when=None,
         body="The pull authenticates with a key pair made on Pressable (`rehearse.setup`). The live site has to accept its public "
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
         body="Read-only first: PHP, shell functions, extensions, writable places outside the web root, table prefix.\n\n"
              "```bash\n" + remote('{"action":"probe","work":"{work}"}') + "\n```\n\n"
              "Needs `exec` in `shell_functions`, `/tmp` writable and outside the web root, and table prefix `{source_prefix}` "
              "(the source's). Probed on another Pressable site (2026-11-17): all present, `max_execution_time` 0.\n\n"
              "Then check a background process outlives the WP-CLI call (**writes a small file in {work}**):\n\n"
              "```bash\n" + remote('{"action":"bgtest","work":"{work}"}') + "\n"
              "sleep 60; " + remote('{"action":"probe","work":"{work}"}') + " | python3 -c 'import json,sys; print(json.load(sys.stdin).get(\"bgtest\"))'\n```",
         verify="`work` still exists on the second probe (`/tmp` persists between calls). `bgtest.last` close to `now` would "
                "mean background runs survive; on Pressable they did not (2026-11-17: each WP-CLI call gets its own container), "
                "so the runbook's pulls run with `\"foreground\": true`, which holds the call open until the pull ends."),
    dict(id="rehearse.setup", phase="rehearse", actor="both", title="Install the Reprint client on Pressable and authorize it", when=None,
         body="**Writes to the Pressable site** (the work directory only): downloads `reprint.phar` and makes a key pair. The "
              "private key stays in `{work}`.\n\n"
              "```bash\n" + remote('{"action":"setup","work":"{work}","source":"https://{domain}"}') + "\n```\n\n"
              "It prints a **Migration Token** (a public key). A person pastes it into **Tools → Reprint Server** on the live site "
              "and chooses **Authorize client**.",
         verify="The live site's Reprint screen lists the token as authorized, and the first pull below gets past preflight."),
    dict(id="rehearse.files", phase="rehearse", actor="agent", title="Pull wp-content onto Pressable", when=None,
         body="Only wp-content, without WordPress.com's platform plugins or the freeze file. **Writes to the work directory.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"files","foreground":true,"source":"https://{domain}/?reprint-api","new_site_url":"https://{target}","exclude":["{source_content_dir}/mu-plugins/t51-migration-freeze.php"]}') + "\n"
              + remote('{"action":"status","work":"{work}"}') + "\n```\n\n"
              "It returns when the pull ends (`exit` 0) or at `max_seconds` (exit 124). On anything but 0, run the same command "
              "again: Reprint resumes. Note `seconds`; the window's final pull repeats this.",
         verify="`status` shows `files.exit` 0 and a `pulled_wp_content` path."),
    dict(id="rehearse.place", phase="rehearse", actor="agent", title="Put the pulled wp-content in place", when=None,
         body="Look first:\n\n```bash\n" + remote('{"action":"place","work":"{work}","dry_run":true}') + "\n```\n\n"
              "It skips platform files of both hosts, caches and the migration mu-plugins, and lists any file it would overwrite. "
              "On a new site the overwrites are only what create-site installed (Atlantis). Then, **writing to wp-content**:\n\n"
              "```bash\n" + remote('{"action":"place","work":"{work}"}') + "\n```",
         verify="`by_top_level` covers plugins, themes, mu-plugins and uploads, and `overwrites` holds nothing unexpected."),
    dict(id="rehearse.db", phase="rehearse", actor="agent", title="Pull the database into Pressable", when=None,
         body="Replaces this site's tables with the live site's and rewrites `https://{domain}` to `https://{target}`. The "
              "quarantine (a file) stays in force. **Replaces the Pressable database.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"db","foreground":true,"source":"https://{domain}/?reprint-api","new_site_url":"https://{target}"}') + "\n"
              + remote('{"action":"status","work":"{work}"}') + "\n```\n\n"
              "If anything fails, check the flags against the installed client: `" + remote('{"action":"help","work":"{work}","command":"pull-db"}') + "`.",
         verify="`db.exit` is 0, and `wp option get home` on Pressable returns `https://{target}`."),
    dict(id="rehearse.users", phase="rehearse", actor="agent", title="Restore the Team 51 login after the import", when=None,
         body="The import replaced the users table with the live site's. The concierge user site creation made, and the "
              "password it saved in 1Password, are gone; the live site's users (Team 51's account, the partner's, any others) "
              "came across with their WordPress.com-linked accounts. Rotate the concierge password so 1Password matches again. "
              "**Writes to the Pressable site and 1Password.**\n\n"
              "```bash\nteam51 pressable:rotate-site-wp-user-password {pressable_id} --user=concierge@wordpress.com\n```",
         verify="Logging in to `https://{target}/wp-admin` with the 1Password entry works, and MyPressable's WP Admin button logs in."),
    dict(id="rehearse.plugins", phase="rehearse", actor="agent", title="Install what WordPress.com supplied itself", when=None,
         body="```bash\n{scripts}/wp_eval.sh pressable {pressable_id} {scripts}/site_audit.php > {dir}/site-target.json\n"
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
         body="Same commands as the rehearsal, with the same work directory, so only changes come down. **Replaces the Pressable "
              "database.**\n\n"
              "```bash\n" + remote('{"action":"run","work":"{work}","step":"files","foreground":true,"source":"https://{domain}/?reprint-api","new_site_url":"https://{target}","exclude":["{source_content_dir}/mu-plugins/t51-migration-freeze.php"]}') + "\n"
              "# when files.exit is 0:\n"
              + remote('{"action":"place","work":"{work}"}') + "\n"
              + remote('{"action":"run","work":"{work}","step":"db","foreground":true,"source":"https://{domain}/?reprint-api","new_site_url":"https://{target}"}') + "\n"
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
    dict(id="cut.old-site", phase="cut", actor="agent", title="Finish with the old site while the CLI can still reach it", when=None,
         body="Once the domain moves, the team51 CLI cannot reach the old site for a while: it goes through WordPress.com's API "
              "at the old site's primary domain, which then lands on Pressable (\"api_not_found … jetpack.jsonAPI does not exist\"). "
              "It works again once WordPress.com moves the old site to its `*.wpcomstaging.com` address (thinkbiggerinnovation.com, "
              "2026-11-18). So, just before the DNS change, count what the old site took since the window started and take its "
              "Jetpack Monitor webhook off:\n\n"
              "```bash\nT51_ARGS='{{\"since\":\"{window_started}\"}}' {scripts}/wp_eval.sh wpcom {source_blog_id} {scripts}/parity.php \\\n"
              "  | python3 -c \"import json,sys; print(json.load(sys.stdin)['after_since'])\"\n"
              "team51 jetpack-monitor:register-webhook {source_blog_id} --deregister\n```\n\n"
              "With the webhook gone, an outage during the cutover is not reported until `post.monitoring` registers the new blog.",
         verify="Counts zero (or each row ported), and `register-webhook {source_blog_id} --list` shows webhook `none`."),
    dict(id="cut.add-domain", phase="cut", actor="both", title="Add {domain} to the Pressable site", when=None,
         body="The registration, the name servers and every other record stay at WordPress.com. Nothing changes for visitors in "
              "this step: WP Cloud keeps sending {domain} to the Atomic site until Pressable has provisioned it (next step). "
              "There is no need to detach the domain from the Atomic site.\n\n"
              "```bash\nteam51 pressable:add-site-domain {pressable_id} {domain}\nteam51 pressable:add-site-domain {pressable_id} www.{domain}\n```\n\n"
              "Pressable makes the first domain primary by itself and the CLI then runs `wp search-replace` from the temporary "
              "address to {domain}; `--primary` is not needed (2026-11-18).\n\n"
              "Pressable writes the records it wants into its own DNS zone for the domain (MyPressable → the site → DNS): an "
              "`atomic-domain-…` TXT for the apex and one for `www`, and `openhosting1/2._domainkey` CNAMEs. That zone is not the "
              "one the internet sees. Copy the two TXT values (full length, with the copy buttons) into the **WordPress.com** zone, "
              "at `@` and `www`. Check the DKIM CNAMEs are already there (they usually are); add any that are not.\n\n"
              "`www` covered only by a wildcard (`* CNAME {apex}`, see `zone-before.txt`): a TXT at `www` makes `www` exist as a "
              "name, and the wildcard stops answering for it, so `www` would stop resolving. Add `www` `A` records for "
              "`{pressable_ips}` **before** its TXT. Today Pressable's addresses send `www` to the Atomic site as well, so this "
              "changes nothing for visitors.\n\n"
              "```bash\nfor n in {apex} www.{apex}; do dig +short TXT $n @ns1.wordpress.com | grep atomic; dig +short A $n @ns1.wordpress.com; done\n```",
         verify="`mcp__team51__pressable_list_site_domains` lists both (`provisioned` is still false), and both TXT values come "
                "back from `ns1.wordpress.com` exactly as Pressable shows them."),
    dict(id="cut.records", phase="cut", actor="human", title="Point the apex at Pressable", when=None,
         body="In the WordPress.com DNS screen for {apex}, **add** two apex `A` records, `{pressable_ips}`. The \"Handled by "
              "WordPress.com\" `A` row cannot be edited, only deleted; adding the first custom apex `A` removes it by itself "
              "(2026-11-18). There is no gap: Pressable's addresses keep serving the Atomic site until the handover.\n\n"
              "Leave every other record exactly as it is, then check nothing else moved:\n\n"
              "```bash\npython3 {scripts}/zone_snapshot.py {apex} --names {dir}/zone-before.txt --diff {dir}/zone-before.txt\n```\n\n"
              "The only differences should be the apex `A` lines and the apex `atomic-domain` TXT (`www` is not in the names "
              "file unless it had its own record; check it with `dig`). Put back anything else that went.\n\n"
              "**The handover.** Pressable shows both domains `provisioned` and `healthy` a few minutes after the apex points at "
              "it, and only then does WP Cloud send {domain} to the Pressable site. Tell the hosts apart by `host-header` "
              "(`WordPress.com` on the Atomic site, `wpcloud` on Pressable) or by the quarantine's noindex. Not by `x-ac`: it "
              "names the edge pool and reads `_atomic_…` on both.\n\n"
              "```bash\ncurl -s -D - -o /tmp/home.html \"https://{domain}/?nocache=$RANDOM\" | grep -iE '^HTTP|^host-header'; grep -o \"<meta name='robots'[^>]*>\" /tmp/home.html\n```\n\n"
              "Rollback: delete the two new records and add `A` records with the values in `zone-before.txt`.",
         verify="```bash\nfor r in 1.1.1.1 8.8.8.8 9.9.9.9; do echo \"$r: $(dig +short {apex} @$r | tr '\\n' ' ') | www: $(dig +short www.{apex} @$r | tr '\\n' ' ')\"; done\n"
                "curl -sI https://www.{domain} | grep -iE '^HTTP|^location'\n```\n\n"
                "Pressable's addresses from every resolver; both domains `provisioned` and `healthy`; `host-header: wpcloud` with "
                "the quarantine's noindex; `www` redirects to the apex; a valid certificate (WP Cloud's shared "
                "`tls.automattic.com` lists {domain})."),
    dict(id="cut.jetpack", phase="cut", actor="both", title="Replace the copied Jetpack connection", when=None,
         body="Only after the handover: connecting makes WordPress.com call the site at {domain}, which before then reaches the "
              "old site. The copy still holds the live site's connection tokens and the quarantine has kept Jetpack offline. "
              "Delete them and take the quarantine off (that also ends the noindex). **Writes to the live site.**\n\n"
              "```bash\nteam51 pressable:run-site-wp-cli-command 'option delete jetpack_options jetpack_private_options' {pressable_id}\n"
              "{scripts}/mu_plugin.sh remove pressable {pressable_id} t51-migration-quarantine.php\n"
              "team51 pressable:run-site-wp-cli-command 'cache flush' {pressable_id}\n```\n\n"
              "Then a person connects Jetpack in wp-admin as the Team 51 account. Never the \"migrate\" identity-crisis option, "
              "and never reconnect the old WordPress.com site: the old blog ID stays with it.\n\n"
              "WordPress.com picks the blog by URL, so the connection may land on a blog that already holds {domain}, such as the "
              "domain's Jetpack site from an earlier host. thinkbiggerinnovation.com reused its 2023 blog, Team 51-owned, with an "
              "active Jetpack Complete plan (2026-11-18). That is fine, but look at it before going on: owner, plan, subscribers, "
              "and Jetpack Social connections (an old account with auto-share on would post every new post to it).\n\n"
              "```bash\npython3 {scripts}/state.py --dir {dir} target --blog-id <blog ID>\npython3 {scripts}/build_audit.py --dir {dir}\n```",
         verify="On Pressable: connected, with an owner, not offline, no identity crisis, on a blog ID other than "
                "`{source_blog_id}`; `compare_sites.py` lists no Jetpack REST namespaces missing; the quarantine is gone "
                "(`mu_plugin.sh status`) and the home page has no noindex."),
    dict(id="cut.smoke", phase="cut", actor="human", title="Smoke test the live site", when=None,
         body="Home page, key pages, a form submission (it now sends mail), wp-admin login, and the front-end check against the "
              "pre-window baseline (verify skill, checkpoint `live`).",
         verify="A person signs off. Tell the partner the site has moved."),

    # ------------------------------------------------------------------- post
    dict(id="post.stragglers", phase="post", actor="both", title="Check nothing was written to the old site in the window", when=None,
         body="`cut.old-site` counted up to the DNS change. For the time since, read the old site's **Activity Log** in the "
              "WordPress.com dashboard (blog `{source_blog_id}`) for content changes after `{window_started}` UTC. Once the old "
              "site has moved to its `*.wpcomstaging.com` address the CLI reaches it again, and the `cut.old-site` command works.",
         verify="No content changes, or each one copied across by hand."),
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
         body="Register the OpsOasis webhook on the new blog; Jetpack Monitor comes on with the connection but without it. "
              "**Adds a webhook to the site's Monitor settings.**\n\n"
              "```bash\nteam51 jetpack-monitor:register-webhook {target_blog_id}\n"
              "team51 jetpack-monitor:register-webhook {target_blog_id} {source_blog_id} --list\n"
              "team51 wpcom:atlantis-status --site={target_blog_id} --no-prod --no-issues-only\n"
              "team51 atlantis:mark-managed {pressable_id} --host=pressable --dry-run\n```\n\n"
              "If the old blog still shows webhook `ours` (its deregister failed in `cut.old-site`), deregister it once the CLI "
              "reaches the old site again, or a downtime alert arrives twice.",
         verify="New blog: webhook `ours`; old blog: `none`. Atlantis reporting with its modules on; the site already managed. "
                "The next daily health check lists the site without problems."),

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
    dict(id="decom.wpcom-sites", phase="decom", actor="human", title="Retire the old WordPress.com sites", when=has("decom.wpcom-sites"),
         body="The report lists them: the old production blog `{source_blog_id}`, its staging site, and any stale blog on the "
              "same name. Delete each (or ask a Happiness Engineer to) once the agreed period is over and the plan is cancelled. "
              "The old site's subscribers and stats must already be on the new blog ID. **Never retire `{target_blog_id}`**: if "
              "Jetpack reused a blog the audit called stale, it is now the live site's.",
         verify="Blog RC shows each one deleted; the domain still resolves to Pressable."),
    dict(id="decom.opsoasis", phase="decom", actor="human", title="Tidy Team 51 monitoring", when=None,
         body="Remove the `known_issues` row for blog `{source_blog_id}` once the old site is gone.",
         verify="`wp opsoasis doctor` is clean."),
]


def build(manifest, switched_on):
    return [s for s in STEPS if s["when"] is None or s["when"](manifest, switched_on)]
