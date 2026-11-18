#!/usr/bin/env python3
"""Compare two site_audit.php outputs: source first, target second.

    compare_sites.py site.json site-target.json

Reports differences in plugins, theme, mu-plugins, drop-ins, versions and the
things a migration can silently lose. Exit 1 if anything needs attention.

Source is the WordPress.com (Atomic) site, target the Pressable site.
"""
import json
import sys

# Plugins each platform supplies itself. A difference in these is a note, not a problem.
HOST_PLUGINS = {"wpcomsh", "page-optimize", "gutenberg", "woocommerce-fraud-protection", "pressable-cache-management",
                "pressable-onepress-login", "jetpack", "akismet"}
# WordPress.com's own mu-plugins, which the copy leaves behind on purpose.
WPCOM_MU = ("wpcomsh", "woocommerce-fraud-protection")
# REST namespaces WordPress.com's platform plugins register (thinkbiggerinnovation.com, 2026-11-17).
WPCOM_NAMESPACES = ("help-center", "jetpack-global-styles/", "newspack-blocks/", "wpcomsh/", "wpcom/", "wpcom-")
# Namespaces Jetpack did not register while held offline by the quarantine; re-check them after cut.jetpack.
OFFLINE_NAMESPACES = ("my-jetpack/", "jetpack/v4/explat")


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(64)
    src, dst = (json.load(open(p)) for p in sys.argv[1:3])
    problems, notes = [], []
    sp = {p["slug"]: p for p in src["plugins"]}
    dp = {p["slug"]: p for p in dst["plugins"]}
    for slug, p in sorted(sp.items()):
        q = dp.get(slug)
        bucket = notes if slug in HOST_PLUGINS else problems
        if not q:
            bucket.append("plugin missing on target: %s (%s on source)" % (slug, "active" if p["active"] else "inactive"))
        else:
            if p["version"] != q["version"]:
                bucket.append("plugin %s: version %s on source, %s on target" % (slug, p["version"], q["version"]))
            if p["active"] != q["active"]:
                problems.append("plugin %s: %s on source, %s on target" % (slug, "active" if p["active"] else "inactive",
                                                                           "active" if q["active"] else "inactive"))
    for slug in sorted(set(dp) - set(sp)):
        notes.append("plugin only on target: %s (%s)" % (slug, "active" if dp[slug]["active"] else "inactive"))

    for key in ("active", "parent", "version"):
        if src["themes"][key] != dst["themes"][key]:
            problems.append("theme %s: %r on source, %r on target" % (key, src["themes"][key], dst["themes"][key]))
    missing_themes = set(src["themes"]["installed"]) - set(dst["themes"]["installed"])
    if missing_themes:
        notes.append("themes not on target: " + ", ".join(sorted(missing_themes)))

    for label, a, b in (("mu-plugin files", src["mu_plugins"]["files"], dst["mu_plugins"]["files"]),
                        ("mu-plugin dirs", src["mu_plugins"]["dirs"], dst["mu_plugins"]["dirs"])):
        only_src, only_dst = sorted(set(a) - set(b)), sorted(set(b) - set(a))
        platform = [m for m in only_src if m.startswith(WPCOM_MU)]
        only_src = [m for m in only_src if m not in platform]
        if platform:
            notes.append("WordPress.com %s left behind as expected: %s" % (label, ", ".join(platform)))
        if only_src:
            problems.append("%s missing on target: %s" % (label, ", ".join(only_src)))
        if only_dst:
            notes.append("%s only on target: %s" % (label, ", ".join(only_dst)))
    if dst.get("host_files"):
        leftovers = [h for h in dst["host_files"] if h.startswith(("mu-plugins/wpcomsh", "mu-plugins/woocommerce-fraud-protection"))]
        if leftovers:
            problems.append("WordPress.com platform files on target: " + ", ".join(leftovers))

    for label, path in (("WordPress version", ("core", "wp_version")), ("table prefix", ("core", "table_prefix")),
                        ("permalinks", ("core", "permalinks")), ("timezone", ("core", "timezone")), ("locale", ("core", "locale"))):
        a, b = src[path[0]][path[1]], dst[path[0]][path[1]]
        if a != b:
            problems.append("%s: %r on source, %r on target" % (label, a, b))
    a, b = src["core"]["php_version"].rsplit(".", 1)[0], dst["core"]["php_version"].rsplit(".", 1)[0]
    if a != b:
        problems.append("PHP: %s on source, %s on target" % (a, b))
    if dst["core"].get("environment_type") != "production":
        notes.append("target environment type is %r" % dst["core"].get("environment_type"))
    if src["jetpack"].get("blog_id") and src["jetpack"]["blog_id"] == dst["jetpack"].get("blog_id"):
        # The copy brings the source's Jetpack connection options. The quarantine keeps Jetpack offline, and the
        # cutover clears them and connects afresh; a target that still holds them after cutover could talk to the
        # live WordPress.com blog.
        quarantined = "t51-migration-quarantine.php" in dst["mu_plugins"]["files"]
        (notes if quarantined else problems).append(
            "target holds the SOURCE Jetpack connection (blog ID %s)%s" % (
                src["jetpack"]["blog_id"], "; the quarantine keeps Jetpack offline until cut.jetpack clears it" if quarantined
                else " and the quarantine is gone: clear it now (cut.jetpack) before Jetpack talks to the live blog"))
    src_key, dst_key = src["team51"].get("atlantis_key"), dst["team51"].get("atlantis_key")
    if src_key and src_key != dst_key and not src["team51"].get("atlantis_messages"):
        notes.append("Atlantis encryption key differs (source %s, target %s); the source has no messages, so nothing is lost" % (src_key, dst_key or "none"))
    elif src_key and src_key != dst_key:
        problems.append("Atlantis encryption key differs (source %s, target %s): the copied Atlantis messages cannot be "
                        "decrypted; see step prep.atlantis-key" % (src_key, dst_key or "none"))
    if dst["team51"].get("safety_net"):
        problems.append("SafetyNet is present on the target: remove it before anything else")

    src_consts = {c["name"] for c in src["constants"]["in_wp_config"]}
    dst_consts = {c["name"] for c in dst["constants"]["in_wp_config"]}
    not_carried = sorted(src_consts - dst_consts - {"WP_DEBUG", "WP_CACHE", "DISABLE_WP_CRON"})
    if not_carried:
        notes.append("constants in source wp-config but not target: " + ", ".join(not_carried))
    src_ns, dst_ns = set(src["rest_namespaces"]), set(dst["rest_namespaces"])
    missing_ns = sorted(src_ns - dst_ns)
    platform_ns = [n for n in missing_ns if n.startswith(WPCOM_NAMESPACES)]
    offline_ns = [n for n in missing_ns if n.startswith(OFFLINE_NAMESPACES)
                  and "t51-migration-quarantine.php" in dst["mu_plugins"]["files"]]
    missing_ns = [n for n in missing_ns if n not in platform_ns and n not in offline_ns]
    if platform_ns:
        notes.append("WordPress.com platform REST namespaces not on target (expected): " + ", ".join(platform_ns))
    if offline_ns:
        notes.append("Jetpack REST namespaces missing while the quarantine holds Jetpack offline; re-check after "
                     "cut.jetpack: " + ", ".join(offline_ns))
    if missing_ns:
        problems.append("REST namespaces missing on target: " + ", ".join(missing_ns))
    src_cron, dst_cron = set(src["cron"]["hooks"]), set(dst["cron"]["hooks"])
    if src_cron - dst_cron:
        notes.append("cron hooks not scheduled on target: " + ", ".join(sorted(src_cron - dst_cron)[:30]))

    print("NEEDS ATTENTION (%d)" % len(problems))
    for p in problems:
        print("  - " + p)
    print("\nNOTES (%d)" % len(notes))
    for n in notes:
        print("  - " + n)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
