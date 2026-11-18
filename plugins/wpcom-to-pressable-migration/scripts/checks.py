"""The audit's check catalogue for a WordPress.com (Atomic) -> Pressable migration.

Each check is a function that takes the merged manifest and returns a list of
findings. A finding is a dict:

    id        stable identifier, e.g. "jetpack.subscribers"
    area      report section
    severity  blocker | decision | manual | auto | info
    title     one line
    detail    what was found (facts from the manifest)
    action    what to do about it
    steps     runbook step IDs this finding switches on (optional)

Severities:
    blocker   do not schedule the migration until resolved
    decision  someone has to choose before work starts
    manual    a person does this during the migration
    auto      an agent or script does this during the migration
    info      worth knowing; no action on its own

Adding a check: write a function, decorate it with @check, return findings.
Every surprise in a real migration should become a check here.
"""

CHECKS = []

# Rules that are already settled for every migration. The audit applies them and says so; it does not ask anyone to
# decide them again. Change them here, not per site.
STANDING_RULES = [
    "The site stays Team 51-managed on Pressable: Atlantis, monitoring and Team 51 accounts stay. The partner is added as a Pressable collaborator.",
    "The copy is made with Reprint, run on the new Pressable site, pulling from the live site. It can be run again: a rehearsal first, then a final pull in the cutover window.",
    "The Pressable site is created with `team51 pressable:create-site` without a repository. Pressable's GitHub integration is connected just before the DNS change, never through DeployHQ.",
    "A domain registered at WordPress.com stays registered there, with its DNS at WordPress.com, unless the task says otherwise. Only the site's own records change.",
    "Jetpack on Pressable gets a new blog ID. Subscribers are migrated, and stats merged where the Stats module was on.",
    "SafetyNet is never installed on the new production site.",
]

# Who can answer or do each finding, by ID prefix. First match wins.
OWNERS = [
    ("jetpack.products", "TAM, with the Jetpack licensing team"),
    ("jetpack.", "Developer (MC tools, after cutover)"),
    ("videopress.", "Developer, with the VideoPress team"),
    ("dns.access.", "TAM, with the partner"),
    ("dns.", "Developer"),
    ("woo.", "Developer, with the WooPayments team (#woosupport)"),
    ("estate.", "TAM"),
    ("writes.", "TAM agrees the window with the partner"),
    ("billing.", "TAM"),
    ("access.", "Developer"),
    ("context.", "TAM"),
]

SEVERITY_ORDER = ["blocker", "decision", "manual", "auto", "info"]

# What WordPress.com supplies itself and Reprint leaves behind (--exclude-host-plugins), or that only runs there.
WPCOM_PLATFORM = {"wpcomsh", "woocommerce-fraud-protection", "page-optimize"}
# Plugins Atomic keeps in a shared platform copy. Whether a pull brings them is checked after the first pull, and
# anything missing is installed on Pressable from WordPress.org.
WPCOM_MANAGED_PLUGINS = {"jetpack", "akismet", "jetpack-boost", "jetpack-videopress", "gutenberg", "jetpack-protect", "jetpack-social",
                         "jetpack-search", "jetpack-backup", "woocommerce", "classic-editor"}
# Jetpack modules a WordPress.com Business plan pays for, which need a Jetpack plan on Pressable.
PLAN_MODULES = {"backup": "Backup", "activity-log": "Activity log (full history)", "videopress": "VideoPress", "search": "Search",
                "scan": "Scan", "wordads": "Ads"}


def owner_for(finding):
    if finding.get("owner"):
        return finding["owner"]
    for prefix, who in OWNERS:
        if finding["id"].startswith(prefix):
            return who
    return "TAM" if finding["severity"] == "decision" else "Developer"


def check(fn):
    CHECKS.append(fn)
    return fn


def F(id, area, severity, title, detail="", action="", steps=None, owner=None):
    return dict(id=id, area=area, severity=severity, title=title, detail=detail, action=action, steps=steps or [], owner=owner)


