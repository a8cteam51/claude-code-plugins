"""The audit's check catalogue.

Each check is a function that takes the merged manifest and returns a list of
findings. A finding is a dict:

    id        stable identifier, e.g. "videopress.in-use"
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

# Rules that are already settled for every migration. The audit applies them
# and says so; it does not ask anyone to decide them again. Change them here,
# not per site.
STANDING_RULES = [
    "Team 51 owns the new site, repo and domain until the partner accepts it. Ownership moves at handover, not during migration.",
    "A development or staging site on Pressable is not migrated. A WordPress.com staging site is made from the new production site after cutover; the old one is deleted at decommission.",
    "WordPress.com GitHub Deployments replace DeployHQ, but only where the existing deploy is connected and current.",
    "DNS zones hosted at Pressable move to WordPress.com DNS.",
    "Atlantis is removed from the new site. Other Team 51 access and tooling stays until handover.",
    "Jetpack features covered by a WordPress.com Business or Commerce plan need no decision. Only real gaps are raised.",
]

# Who can answer or do each finding, by ID prefix. First match wins.
OWNERS = [
    ("videopress.", "Developer, with the VideoPress team"),
    ("jetpack.features", "Management"),
    ("jetpack.payments", "Developer, with the Jetpack team"),
    ("jetpack.blog-id", "Developer (MC tools, after cutover)"),
    ("dns.access.", "TAM, with the partner"),
    ("dns.account.", "TAM"),
    ("dns.other-sites.", "TAM"),
    ("dns.", "Developer"),
    ("woo.woopayments", "TAM, with WooPayments support"),
    ("woo.regulated-goods", "TAM, with the Terms of Service team"),
    ("woo.gateway-domain-bound", "Developer, with the partner at cutover"),
    ("woo.gateways", "Developer, with the partner"),
    ("woo.api-keys", "TAM asks the partner; developer checks"),
    ("woo.", "Developer"),
    ("estate.existing-wpcom", "TAM"),
    ("estate.related", "TAM"),
    ("estate.no-partner-user", "TAM"),
    ("writes.", "TAM agrees the window with the partner"),
    ("reprint.", "Developer"),
    ("context.", "TAM"),
]


def owner_for(finding):
    if finding.get("owner"):
        return finding["owner"]
    for prefix, who in OWNERS:
        if finding["id"].startswith(prefix):
            return who
    return "TAM" if finding["severity"] == "decision" else "Developer"

SEVERITY_ORDER = ["blocker", "decision", "manual", "auto", "info"]


def check(fn):
    CHECKS.append(fn)
    return fn


def F(id, area, severity, title, detail="", action="", steps=None, owner=None):
    return {"id": id, "area": area, "severity": severity, "title": title, "detail": detail, "action": action,
            "steps": steps or [], "owner": owner}


def g(d, *path, default=None):
    for key in path:
        if not isinstance(d, dict) or key not in d or d[key] is None:
            return default
        d = d[key]
    return d


def active_slugs(m):
    return {p["slug"] for p in g(m, "site", "plugins", default=[]) if p.get("active")}


def all_slugs(m):
    return {p["slug"] for p in g(m, "site", "plugins", default=[])}


# Plugins that are unnecessary or commonly disallowed on WordPress.com. This is
# a starting list from the first audits, not the official one: always confirm
# against https://wordpress.com/support/incompatible-plugins/.
LIKELY_INCOMPATIBLE = {
    "caching (the platform handles caching)": ["breeze", "nginx-helper", "w3-total-cache", "wp-super-cache", "wp-fastest-cache",
                                              "litespeed-cache", "sg-cachepress", "hummingbird-performance", "cache-enabler",
                                              "pressable-cache-management", "wp-rocket"],
    "backup or migration (the platform handles backups)": ["migrate-guru", "wpcom-migration", "all-in-one-wp-migration", "duplicator",
                                                           "duplicator-pro", "updraftplus", "backwpup", "blogvault-real-time-backup",
                                                           "wpvivid-backuprestore", "backupbuddy", "reprint-exporter-wp"],
    "security or SSL (overlaps the platform)": ["malcare-security", "really-simple-ssl", "sf-move-login", "wps-hide-login",
                                                 "better-wp-security", "all-in-one-wp-security-and-firewall", "sucuri-scanner"],
    "previous-host tooling": ["dreamhost-panel-login", "pressable-onepress-login", "wpengine-common", "kinsta-mu-plugins",
                               "sg-security", "bluehost-wordpress-plugin", "mojo-marketplace-wp-plugin", "gd-system-plugin"],
    "file or database access": ["wp-file-manager", "file-manager-advanced", "wp-phpmyadmin-extension", "adminer"],
}

# What a WordPress.com Business or Commerce plan includes, against what a
# Pressable site gets (a Jetpack Security licence) or may have been comped
# (often Jetpack Complete). Source: the Field Guide matrix "Paid Jetpack and
# Other Bets product features on WP.com/Woo.com Sites" and Pressable's docs, as
# supplied on 2026-10-10. Recheck before relying on it; plans change.
#   key: (label, status on the target, note)
#   status: included | native | add-on | not-included
JETPACK_ON_WPCOM = {
    "backup": ("Backups", "included", "Pressable's licence is a 10 GB backup plan; WordPress.com uses its own backups. Check retention suits the partner."),
    "akismet": ("Akismet anti-spam", "included", ""),
    "ai": ("AI Assistant", "included", ""),
    "stats": ("Stats", "included", "History stays on the old blog ID until stats are merged."),
    "videopress": ("VideoPress", "included", "50 GB on Business and Commerce. Existing videos still do not follow the site; see the VideoPress finding."),
    "search": ("Jetpack Search", "included", "Business and above. The index is rebuilt for the new blog ID."),
    "scan": ("Scan, brute-force protection, downtime monitor", "native", "WordPress.com has its own equivalents. Jetpack Protect is disabled there."),
    "boost": ("Boost (paid tier: automatic critical CSS, image analysis)", "add-on", "Not bundled. If the paid tier is in use it must be bought or comped for the new site."),
    "social": ("Social (paid tier: re-sharing, image generator, video sharing)", "add-on", "Not bundled, and re-sharing is a paid feature on WordPress.com. Connections must be made again on the new blog ID."),
    "crm": ("Jetpack CRM", "not-included", "Not included on either host. Its data is in the site's database and travels with it; any paid extensions need their licence checked."),
}

KNOWN_REST = ("akismet/", "jetpack", "my-jetpack/", "wpcom/", "videopress/", "wc/", "wc-", "wccom-site/", "a8csp-atlantis/",
              "create-block-theme/", "yoast/", "wp-rocket/", "redirection/", "wc-admin", "wc-analytics", "wc-telemetry",
              "regenerate-thumbnails/", "mailpoet/", "wp-mail-smtp/", "elementor/", "code-snippets/")

CONSTANT_NOTES = {
    "WPCOMSP_BILMUR": "Team 51 Bilmur performance tracking. Decide whether it continues after the move.",
    "WPC_BOT_PROTECTION_ENABLED": "WP Cloud bot protection, set by `team51 pressable:enable-bot-protection`. Confirm the WordPress.com equivalent.",
    "A8CSP_ATLANTIS": "Belongs to Atlantis. Drop it with the plugin.",
    "SAFETY_NET": "SafetyNet setting. SafetyNet must not run on a migration target.",
    "WP_ENVIRONMENT_TYPE": "Must be `production` on the target before cutover.",
    "WP_DEBUG": "Development flag. Usually not carried over.",
    "DISABLE_WP_CRON": "Cron trigger setting. The target host manages this.",
    "WP_MEMORY_LIMIT": "Memory setting. Check the target's limit before carrying over.",
    "WP_CACHE": "Host cache flag. Not carried over.",
    "JETPACK_": "Jetpack setting. Check whether it still applies on WordPress.com.",
}


@check
def not_supported(m):
    out = []
    core = g(m, "site", "core", default={})
    if core.get("multisite"):
        out.append(F("core.multisite", "Site", "blocker", "Site is a multisite network",
                     "This process and the Migration Assistant flow have only been designed for single sites.",
                     "Stop. Raise with the Reprint team before planning this site."))
    if core and not core.get("is_pressable"):
        out.append(F("core.not-pressable", "Site", "decision", "Source does not report itself as Pressable",
                     "IS_PRESSABLE is not set. is_atomic=%s." % core.get("is_atomic"),
                     "Confirm the host. Parts of this process assume a Pressable source."))
    if core.get("environment_type") and core["environment_type"] != "production":
        out.append(F("core.environment", "Site", "manual", "Source environment type is `%s`" % core["environment_type"],
                     "The value travels in wp-config, not the database, but anything keyed on it behaves differently.",
                     "Confirm the target's WP_ENVIRONMENT_TYPE is `production` before cutover."))
    return out


@check
def videopress(m):
    vp = g(m, "site", "videopress", default={})
    if not vp:
        return []
    if vp.get("in_use"):
        n = vp.get("attachments_with_guid") or 0
        detail = ("%s videos carry a VideoPress ID; %s posts use the VideoPress block, %s a VideoPress shortcode, "
                  "%s an embed URL, %s a videos.files.wordpress.com URL." % (
                      n, vp.get("posts_with_block"), vp.get("posts_with_shortcode"),
                      vp.get("posts_with_embed_url"), vp.get("posts_with_videos_files_url")))
        theme_files = vp.get("theme_files") or []
        if theme_files:
            detail += " The active theme references VideoPress in: %s. Those are in code, so re-pointing means a code change." % ", ".join("`%s`" % t for t in theme_files[:10])
        common = ("Videos are stored against the source blog ID. On the new blog ID they are orphaned and the player reports the "
                  "video as private. There is no bulk transfer (tracked in VIDP-93). ")
        if n and n <= 25:
            return [F("videopress.in-use", "VideoPress", "decision", "Site has VideoPress content: %s videos" % n, detail,
                      common + "With this few, either move them one at a time with https://mc.a8c.com/tools/video-move/ or "
                      "re-upload them on the new site and re-point each block. Ask in #videopress with both blog IDs first. "
                      "Do not delete or disconnect the old site until every video plays on the new one.",
                      steps=["prep.videopress", "post.videopress"])]
        return [F("videopress.in-use", "VideoPress", "blocker", "Site has VideoPress content: %s videos" % (n or "an unknown number of"), detail,
                  common + "At this size the working route is: keep the videos serving from the old blog ID (a complimentary "
                  "VideoPress plan on it), bulk-download them (MC File Tools → List Blog Videos → Download All Videos), re-upload "
                  "on the new site and re-point every block and embed. Agree that plan with the VideoPress team, with both blog "
                  "IDs, before scheduling. The old site cannot be deleted until this is finished.",
                  steps=["prep.videopress", "post.videopress"])]
    if vp.get("module_active"):
        return [F("videopress.module-only", "VideoPress", "info", "VideoPress module is on but no VideoPress content was found",
                  "No attachments with a VideoPress ID and no VideoPress blocks, shortcodes or embeds in content.",
                  "No action. Re-run the audit shortly before cutover in case video is added.")]
    return []


@check
def jetpack(m):
    out = []
    jp = g(m, "site", "jetpack", default={})
    if not jp:
        return out
    blog_id = jp.get("blog_id")
    wp = g(m, "wpcom", default={})
    if blog_id:
        subs = wp.get("subscribers")
        views = wp.get("views_30d")
        out.append(F("jetpack.blog-id", "Jetpack and blog ID", "manual", "Blog ID will change (source is %s)" % blog_id,
                     "Stats, subscribers and other WordPress.com-side data stay on the source blog ID. Subscribers: %s. Views, last 30 days: %s." % (
                         subs if subs is not None else "not checked", views if views is not None else "not checked"),
                     "After cutover, merge stats from %s into the new blog ID, and migrate subscribers%s. The subscriber figure is "
                     "WordPress.com's and can include social followers. Skip stats only if the partner wants a fresh start." % (
                         blog_id, " (none recorded, so that step is left out)" if subs == 0 else ""),
                     steps=["post.stats"] + ([] if subs == 0 else ["post.subscribers"])))
    else:
        out.append(F("jetpack.not-connected", "Jetpack and blog ID", "info", "No Jetpack blog ID found on the source",
                     "Jetpack is not connected, so there are no stats or subscribers to move.", ""))
    modules = set(jp.get("active_modules") or [])
    slugs = all_slugs(m)
    in_use = {
        "backup": "backup" in modules or "vaultpress" in modules,
        "akismet": "akismet" in active_slugs(m),
        "ai": "ai" in modules,
        "stats": "stats" in modules,
        "videopress": bool(g(m, "site", "videopress", "in_use")),
        "search": "search" in modules or bool(jp.get("search_plugin_active")),
        "scan": bool(modules & {"protect", "monitor", "scan", "waf", "account-protection"}),
        "boost": bool(jp.get("boost_active")),
        "social": "publicize" in modules or bool(jp.get("social_plugin_active")) or bool(jp.get("social_connections")),
        "crm": bool(jp.get("crm_active")) or "zero-bs-crm" in active_slugs(m),
    }
    plan_slug = jp.get("plan_slug") or ""
    products = jp.get("product_slugs") or []
    all_plan = " ".join([plan_slug] + products).lower()
    complete = "complete" in all_plan
    rows, gaps = [], []
    for key, (label, status, note) in JETPACK_ON_WPCOM.items():
        if not in_use[key]:
            continue
        shown = {"included": "Included", "native": "WordPress.com equivalent", "add-on": "**Add-on, not included**",
                 "not-included": "**Not included**"}[status]
        rows.append("| %s | %s | %s |" % (label, shown, note))
        if status == "add-on":  # "not-included" means not included on Pressable either: no regression.
            gaps.append(label.split(" (")[0])
    if rows:
        plan_line = "Plan the site reports: `%s`%s." % (plan_slug or "unknown", (" plus " + ", ".join("`%s`" % p for p in products)) if products else "")
        if complete:
            plan_line += " Jetpack Complete is usually comped on the Team 51 account against this blog ID and will not follow the site."
        table = "| Feature in use on the source | On a WordPress.com Business or Commerce plan | Note |\n|---|---|---|\n" + "\n".join(rows)
        if gaps:
            out.append(F("jetpack.features", "Jetpack and blog ID", "decision",
                         "Jetpack features in use that the WordPress.com plan does not include: %s" % ", ".join(gaps),
                         plan_line + "\n\n" + table,
                         "For Boost and Social, find out whether the paid tier is actually used (the audit can see the plugin or "
                         "module, not the tier). Anything the partner relies on needs buying or comping for the new site: a "
                         "management decision, not a per-site one.", steps=["prep.plan"]))
        else:
            out.append(F("jetpack.features", "Jetpack and blog ID", "info",
                         "Every Jetpack feature in use is covered by a WordPress.com Business or Commerce plan",
                         plan_line + "\n\n" + table,
                         "No gap. Confirm the target is on Business or above."))
    plan = wp.get("source_plan") or wp.get("source_products")
    if plan:
        out.append(F("jetpack.source-plan", "Jetpack and blog ID", "info", "Plans and products on the source blog ID", str(plan),
                     "These do not move with the site. Confirm the target has equivalents."))
    mem = (m.get("site") or {}).get("jetpack_payments") or {}
    if mem.get("plans") or mem.get("posts_with_blocks"):
        out.append(F("jetpack.payments", "Jetpack and blog ID", "blocker", "Site takes payments through Jetpack (donations, paid content or payment buttons)",
                     "%s payment plans; %s posts or templates use a Jetpack payments, donations or premium-content block." % (
                         mem.get("plans"), mem.get("posts_with_blocks")),
                     "These run through WordPress.com against the source blog ID: the Stripe connection, the plans and any paying "
                     "subscribers. There is no known procedure here for moving them. Find one with the Jetpack memberships team "
                     "before migrating."))
    if jp.get("reprint_exporter"):
        out.append(F("reprint.jetpack-exporter", "Reprint", "info", "Jetpack's built-in Reprint exporter is available on this site",
                     "Jetpack %s reports the exporter as available, so the source may not need the Reprint plugin installed." % jp.get("version"),
                     "Use it if the Migration Assistant accepts it; otherwise install the Reprint plugin on the source."))
    else:
        out.append(F("reprint.plugin-needed", "Reprint", "manual", "Source needs the Reprint plugin",
                     "Jetpack's built-in exporter is not available here (needs Jetpack 16.2+ on Pressable).",
                     "Install the Reprint exporter plugin on the source, or update Jetpack first.", steps=["sync.source-exporter"]))
    return out


@check
def woocommerce(m):
    out = []
    woo = g(m, "site", "woocommerce", default={})
    if not woo.get("active"):
        return out
    out.append(F("woo.store", "WooCommerce", "info", "WooCommerce store: %s orders in the last 30 days, %s in the last 7" % (
        woo.get("orders_30d"), woo.get("orders_7d")),
        "Total orders %s. Last order (GMT) %s. HPOS %s." % (woo.get("orders_total"), woo.get("last_order_gmt"),
                                                             "on" if woo.get("hpos") else "off"),
        "Plan a write freeze for cutover and keep the copy quarantined until then.", steps=["cut.freeze", "prep.quarantine"]))
    if woo.get("regulated_product_terms"):
        ids = " ".join(gw["id"] for gw in (woo.get("gateways_enabled") or []))
        out.append(F("woo.regulated-goods", "WooCommerce", "decision",
                     "%s published products look like regulated goods (CBD, hemp, vape, tobacco or similar, by name)" % woo["regulated_product_terms"],
                     "Enabled gateways: %s." % (ids or "none"),
                     "Check the store against the WordPress.com Store Guidelines before planning the move. CBD is allowed on "
                     "WordPress.com and Pressable alike only with WooCommerce and an approved processor (Square in the US, Viva in "
                     "parts of the EU), never WooPayments; most other controlled goods are not allowed at all. Confirm with the "
                     "Terms of Service team if in doubt: https://wordpress.com/support/store-guidelines/"))
    hours = woo.get("orders_by_utc_hour_30d") or []
    if hours:
        by_hour = {int(h["h"]): int(h["n"]) for h in hours}
        best, best_sum = None, None
        for start in range(24):
            total = sum(by_hour.get((start + i) % 24, 0) for i in range(3))
            if best_sum is None or total < best_sum:
                best, best_sum = start, total
        out.append(F("woo.quiet-window", "WooCommerce", "info",
                     "Quietest 3-hour window in the last 30 days starts %02d:00 UTC" % best,
                     "%s orders were placed in that window across 30 days." % best_sum,
                     "Use this as the starting point for the cutover window, then agree it with the partner."))
    gateways = woo.get("gateways_enabled") or []
    bound = [gw for gw in gateways if any(k in gw["id"] for k in ("square", "ppcp", "paypal", "stripe", "amazon", "klarna", "afterpay"))]
    if bound:
        out.append(F("woo.gateway-domain-bound", "WooCommerce", "manual",
                     "Payment gateways that connect to an account by site address: %s" % ", ".join(gw["title"] for gw in bound),
                     "These authorise against the site's URL. On an earlier Team 51 migration, Square would not connect to a site on "
                     "a wpcomstaging.com address at all, and the move to WordPress.com was abandoned for Pressable.",
                     "Do not expect to prove these gateways on the temporary address. Find out before scheduling whether each "
                     "provider accepts the temporary domain; if not, the first real test is after the domain is attached, so have "
                     "the partner (or whoever can log in to the provider) available at cutover and agree a rollback point.",
                     steps=["post.gateways"]))
    if gateways:
        out.append(F("woo.gateways", "WooCommerce", "manual", "%d payment gateways enabled" % len(gateways),
                     ", ".join("%s (`%s`)" % (gw["title"], gw["id"]) for gw in gateways),
                     "After cutover, place a real or test order through each one. Check each gateway's own dashboard for webhook "
                     "or callback URLs registered against the domain.", steps=["post.gateways"]))
    test_gateways = [gw for gw in gateways if any(k in (gw["id"] + " " + gw["title"]).lower() for k in ("sandbox", "test", "dummy", "bogus"))]
    if test_gateways:
        out.append(F("woo.test-gateway", "WooCommerce", "manual", "A test or sandbox payment gateway is enabled on the live store",
                     ", ".join("%s (`%s`)" % (gw["title"], gw["id"]) for gw in test_gateways),
                     "Ask the partner whether this is intended. It travels with the database as it is."))
    wcp = woo.get("woopayments") or {}
    wcp_gateway = any(gw["id"].startswith("woocommerce_payments") for gw in gateways)
    if wcp.get("plugin_active"):
        facts = "Connected: %s. Account status `%s`, live=%s, country %s. WooPayments gateways enabled: %s." % (
            wcp.get("connected"), wcp.get("status"), wcp.get("is_live"), wcp.get("country"), "yes" if wcp_gateway else "no")
        if wcp.get("connected") or wcp.get("account_cached"):
            out.append(F("woo.woopayments", "WooCommerce", "manual", "WooPayments account is tied to the source blog ID", facts,
                         "Contact WooPayments support BEFORE scheduling cutover to move the account to the new blog ID. Until it moves, "
                         "payment events go to the old site and the new site cannot take WooPayments payments. Keep another gateway "
                         "live as a fallback if there is one.", steps=["prep.woopayments", "post.woopayments"]))
        else:
            out.append(F("woo.woopayments-unclear", "WooCommerce", "manual", "WooPayments is active but no connected account was detected",
                         facts + " Read over WP-CLI, which can under-report.",
                         "Open Payments → Overview in wp-admin. If an account is connected, treat this as the account-move case and "
                         "contact WooPayments support before scheduling cutover. If not, deactivate the plugin or leave it; there is "
                         "nothing to move.", steps=["prep.woopayments", "post.woopayments"]))
    tokens = wcp.get("saved_tokens") or []
    if tokens:
        out.append(F("woo.saved-tokens", "WooCommerce", "manual", "Customers have saved payment methods",
                     ", ".join("%s: %s" % (t["gateway_id"], t["n"]) for t in tokens),
                     "Tokens travel with the database but only work if the gateway account still recognises them. Confirm with "
                     "each gateway; this matters most for subscriptions."))
    subs = woo.get("subscriptions") or {}
    if subs.get("plugin_active"):
        out.append(F("woo.subscriptions", "WooCommerce", "manual", "WooCommerce Subscriptions is active",
                     "Subscriptions by status: %s." % (subs.get("by_status") or "none"),
                     "Renewals must not run on two copies. Subscriptions switches itself to staging mode when the site URL changes, "
                     "which protects the copy; confirm that on the first sync, and confirm it returns to live mode after cutover.",
                     steps=["verify.subscriptions-staging", "post.subscriptions"]))
    hooks = woo.get("webhooks") or []
    active_hooks = [h for h in hooks if h.get("status") == "active"]
    if hooks:
        out.append(F("woo.webhooks", "WooCommerce", "manual", "%d WooCommerce webhooks (%d active)" % (len(hooks), len(active_hooks)),
                     "; ".join("%s → %s [%s]" % (h["topic"], h["delivery_host"], h["status"]) for h in hooks[:15]),
                     "They travel with the database. The quarantine stops them firing from the copy. After cutover, confirm each "
                     "active one still delivers.", steps=["post.webhooks"]))
    keys = woo.get("api_keys") or []
    if keys:
        out.append(F("woo.api-keys", "WooCommerce", "manual", "%d WooCommerce REST API keys" % len(keys),
                     "; ".join("%s (%s, last used %s)" % (k.get("description") or "no description", k.get("permissions"),
                                                           (k.get("last_access") or "never")[:10]) for k in keys[:15]),
                     "Keys travel with the database, so integrations keep working once DNS points at the new site. Ask the partner "
                     "which integrations are live and check them after cutover.", steps=["post.integrations"]))
    if woo.get("woocommerce_com_connected"):
        out.append(F("woo.woocom", "WooCommerce", "manual", "Site is connected to WooCommerce.com",
                     "Extension updates and subscriptions depend on this connection.",
                     "Check the connection in WooCommerce → Extensions after cutover and reconnect if it dropped."))
    return out


@check
def writes(m):
    out = []
    c = g(m, "site", "content", default={})
    woo = g(m, "site", "woocommerce", default={})
    kinds = []
    if woo.get("active") and (woo.get("orders_30d") or 0) > 0:
        kinds.append("orders (%s in 30 days)" % woo["orders_30d"])
    if (c.get("comments_30d") or 0) > 0:
        kinds.append("comments (%s in 30 days)" % c["comments_30d"])
    if (c.get("users_registered_30d") or 0) > 0:
        kinds.append("user registrations (%s in 30 days)" % c["users_registered_30d"])
    if (c.get("feedback_posts_30d") or 0) > 0:
        kinds.append("form or booking posts (%s in 30 days)" % c["feedback_posts_30d"])
    if (c.get("posts_modified_30d") or 0) > 0:
        kinds.append("content edits (%s posts changed in 30 days)" % c["posts_modified_30d"])
    for row in g(m, "site", "local_data", default=[]):
        if row.get("rows_30d"):
            kinds.append("%s (%s new rows in 30 days)" % (row["key"], row["rows_30d"]))
        elif row.get("rows") and "rows_30d" not in row:
            kinds.append("%s (%s rows, age unknown)" % (row["key"], row["rows"]))
    if kinds:
        strict = any(k.startswith(("orders", "user registrations", "form", "formidable", "gravityforms", "wpforms", "memberpress",
                                   "pmpro", "slicewp", "give")) for k in kinds)
        out.append(F("writes.activity", "Data written by visitors and editors", "manual",
                     "Site receives writes that a freeze must cover" if strict else "Site receives occasional writes",
                     "; ".join(kinds),
                     ("Use a strict freeze: block checkout, forms, registration and comments on the source for the final sync."
                      if strict else "A light freeze is enough: close comments and ask editors not to publish during the window."),
                     steps=["cut.freeze"]))
    else:
        out.append(F("writes.none", "Data written by visitors and editors", "info", "No write activity found in the last 30 days",
                     "No orders, comments, registrations, form entries or content edits.",
                     "A freeze is still part of cutover, but the risk of losing data is low."))
    if c.get("users_can_register"):
        out.append(F("writes.registration-open", "Data written by visitors and editors", "info", "User registration is open", "", ""))
    return out


@check
def config_and_files(m):
    out = []
    consts = g(m, "site", "constants", "in_wp_config", default=[])
    core_names = {"WP_DEBUG", "WP_ENVIRONMENT_TYPE", "WP_CACHE", "DISABLE_WP_CRON"}
    rows = []
    for c in consts:
        name = c["name"]
        note = next((v for k, v in CONSTANT_NOTES.items() if name.startswith(k)), "Site-specific. Find out what uses it before deciding.")
        value = (" = `%s`" % c["value"]) if "value" in c else ""
        rows.append("`%s`%s — %s" % (name, value, note))
    custom = [c for c in consts if c["name"] not in core_names]
    if custom:
        out.append(F("config.constants", "wp-config and platform files", "manual",
                     "%d constants are defined in wp-config.php" % len(consts), "\n".join("- " + r for r in rows),
                     "wp-config.php is not copied. For each constant: carry it over, replace it, or drop it. Values are not in "
                     "this report; read them from the source when needed.", steps=["platform.constants"]))
    redirects, config_copies, others = [], [], []
    for f in g(m, "site", "root_files", default=[]):
        base = f["path"].rsplit("/", 1)[-1]
        low = base.lower()
        if base == "wp-config.php":
            continue
        line = "`%s` (%s bytes, modified %s)" % (base, f["bytes"], f["modified"])
        if "redirect" in low:
            redirects.append(line)
        elif low.startswith("wp-config") or "salt" in low or low.endswith((".bak", ".old", ".orig")):
            config_copies.append(line)
        elif f["bytes"] > 0:
            others.append(line)
    if redirects:
        out.append(F("files.redirects", "wp-config and platform files", "manual", "Platform redirects file outside wp-content",
                     ", ".join(redirects),
                     "Only wp-content is copied. Carry these redirects over (the same file if WordPress.com supports it, otherwise a "
                     "redirect plugin or mu-plugin) and test them after cutover.", steps=["platform.root-files"]))
    if others:
        out.append(F("files.root", "wp-config and platform files", "manual", "%d other files outside wp-content" % len(others),
                     ", ".join(others),
                     "Only wp-content is copied. For each, find out whether anything still uses it and recreate it on the target if so.",
                     steps=["platform.root-files"]))
    if config_copies:
        out.append(F("files.config-copies", "wp-config and platform files", "info", "Old copies of wp-config or salts sit in the site root",
                     ", ".join(config_copies),
                     "They are not copied, which is right. They probably hold old credentials: delete them from the source."))
    host = g(m, "site", "host_files", default=[])
    if host:
        out.append(F("files.host", "wp-config and platform files", "auto", "Pressable host files present in wp-content",
                     ", ".join("`%s`" % h for h in host),
                     "Reprint copies host files by default and leaves cleanup to the target. After the first sync, confirm these are "
                     "gone or replaced by the target's own.", steps=["verify.host-files"]))
    mu = g(m, "site", "mu_plugins", default={})
    custom_mu = [d for d in mu.get("dirs", [])] + [f for f in mu.get("files", []) if f not in ("mu-loader.php",)]
    if custom_mu:
        out.append(F("files.mu-plugins", "wp-config and platform files", "manual", "Custom must-use plugins",
                     ", ".join("`%s`" % x for x in custom_mu),
                     "These are copied. Read each for Pressable-specific code (IS_PRESSABLE checks, cache purges, host APIs) that "
                     "needs changing for WordPress.com.", steps=["platform.custom-code"]))
    extras = [e for e in g(m, "site", "content_extras", default=[]) if e not in ("README.md", ".gitignore", "LICENSE")]
    if extras:
        out.append(F("files.content-extras", "wp-config and platform files", "info", "Non-standard entries in wp-content",
                     ", ".join("`%s`" % e for e in extras), "These are copied. Check nothing depends on an absolute path."))
    code = g(m, "site", "code_in_database", default={})
    if code.get("plugins_active"):
        out.append(F("code.database", "wp-config and platform files", "manual", "Code is stored in the database by a snippet plugin",
                     ", ".join("`%s`" % p for p in code["plugins_active"]),
                     "It travels with the database, so it runs on the target immediately, including on the quarantined copy. "
                     "Read the snippets for host-specific code before the first sync.", steps=["platform.custom-code"]))
    return out


@check
def plugins(m):
    out = []
    plugs = g(m, "site", "plugins", default=[])
    if not plugs:
        return out
    present = {p["slug"]: p for p in plugs}
    hits = []
    for reason, slugs in LIKELY_INCOMPATIBLE.items():
        for slug in slugs:
            if slug in present:
                hits.append("`%s` (%s) — %s" % (slug, "active" if present[slug]["active"] else "inactive", reason))
    if hits:
        out.append(F("plugins.incompatible", "Plugins and themes", "manual", "%d plugins are likely unnecessary or disallowed on WordPress.com" % len(hits),
                     "\n".join("- " + h for h in hits),
                     "Check each against https://wordpress.com/support/incompatible-plugins/. Remove inactive ones on the source "
                     "before the final sync where the partner agrees; deactivate active ones on the target after it.",
                     steps=["prep.plugin-cleanup"]))
    inactive = [p["slug"] for p in plugs if not p["active"]]
    if len(inactive) >= 5:
        out.append(F("plugins.inactive", "Plugins and themes", "info", "%d inactive plugins" % len(inactive),
                     ", ".join("`%s`" % s for s in inactive[:40]), "Optional cleanup before migrating. Less to copy and less to audit."))
    t51 = g(m, "site", "team51", default={})
    if t51.get("atlantis_present"):
        mentions = t51.get("theme_mentions_atlantis") or 0
        out.append(F("team51.atlantis", "Team 51 tooling", "auto" if not mentions else "manual",
                     "Atlantis is installed and must not stay on the new site",
                     "Active: %s. Files in the active theme that mention Atlantis or a colophon: %s." % (t51.get("atlantis_active"), mentions),
                     ("Remove Atlantis on the target after the final sync." if not mentions else
                      "The theme references Atlantis or its colophon. Remove those references first (see recent "
                      "`remove atlantis-dependent colophon` PRs in a8cteam51 for the pattern), or the footer breaks when the "
                      "plugin goes. Then remove Atlantis on the target after the final sync."),
                     steps=["post.atlantis"] + (["platform.colophon"] if mentions else [])))
    if t51.get("safety_net"):
        out.append(F("team51.safety-net", "Team 51 tooling", "blocker", "SafetyNet is present on the source",
                     "SafetyNet deletes or scrubs data on any non-production environment.",
                     "Remove it from the source before syncing, and never install it on a migration target."))
    if t51.get("sso_plugins"):
        out.append(F("team51.sso", "Team 51 tooling", "info", "Team 51 SSO plugin present",
                     ", ".join("`%s`" % s for s in t51["sso_plugins"]), "Leave in place for now. Removed at handover."))
    theme = g(m, "site", "themes", default={})
    premium_themes = {"Divi": "Elegant Themes", "Avada": "ThemeFusion", "astra": None, "flatsome": "UX Themes", "bridge": "Qode",
                      "enfold": "Kriesi", "betheme": "Muffin", "salient": "ThemeNectar", "the7": "Dream-Theme", "kadence": None}
    for name in (theme.get("active"), theme.get("parent")):
        if name in premium_themes and premium_themes[name]:
            out.append(F("themes.premium", "Plugins and themes", "info", "Premium theme `%s` (%s)" % (name, premium_themes[name]),
                         "Version %s." % theme.get("version"),
                         "The licence is the partner's or ours. Confirm who holds it; updates depend on it."))
            break
    unused = [t for t in theme.get("installed", []) if t not in (theme.get("active"), theme.get("parent"))]
    if len(unused) >= 4:
        out.append(F("themes.unused", "Plugins and themes", "info", "%d unused themes installed" % len(unused),
                     ", ".join("`%s`" % t for t in unused), "Optional cleanup before migrating."))
    licensed = [p for p in plugs if p["active"] and (p.get("woo") or (p.get("update_uri") and "wordpress.org" not in p["update_uri"]
                                                                       and "a8cteam51" not in p["update_uri"]))]
    if licensed:
        out.append(F("plugins.licensed", "Plugins and themes", "info", "%d active plugins update from outside WordPress.org" % len(licensed),
                     ", ".join("`%s`" % p["slug"] for p in licensed[:40]),
                     "Licences are usually bound to the domain, which does not change. Check updates still appear after cutover."))
    return out


@check
def integrations(m):
    out = []
    site = g(m, "site", default={})
    custom_ns = [n for n in site.get("rest_namespaces", []) if not n.startswith(KNOWN_REST)]
    if custom_ns:
        out.append(F("integrations.rest", "Integrations", "manual", "%d REST namespaces from plugins or custom code" % len(custom_ns),
                     ", ".join("`%s`" % n for n in custom_ns[:40]),
                     "Identify which are called from outside the site. Smoke-test those on the copy and again after cutover.",
                     steps=["verify.endpoints"]))
    n = g(site, "content", "application_password_users", default=0)
    if n:
        out.append(F("integrations.app-passwords", "Integrations", "manual", "%d users have application passwords" % n,
                     "Something outside the site authenticates as these users.",
                     "They travel with the database. Ask the partner what uses them and check after cutover.", steps=["post.integrations"]))
    smtp = g(site, "mail", "smtp_plugins_active", default=[])
    if smtp:
        out.append(F("integrations.smtp", "Integrations", "manual", "Email is sent through a plugin: %s" % ", ".join(smtp),
                     "Credentials travel with the database.",
                     "Send a test email after cutover. If the provider restricts by sending IP, the new host's IPs need allowing.",
                     steps=["post.email"]))
    else:
        out.append(F("integrations.mail-default", "Integrations", "manual", "Email is sent by the host's default mailer",
                     "No SMTP plugin is active, so mail leaves through Pressable today and will leave through WordPress.com after.",
                     "Send a test email after cutover and check it is not spam-foldered. SPF may need updating if it names the old host.",
                     steps=["post.email"]))
    red = site.get("redirects") or {}
    if red.get("redirection_rows") or red.get("rank_math_rows"):
        out.append(F("integrations.redirects", "Integrations", "info", "Redirects are stored by a plugin",
                     "Redirection: %s enabled rules. Rank Math: %s." % (red.get("redirection_rows"), red.get("rank_math_rows")),
                     "They travel with the database. Spot-check a few after cutover."))
    cron = site.get("cron") or {}
    known_cron = ("wp_", "jetpack", "jp_", "delete_expired", "recovery_mode", "woocommerce_", "wc_", "action_scheduler", "akismet",
                  "wpseo", "do_pings", "publish_future_post", "importer_", "update_network_counts", "wcpay", "a8csp", "rest_")
    custom_cron = [h for h in (cron.get("hooks") or {}) if not h.startswith(known_cron)]
    if custom_cron:
        out.append(F("integrations.cron", "Integrations", "manual", "%d scheduled events from plugins or custom code" % len(custom_cron),
                     ", ".join("`%s`" % h for h in custom_cron[:40]),
                     "They are paused on the quarantined copy. After cutover, confirm they are still scheduled and running.",
                     steps=["post.cron"]))
    sched = site.get("action_scheduler") or {}
    if (sched.get("pending") or 0) > 200:
        out.append(F("integrations.action-scheduler", "Integrations", "info", "%s pending scheduled actions" % sched["pending"],
                     "Top hooks: %s." % ", ".join("%s (%s)" % (r["hook"], r["n"]) for r in (sched.get("pending_top") or [])[:8]),
                     "A large queue runs as soon as the quarantine lifts. Check nothing in it should not run twice."))
    return out


@check
def database(m):
    out = []
    db = g(m, "site", "database", default={})
    if not db:
        return out
    mb = db.get("total_mb") or 0
    files_mb = round((g(m, "pressable", "fileSystemUsageBytes", default=0) or 0) / 1048576)
    size = "Database %s MB in %s tables" % (mb, db.get("tables"))
    if files_mb:
        size += "; files %s MB" % files_mb
    sev = "info"
    action = "Small. The freeze should be minutes."
    if mb > 2000:
        action = "Large. Rehearse the sync and time it; the database pull and apply time is the freeze length. Jetpack's exporter closes its window after an hour, so plan for that or use the Reprint plugin."
        sev = "manual"
    elif mb > 300:
        action = "Medium. Rehearse the sync and time it; that time is the freeze length."
    out.append(F("db.size", "Database and files", sev, size,
                 "Largest tables: %s." % ", ".join("%s (%s MB)" % (t["name"], t["mb"]) for t in (db.get("largest") or [])[:6]),
                 action, steps=["sync.rehearse"]))
    foreign = db.get("foreign_prefix") or []
    if foreign:
        core_like = [t for t in foreign if t in ("wp_options", "wp_posts", "wp_users", "wp_postmeta", "wp_usermeta", "wp_comments")]
        if len(core_like) >= 3:
            out.append(F("db.second-install", "Database and files", "manual",
                         "The database holds a second set of WordPress tables under the `wp_` prefix",
                         "%d tables outside the site's `%s` prefix: %s." % (len(foreign), g(m, "site", "core", "table_prefix"),
                                                                           ", ".join("`%s`" % t for t in foreign[:30])),
                         "These look like leftovers from an earlier install or migration. Confirm nothing reads them. Check whether "
                         "the first sync copies them, and whether they collide with tables the target already has."))
        else:
            out.append(F("db.foreign-tables", "Database and files", "manual", "%d tables do not use the site's table prefix" % len(foreign),
                         ", ".join("`%s`" % t for t in foreign[:30]),
                         "Find out what owns them. Check after the first sync whether they arrived and whether they are needed."))
    prefix = g(m, "site", "core", "table_prefix")
    if prefix and prefix != "wp_":
        out.append(F("db.prefix", "Database and files", "info", "Table prefix is `%s`" % prefix, "",
                     "The WP Cloud adapter sets the target's prefix to match. Confirm after the first sync."))
    php = g(m, "site", "core", "php_version")
    if php:
        out.append(F("core.php", "Site", "auto", "PHP %s on the source" % php, "",
                     "Set the target to the same minor version before the first sync. Change PHP version as a separate task, not during migration.",
                     steps=["prep.php"]))
    return out


@check
def dns(m):
    out = []
    zones = m.get("dns") or []
    if not zones:
        return [F("dns.not-checked", "DNS and domains", "manual", "DNS was not audited", "No dns-*.json in the migration folder.",
                  "Run scripts/dns_audit.py for each apex domain attached to the site.")]
    for z in zones:
        apex = z.get("apex")
        reg = (g(z, "registrar", "registrar") or "unknown registrar").rstrip(".")
        base = "Registrar: %s. Name servers: %s." % (reg, ", ".join(z.get("name_servers") or []) or "unknown")
        if z.get("access_needed_from_partner"):
            decided = g(m, "decisions", "registrar_access", apex)
            sev = "info" if decided == "confirmed" else "blocker"
            out.append(F("dns.access." + apex, "DNS and domains", sev,
                         "%s: registrar or DNS access is needed from the partner%s" % (apex, " (confirmed)" if decided == "confirmed" else ""),
                         base + " " + z.get("access_required", ""),
                         "Do not schedule cutover until someone with access is confirmed and available in the window. Record it with "
                         "`state.py decide registrar_access.%s confirmed`." % apex, steps=["prep.dns-access"]))
        elif z.get("case") == "automattic-registrar/pressable-dns":
            out.append(F("dns.account." + apex, "DNS and domains", "manual", "%s: registered with Automattic, DNS at Pressable" % apex,
                         base, "Find which WordPress.com account holds the registration. The zone moves to WordPress.com DNS.",
                         steps=["dns.zone-move"]))
        elif z.get("case") == "unknown":
            out.append(F("dns.unknown." + apex, "DNS and domains", "manual", "%s: could not read name servers or registrar" % apex,
                         base, "Check by hand."))
        if z.get("dns_host") == "pressable":
            out.append(F("dns.zone." + apex, "DNS and domains", "manual", "%s: the whole DNS zone is hosted at Pressable and must move" % apex,
                         "Records found by guessing names: %s. This is a floor, not the full zone." % ", ".join(sorted(z.get("records", {}).keys())),
                         "Export the full zone from Pressable, recreate it in WordPress.com DNS, and switch name servers last.",
                         steps=["dns.export", "dns.zone-move"]))
        if z.get("mail_related"):
            out.append(F("dns.mail." + apex, "DNS and domains", "manual", "%s: email depends on this zone (%s)" % (apex, z.get("mail_provider_hint")),
                         "Mail-related names: %s." % ", ".join(z["mail_related"]),
                         "Every MX, SPF, DKIM and DMARC record must exist in the new zone before name servers change. DKIM selectors "
                         "cannot be guessed reliably; get them from the zone export.", steps=["dns.zone-move"]))
        if z.get("points_at_other_wpcloud_site"):
            out.append(F("dns.other-sites." + apex, "DNS and domains", "decision", "%s: subdomains point at other sites on our platform" % apex,
                         ", ".join(z["points_at_other_wpcloud_site"]),
                         "Each is a separate site that shares this zone. Decide whether it migrates in the same batch; either way its "
                         "record must be carried into the new zone."))
        if z.get("other_hosts"):
            out.append(F("dns.other-hosts." + apex, "DNS and domains", "info", "%s: records pointing at other services" % apex,
                         ", ".join(z["other_hosts"]), "Carry them into the new zone unchanged."))
        if z.get("wildcard"):
            out.append(F("dns.wildcard." + apex, "DNS and domains", "info", "%s: wildcard record present" % apex, str(z["wildcard"]),
                         "Carry it over and check it does not hide missing records."))
    return out


@check
def deploys(m):
    out = []
    d = m.get("deploy")
    if not d:
        return [F("deploy.not-checked", "Deploys", "manual", "Deploy state was not audited", "No deploy.json in the migration folder.",
                  "Do not connect WordPress.com deploys until this is checked.")]
    prod = d.get("production") or {}
    state = prod.get("state", "unknown")
    where = "Repo `%s`, branch `%s`, DeployHQ project `%s`." % (prod.get("repo"), prod.get("branch"), prod.get("project"))
    if state == "connected-current":
        out.append(F("deploy.current", "Deploys", "auto", "Deploy is connected and current", where + " " + (prod.get("evidence") or ""),
                     "Safe to connect WordPress.com GitHub Deployments from the same branch.", steps=["platform.deploy-connect"]))
    elif state == "behind-tooling-only":
        out.append(F("deploy.tooling-only", "Deploys", "auto", "Deploy is connected; undeployed commits only touch repo tooling",
                     where + " " + (prod.get("evidence") or ""),
                     "Safe to connect WordPress.com GitHub Deployments. The undeployed commits change nothing on the server.",
                     steps=["platform.deploy-connect"]))
    elif state == "behind":
        out.append(F("deploy.behind", "Deploys", "decision", "Deploy is connected but the branch is ahead of the server",
                     where + " " + (prod.get("evidence") or ""),
                     "Review the undeployed commits. Either deploy them on Pressable first and test, or accept that they go live with "
                     "the first WordPress.com deploy.", steps=["platform.deploy-connect"]))
    elif state == "drifted":
        out.append(F("deploy.drifted", "Deploys", "manual", "Files on the server differ from the deployed revision",
                     where + " " + (prod.get("evidence") or ""),
                     "Do not connect deploys yet. Reconcile the server's changes into the repo first, or the first deploy overwrites them.",
                     steps=["platform.deploy-reconcile"]))
    elif state == "not-connected":
        out.append(F("deploy.not-connected", "Deploys", "manual", "No deploy targets the production site",
                     prod.get("evidence") or "No DeployHQ server or host deployment was found for this site.",
                     "Do not connect WordPress.com deploys. Migrate files as they are. Getting production code into git is a separate task.",
                     steps=["platform.deploy-skip"]))
    else:
        out.append(F("deploy.unknown", "Deploys", "manual", "Deploy state could not be determined", prod.get("evidence") or "",
                     "Check DeployHQ and the host's own deployments by hand before connecting anything."))
    others = d.get("other_projects") or []
    if others:
        out.append(F("deploy.other-projects", "Deploys", "info", "Other deploy targets or repos connected with this site",
                     "\n".join("- %s" % o for o in others),
                     "None of these deploys to production. Listed so nobody mistakes one for the production deploy."))
    flagged = d.get("needs_decision") or []
    if flagged:
        out.append(F("deploy.needs-decision", "Deploys", "decision", "A separate project exists for this site and may change the plan",
                     "\n".join("- %s" % o for o in flagged),
                     "Find out what it is for (a redesign in flight is the usual case) and whether this site should be migrated "
                     "before it, with it, or not at all.", owner="TAM"))
    return out


@check
def estate(m):
    out = []
    related = m.get("related") or []
    is_dev = lambda r: bool(r.get("staging")) or bool(__import__("re").search(r"(^|[-.])(dev|development|staging|stage|test)([-.]|$)", (r.get("name") or "") + " " + (r.get("url") or ""), __import__("re").I))  # noqa: E731
    dev_sites = [r for r in related if is_dev(r)]
    other_sites = [r for r in related if not is_dev(r)]
    line = lambda r: "- %s (%s)" % (r.get("url"), r.get("name"))  # noqa: E731
    if dev_sites:
        out.append(F("estate.dev-sites", "Related sites", "auto", "%d development or staging site%s on Pressable" % (len(dev_sites), "" if len(dev_sites) == 1 else "s"),
                     "\n".join(line(r) for r in dev_sites),
                     "Standing rule: not migrated. After cutover a WordPress.com staging site is created with the `develop` branch "
                     "connected, and these are deleted at decommission. Say so only if this site needs something different.",
                     steps=["post.staging"]))
    if other_sites:
        out.append(F("estate.related", "Related sites", "decision", "%d other site%s on the Pressable account with this site's name" % (len(other_sites), "" if len(other_sites) == 1 else "s"),
                     "\n".join(line(r) for r in other_sites),
                     "These are not development copies. Find out what each is (a redesign, a second site for the same partner) and "
                     "whether it migrates with this one, later, or not at all."))
    existing = g(m, "wpcom", "existing_sites", default=[])
    if existing:
        out.append(F("estate.existing-wpcom", "Related sites", "decision", "WordPress.com sites already exist for this partner",
                     "\n".join("- %s" % e for e in existing),
                     "Find out whether one of these is the intended target or left over from an earlier attempt, before creating a new site."))
    pr = m.get("pressable") or {}
    collaborators = pr.get("collaborators") or []
    if collaborators:
        out.append(F("estate.collaborators", "Access", "info", "%d Pressable collaborators" % len(collaborators),
                     ", ".join(c.get("email", "") for c in collaborators),
                     "They lose access when the Pressable site goes. Anyone who still needs access gets it on WordPress.com."))
    admins = g(m, "site", "privileged_users", default=[])
    if admins:
        ours = [u for u in admins if u["email"].endswith(("@automattic.com", "@a8c.com")) or u["email"].startswith("concierge")]
        if len(ours) == len(admins):
            out.append(F("estate.no-partner-user", "Access", "info", "No administrator on the site belongs to the partner",
                         "All %d administrators are Automattic accounts." % len(admins),
                         "Nothing to do for the migration. At handover the partner's WordPress.com username will be needed; worth "
                         "asking for early."))
        out.append(F("estate.admins", "Access", "info", "%d administrators or shop managers (%d look like ours)" % (len(admins), len(ours)),
                     ", ".join("%s <%s>" % (u["login"], u["email"]) for u in admins[:30]),
                     "Accounts travel with the database. Team 51 accounts are removed at handover, not during migration; "
                     "`/offboard-site-audit` in a8cteam51/ops-agent-skills covers that."))
    return out


@check
def context(m):
    notes = g(m, "context", "notes", default=[])
    out = []
    for i, n in enumerate(notes[:15]):
        out.append(F("context.%d" % i, "Context from P2, Slack and Linear", n.get("severity", "info"), n.get("note", ""),
                     "%s %s" % (n.get("source", ""), n.get("url", "")), n.get("action", ""), owner=n.get("owner")))
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