def g(d, *path, default=None):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return default
        d = d[p]
    return default if d is None else d


@check
def platform(m):
    site = m["site"]
    out = []
    if g(site, "core", "multisite"):
        out.append(F("platform.multisite", "Platform", "blocker", "The site is a multisite network",
                     "Reprint can move one site out of a network; nothing here handles a whole network.",
                     "Plan this migration by hand."))
    if not g(site, "core", "is_atomic"):
        out.append(F("platform.not-atomic", "Platform", "blocker", "The source is not a WordPress.com Atomic site",
                     "`IS_ATOMIC` is not defined. This process assumes an Atomic source (Jetpack's Reprint exporter, the layout under /srv/htdocs).",
                     "Check the site; a Simple site needs a different route (an export, or making it Atomic first)."))
    left = sorted({p["slug"] for p in site["plugins"] if p["slug"] in WPCOM_PLATFORM} |
                  {d for d in g(site, "mu_plugins", "dirs", default=[]) if d in WPCOM_PLATFORM})
    if left:
        out.append(F("platform.left-behind", "Platform", "auto", "WordPress.com platform code stays behind",
                     "On the source: %s. These run only on WordPress.com; the pull leaves them out." % ", ".join("`%s`" % s for s in left),
                     "Nothing to do. `compare_sites.py` flags any that reach Pressable."))
    managed = sorted(p["slug"] for p in site["plugins"] if p["slug"] in WPCOM_MANAGED_PLUGINS and p["active"])
    if managed:
        pre = [p["slug"] + " " + p["version"] for p in site["plugins"] if p["slug"] in WPCOM_MANAGED_PLUGINS and p["active"]
               and any(x in p["version"] for x in ("-a", "-alpha", "-beta", "-rc"))]
        out.append(F("platform.managed-plugins", "Plugins", "auto", "Plugins WordPress.com manages need a normal install on Pressable",
                     "Active: %s. Atomic serves these from a shared platform copy.%s" % (
                         ", ".join("`%s`" % s for s in managed),
                         (" Pre-release builds on the source: %s; install the current stable release instead." % ", ".join(pre)) if pre else ""),
                     "After the first pull, `compare_sites.py` lists what is missing; install those from WordPress.org (`rehearse.plugins`).",
                     steps=["rehearse.plugins"]))
    inactive = sorted(p["slug"] for p in site["plugins"] if not p["active"] and p["slug"] not in WPCOM_PLATFORM | WPCOM_MANAGED_PLUGINS)
    if inactive:
        out.append(F("platform.inactive", "Plugins", "info", "Inactive plugins come across too",
                     "Inactive: %s." % ", ".join("`%s`" % s for s in inactive),
                     "Leave them, or agree with the partner to delete them after cutover."))
    php = g(site, "core", "php_version", default="")
    out.append(F("platform.php", "Platform", "auto", "Match the PHP version on Pressable",
                 "The source runs PHP %s." % php, "Set the same minor version on the Pressable site before the first pull (`prep.php`).",
                 steps=["prep.php"]))
    return out


@check
def jetpack(m):
    site, wpcom = m["site"], m.get("wpcom") or {}
    jp = g(site, "jetpack", default={})
    out = []
    modules = set(jp.get("active_modules") or [])
    subs = wpcom.get("subscribers")
    out.append(F("jetpack.new-blog-id", "Jetpack", "auto", "Jetpack connects afresh on Pressable, with a new blog ID",
                 "The source is blog %s. The pull copies its connection; the quarantine keeps Jetpack offline on the copy until "
                 "cutover, when the copied connection is deleted and Jetpack is connected as a new site." % jp.get("blog_id"),
                 "Steps `prep.quarantine` and `cut.jetpack`.", steps=["prep.quarantine", "cut.jetpack"]))
    if "subscriptions" in modules or subs:
        out.append(F("jetpack.subscribers", "Jetpack", "manual", "Migrate %s subscribers to the new blog ID" % (subs if subs is not None else "the"),
                     "Subscribers belong to blog %s. Subscriptions module %s." % (jp.get("blog_id"), "on" if "subscriptions" in modules else "off"),
                     "After cutover, with the MC Blog Subscription Migration tool (`post.subscribers`).", steps=["post.subscribers"]))
    if "stats" in modules:
        out.append(F("jetpack.stats", "Jetpack", "manual", "Merge stats into the new blog ID",
                     "The Stats module is on.", "After cutover (`post.stats`).", steps=["post.stats"]))
    else:
        out.append(F("jetpack.stats", "Jetpack", "info", "No stats history to merge",
                     "The Stats module is off on the source, so WordPress.com holds no traffic history for it. The audit also has no "
                     "traffic figures for the site.", "Nothing to do. Turn Stats on after cutover if the partner wants it."))
    products = [p for p in (jp.get("product_slugs") or [])]
    if products:
        decided = g(m, "decisions", "jetpack_products")
        out.append(F("jetpack.products", "Jetpack", "manual" if decided else "decision", "Paid Jetpack products are attached to the old blog ID",
                     "Products: %s.%s" % (", ".join("`%s`" % p for p in products), (" Decided: %s." % decided) if decided else ""),
                     "Decide whether each moves to the new connection (a licence key on Pressable) or lapses with the old site. "
                     "Record it with `state.py decide jetpack_products \"<what happens>\"`.",
                     steps=["post.jetpack-products"]))
    gaps = sorted(label for mod, label in PLAN_MODULES.items() if mod in modules)
    if gaps:
        out.append(F("jetpack.plan", "Jetpack", "info", "Features the WordPress.com plan paid for",
                     "Modules on: %s. On Pressable these need a Jetpack plan or are not used." % ", ".join(gaps),
                     "Check what the Pressable plan includes; note any feature the partner loses."))
    return out


@check
def videopress(m):
    vp = g(m, "site", "videopress", default={})
    if vp.get("in_use"):
        return [F("videopress.in-use", "VideoPress", "manual", "VideoPress videos are tied to the old blog ID",
                  "%s attachments with a VideoPress GUID; %s posts embed VideoPress." % (vp.get("attachments_with_guid"), vp.get("posts_with_block")),
                  "Ask #videopress how to move them before cutover; keep the old site until every video plays on the new one.",
                  steps=["post.videopress"])]
    if vp.get("module_active") or vp.get("plugin_active"):
        return [F("videopress.unused", "VideoPress", "info", "VideoPress is switched on but holds no videos",
                  "Module %s, plugin %s, no videos found." % ("on" if vp.get("module_active") else "off", "active" if vp.get("plugin_active") else "inactive"),
                  "Leave the VideoPress plugin off on Pressable unless the partner uses it.")]
    return []


@check
def woocommerce(m):
    woo = g(m, "site", "woocommerce", default={})
    if not woo.get("active"):
        return []
    return [F("woo.store", "Store", "manual", "The site is a WooCommerce store",
              "Orders and payment accounts make the cutover a hard freeze. WooPayments, if used, is linked to the old blog ID.",
              "Agree a freeze window; ask #woosupport to re-link any WooPayments account to the new blog ID. Never onboard afresh.",
              steps=["window.freeze", "post.woopayments"])]


@check
def writes(m):
    act = m.get("activity") or {}
    site = m["site"]
    woo = g(site, "woocommerce", "active")
    forms = act.get("form_entries_90d")
    comments = act.get("comments_90d", g(site, "content", "comments_30d"))
    last_edit = act.get("last_content_edit")
    busy = woo or (forms or 0) > 30 or (comments or 0) > 30 or act.get("edited_last_14d")
    if not act:
        return [F("writes.unknown", "Cutover", "manual", "Activity not checked: assume the live site needs a freeze",
                  "There is no `activity.json`, so the audit cannot tell how often the site is written to.",
                  "Read the activity log (see the audit skill) and rebuild, or freeze the site in the window.", steps=["window.freeze"])]
    detail = "Last content edit %s by %s; %s form entries and %s comments in 90 days; partner logins: %s." % (
        last_edit or "unknown", act.get("last_content_editor") or "unknown", forms, comments, act.get("last_partner_login") or "none seen")
    if busy:
        return [F("writes.freeze", "Cutover", "manual", "The live site is written to often: freeze it for the final pull",
                  detail, "Install the freeze mu-plugin on the source at the start of the window (`window.freeze`).", steps=["window.freeze"])]
    return [F("writes.quiet", "Cutover", "info", "The live site is rarely written to: no lockdown needed",
              detail + " A request to the partner not to edit during the window is enough.",
              "After cutover, the straggler check (`post.stragglers`) catches anything written to the old site in the window.")]


@check
def atlantis(m):
    t51 = g(m, "site", "team51", default={})
    if not t51.get("atlantis_present"):
        return [F("access.atlantis", "Team 51", "info", "Atlantis is not on the source",
                  "", "`pressable:create-site` installs it on the new site; check it is active after the pull.")]
    # The key encrypts Atlantis Messages content and nothing else, so with no messages there is nothing to carry.
    if not t51.get("atlantis_messages"):
        return [F("access.atlantis-key", "Team 51", "info", "The Atlantis key does not need to move",
                  "The source has no Atlantis messages, the only thing the key encrypts (fingerprint %s). The new site keeps the key "
                  "Atlantis wrote when it was installed." % t51.get("atlantis_key"),
                  "Check the count is still 0 at the final pull; if a message appears, carry the key (`prep.atlantis-key`).")]
    return [F("access.atlantis-key", "Team 51", "auto", "Carry the Atlantis encryption key to Pressable",
              "Key fingerprint %s; %s stored messages. Site creation writes a new key on Pressable." % (t51.get("atlantis_key"), t51.get("atlantis_messages")),
              "Step `prep.atlantis-key`, before the first pull.", steps=["prep.atlantis-key"])]


@check
def config_and_files(m):
    site = m["site"]
    out = []
    consts = sorted(c["name"] for c in g(site, "constants", "in_wp_config", default=[])
                    if c["name"] not in ("WP_DEBUG", "A8CSP_ATLANTIS_ENCRYPTION_KEY", "WP_CACHE"))
    if consts:
        out.append(F("access.constants", "Configuration", "manual", "wp-config constants to recreate on Pressable",
                     "Defined on the source: %s. The pull does not bring wp-config." % ", ".join("`%s`" % c for c in consts),
                     "Set each on Pressable with `wp config set` without printing secret values (`prep.constants`).", steps=["prep.constants"]))
    web = m.get("webroot") or {}
    outside = [e.get("name") for e in web.get("entries") or []]
    in_root = g(web, "attachments", "in_web_root", default=0)
    if outside or in_root or g(web, "redirects", "into_web_root"):
        out.append(F("access.web-root", "Files", "manual", "Files served from outside wp-content",
                     "Web root entries: %s; attachments there: %s." % (", ".join(outside) or "none", in_root),
                     "The pull only takes wp-content. Copy these by hand and check them on the copy.", steps=["rehearse.web-root"]))
    extras = [e for e in g(site, "content_extras", default=[]) if e not in ("boost-cache", "cache", "upgrade", "jetpack-waf", "fonts", "languages")]
    if extras:
        out.append(F("access.content-extras", "Files", "info", "Extra folders in wp-content", ", ".join(extras),
                     "The pull brings them; check they belong on the new site."))
    db = g(site, "database", default={})
    up = g(site, "uploads", default={})
    out.append(F("access.size", "Files", "info", "Size of the copy",
                 "Database %s MB in %s tables; %s attachments." % (db.get("total_mb"), db.get("tables"), up.get("attachments")),
                 "Small sites pull in minutes; plan the window from the rehearsal's timings."))
    return out


@check
def dns(m):
    out = []
    for z in m.get("dns") or []:
        apex = z.get("apex")
        reg, host = z.get("registrar_class"), z.get("dns_host")
        mail = z.get("mail_provider_hint") or "none found"
        if reg == "automattic" and host == "wpcom":
            out.append(F("dns.wpcom.%s" % apex, "DNS", "manual", "%s: registered and hosted at WordPress.com; only the site records change" % apex,
                         "Mail: %s. The apex `A` records are pointed at Pressable inside the WordPress.com zone, with an "
                         "`atomic-domain` TXT for Pressable; `www` too if it has its own record. Mail and other records stay." % mail,
                         "Steps `cut.add-domain`, `cut.records`. Find the WordPress.com account that holds the registration first.",
                         steps=["prep.domain-account", "cut.add-domain", "cut.records"]))
        elif host == "wpcom":
            out.append(F("dns.wpcom-dns.%s" % apex, "DNS", "manual", "%s: DNS at WordPress.com, registered elsewhere" % apex,
                         "Mail: %s." % mail, "Records change inside the WordPress.com zone (`cut.records`).",
                         steps=["prep.domain-account", "cut.add-domain", "cut.records"]))
        else:
            out.append(F("dns.access.%s" % apex, "DNS", "decision", "%s: DNS is hosted elsewhere; confirm who can change it" % apex,
                         "DNS host: %s; registrar: %s; mail: %s." % (host, z.get("registrar"), mail),
                         "Confirm a person with the DNS login is available in the window.", steps=["cut.records"]))
        others = z.get("points_at_other_wpcloud_site") or []
        if others:
            out.append(F("dns.other-sites.%s" % apex, "DNS", "info", "Other hostnames in the zone point at other sites",
                         ", ".join(others), "Leave them alone at cutover, including their `atomic-domain-…` TXT records."))
        verification = [v.get("name") for v in z.get("verification_txt") or []]
        out.append(F("dns.verification.%s" % apex, "DNS", "manual", "Pressable will ask for an `atomic-domain` TXT record for %s" % apex,
                     "Pressable and WordPress.com are both WP Cloud, which proves ownership of a domain with an `atomic-domain-…` TXT "
                     "record. Names in the zone that already carry one: %s." % (", ".join(verification) or "none seen"),
                     "Add the value Pressable shows for the apex and `www` in the zone before setting the domain primary (`cut.add-domain`).",
                     steps=["cut.add-domain"]))
        if z.get("wildcard"):
            out.append(F("dns.wildcard.%s" % apex, "DNS", "info", "The zone has a wildcard record",
                         "Wildcard: %s." % z["wildcard"], "Check it after the change: a wildcard pointing at the apex follows the apex to Pressable."))
        out.append(F("dns.records.%s" % apex, "DNS", "info", "The DNS audit's record list is a floor",
                     "DNS cannot list a zone; the audit only sees names it asked about.",
                     "Export the zone from the WordPress.com dashboard before the window, as a record of what was there (`prep.zone-export`).",
                     steps=["prep.zone-export"]))
    return out


@check
def deploys(m):
    dep = m.get("deploy") or {}
    out = []
    if not dep:
        return [F("access.deploy-unknown", "Deploys", "manual", "Deploy state not checked",
                  "There is no `deploy.json`.", "Find the repo and how it deploys before the window.")]
    if not dep.get("repo"):
        return [F("access.no-repo", "Deploys", "decision", "No repository found for this site",
                  dep.get("evidence", ""), "Decide whether the Pressable site deploys from a repo; without one, skip the deploy steps.")]
    if dep.get("wpcom_deployments"):
        out.append(F("access.wpcom-deploys", "Deploys", "auto", "Disconnect WordPress.com GitHub Deployments before the allowlist goes in",
                     "Connected: %s." % dep.get("wpcom_deployments"),
                     "WordPress.com deployments ignore the `!` lines of the Pressable allowlist and copy nothing. Step `deploy.wpcom-disconnect`.",
                     steps=["deploy.wpcom-disconnect"]))
    if dep.get("layout_ok") is False:
        out.append(F("access.repo-layout", "Deploys", "blocker", "The repo is not laid out as wp-content",
                     dep.get("evidence", ""), "`pressable:prepare-site-repository` only handles a repo whose root is wp-content. Plan the deploy by hand."))
    if dep.get("drift"):
        out.append(F("access.deploy-drift", "Deploys", "decision", "The live site's code differs from the repo",
                     dep["drift"], "Reconcile the repo before connecting Pressable's integration, or the first deploy overwrites the live code."))
    out.append(F("access.allowlist", "Deploys", "auto", "Pressable deploy allowlist goes into .deployignore just before DNS",
                 "Allowlist block present on `%s`: %s." % (dep.get("branch", "trunk"), "yes" if dep.get("allowlist_present") else "no"),
                 "`pressable:prepare-site-repository` writes it from the Pressable site's files after the final pull; "
                 "`pressable:connect-site-repository` then connects the integration (`deploy.*`).",
                 steps=["deploy.prepare", "deploy.connect"]))
    return out


@check
def estate(m):
    out = []
    # The audit sets a severity and action where it could answer the question itself (a staging copy, a dead blog).
    for s in g(m, "wpcom", "existing_sites", default=[]):
        out.append(F("estate.%s" % s.get("blog_id"), "Related sites", s.get("severity", "decision"),
                     "Another WordPress.com site uses this name: %s" % s.get("url"), s.get("note", ""),
                     s.get("action", "Confirm it is not live, or that the DNS change does not affect it."), steps=s.get("steps")))
    for s in g(m, "pressable_related", default=[]):
        out.append(F("estate.pressable.%s" % s.get("id"), "Related sites", "info", "Related Pressable site: %s" % s.get("url"),
                     s.get("note", ""), "Nothing to do; noted so the right site is targeted."))
    collaborator = g(m, "decisions", "partner_collaborator")
    out.append(F("estate.collaborator", "Related sites", "manual" if collaborator else "decision",
                 "Add the partner as a Pressable collaborator" + (": %s" % collaborator if collaborator else ""),
                 "", "Record the email with `state.py decide partner_collaborator <email>`; added in `prep.collaborator`.",
                 steps=["prep.collaborator"]))
    return out


@check
def billing(m):
    stickers = g(m, "wpcom", "stickers", default=[])
    plans = [s for s in stickers if s.endswith("-plan") or s.endswith("-bundle")]
    return [F("billing.wpcom-plan", "Billing", "manual", "Cancel the WordPress.com plan after decommission",
              "Plan stickers: %s." % (", ".join(plans) or "none seen"),
              "After the old site is no longer needed, cancel the plan; keep the domain registration (`decom.plan`).",
              steps=["decom.plan"])]


@check
def context(m):
    notes = g(m, "context", "notes", default=[])
    out = []
    for i, n in enumerate(notes[:15]):
        # A note that asks a question names the decision that answers it; once recorded, it is no longer a question.
        answer = g(m, "decisions", n.get("decision_key") or "")
        severity = "info" if answer and n.get("severity") in ("decision", "blocker") else n.get("severity", "info")
        detail = "%s %s" % (n.get("source", ""), n.get("url", "")) + (" Decided: %s." % answer if answer else "")
        out.append(F("context.%d" % i, "Context from P2, Slack and Linear", severity, n.get("note", ""), detail, n.get("action", ""), owner=n.get("owner")))
    return out


def run_all(manifest):
    findings = []
    for fn in CHECKS:
        try:
            findings.extend(fn(manifest) or [])
        except Exception as err:  # A broken check must not hide the others.
            findings.append(F("check-error." + fn.__name__, "Audit", "manual", "Check `%s` failed to run" % fn.__name__, repr(err),
                              "Fix the check or do this part by hand."))
    for f in findings:
        f["owner"] = owner_for(f)
    findings.sort(key=lambda f: (SEVERITY_ORDER.index(f["severity"]), f["area"], f["id"]))
    return findings
