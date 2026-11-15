#!/usr/bin/env python3
"""Find the rows that differ between the source and target databases, table by table.

    db_diff.py --source <pressable site> --target <wpcom site> --hosts a.example,b.wpcomstaging.com \\
               --out <dir>/db-diff [--sql] [--bucket 1000] [--max-buckets 50]

There is one copy, so anything written on the live site after it ran exists only
there. This finds it. Every table is fingerprinted in buckets of rows on both sides
(db_diff.php, read-only); only the buckets that differ are listed row by row, and
only the rows that differ are fetched in full.

Each difference is one of:
  GAP     a row on the source that is missing or different on the target: data that
          would be lost at cutover. These are what must be resolved.
  TARGET  a row only on the target, or one the platform changes on its own (options,
          caches, queues, sessions). Listed, not a gap.

Writes DIFF.md (readable summary), diff.json (everything) and, with --sql, delta.sql:
REPLACE statements for the GAP rows, taken from the source, for a developer to review.
This script never writes to either site. Exit 1 when there is at least one GAP.
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))

# Tables whose contents differ between any two running copies. Compared, but every
# difference is TARGET, never GAP.
VOLATILE_TABLES = re.compile(
    r"^(actionscheduler_(logs|claims)|jetpack_sync_queue|woocommerce_sessions|wc_rate_limits|woocommerce_log|"
    r"wc_admin_notes|wc_admin_note_actions|redirection_404|redirection_logs|wfhits|wflogs|wfls_|e_events|"
    r"yoast_indexable|yoast_seo_links|wc_product_meta_lookup|wc_order_stats|wc_order_product_lookup|"
    r"wc_customer_lookup|wc_category_lookup|wc_reserved_stock|a8csp_|pmxe_|statistics_)")
# Option names the platform, caches or Jetpack rewrite on the target.
VOLATILE_OPTIONS = re.compile(
    r"^(_site_transient_|_transient_|cron$|rewrite_rules$|jetpack|jp_sync_|jpsq_|jb_|odyssey_|wpcom|at_|atomic|"
    r"wordpress_api_key|reprint_|plugin_update_delays$|fresh_site$|[a-z_]+_children$|"
    r"active_plugins$|recently_activated$|recovery_|auto_updater|auto_core_update|can_compress_scripts$|"
    r"db_upgraded$|uninstall_plugins$|_wp_suggested|wp_.*_last_|woocommerce_admin_|wc_admin_|action_scheduler|"
    r"siteurl$|home$|blog_public$|admin_email_lifespan$|ftp_credentials$|t51_|a8csp|stats_|vaultpress|akismet_)")
VOLATILE_META = re.compile(r"^(_edit_lock|_edit_last|session_tokens|_wp_old_slug|wp_dashboard_quick_press_last_post_id|"
                           r"_wc_session|jetpack|_jetpack|wpcom|_wpcom|wp_wpcom|community-events-location|_transient|"
                           r"my-jetpack-|wp_persisted_preferences|wp_user-settings)")
# What to show for a row, by table. Anything else shows its first columns.
LABEL = {
    "posts": ["ID", "post_type", "post_status", "post_title", "post_modified_gmt"],
    "postmeta": ["post_id", "meta_key"],
    "comments": ["comment_ID", "comment_post_ID", "comment_author", "comment_date_gmt", "comment_approved"],
    "commentmeta": ["comment_id", "meta_key"],
    "users": ["ID", "user_login", "user_registered"],
    "usermeta": ["user_id", "meta_key"],
    "options": ["option_name"],
    "terms": ["term_id", "name"],
    "term_taxonomy": ["term_taxonomy_id", "taxonomy"],
    "term_relationships": ["object_id", "term_taxonomy_id"],
    "wc_orders": ["id", "status", "type", "total_amount", "date_created_gmt", "date_updated_gmt"],
    "wc_orders_meta": ["order_id", "meta_key"],
    "woocommerce_order_items": ["order_item_id", "order_id", "order_item_name"],
    "woocommerce_order_itemmeta": ["order_item_id", "meta_key"],
}


def run(host, site, mode, **args):
    env = dict(os.environ, T51_ARGS=json.dumps(dict(mode=mode, **args)))
    res = subprocess.run([os.path.join(HERE, "wp_eval.sh"), host, site, os.path.join(HERE, "db_diff.php")],
                         env=env, capture_output=True, text=True)
    if res.returncode != 0:
        sys.exit("db_diff.php failed on %s %s (%s):\n%s" % (host, site, mode, (res.stderr or res.stdout)[-2000:]))
    return json.loads(res.stdout)


def both(src_call, dst_call):
    """Run the source and target calls at the same time: each one is mostly waiting on the CLI."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        a, b = pool.submit(*src_call), pool.submit(*dst_call)
        return a.result(), b.result()


def label(table, row):
    cols = LABEL.get(table) or list(row)[:4]
    return ", ".join("%s=%s" % (c, str(row.get(c))[:80].replace("\n", " ")) for c in cols if c in row)


def volatile(table, row):
    if VOLATILE_TABLES.match(table):
        return True
    if table == "options":
        return bool(VOLATILE_OPTIONS.match(row.get("option_name") or ""))
    if table.endswith("meta"):
        return bool(VOLATILE_META.match(row.get("meta_key") or ""))
    return False


def sql_value(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n").replace("\r", "\\r").replace("\0", "\\0") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, help="Pressable site domain or ID")
    ap.add_argument("--target", required=True, help="WordPress.com site domain or ID")
    ap.add_argument("--hosts", required=True, help="comma-separated host names that are the same site (source and target addresses)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--bucket", type=int, default=1000)
    ap.add_argument("--max-buckets", type=int, default=50, help="per table; beyond this the table is reported, not listed")
    ap.add_argument("--tables", help="comma-separated tables without prefix (default: all)")
    ap.add_argument("--sql", action="store_true", help="write delta.sql with the GAP rows from the source")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    hosts = [h.strip() for h in a.hosts.split(",") if h.strip()]
    common = dict(hosts=hosts, size=a.bucket)
    if a.tables:
        common["tables"] = [t.strip() for t in a.tables.split(",")]

    print("Fingerprinting both databases...", file=sys.stderr)
    src, dst = both((lambda: run("pressable", a.source, "buckets", **common),), (lambda: run("wpcom", a.target, "buckets", **common),))
    # PHP sends an array with keys 0, 1, 2… as a JSON list, and an empty one as []. Make them all dicts.
    for side in (src, dst):
        for t in side["tables"].values():
            if isinstance(t["buckets"], list):
                t["buckets"] = {str(i): v for i, v in enumerate(t["buckets"])}
    if src["prefix"] != dst["prefix"]:
        print("Note: table prefix differs (%s on source, %s on target)." % (src["prefix"], dst["prefix"]), file=sys.stderr)

    report = {"source": a.source, "target": a.target, "hosts": hosts, "source_at": src["collected_at"],
              "target_at": dst["collected_at"], "regexp": src["regexp"] and dst["regexp"], "tables": {}}
    gaps = target_only = 0
    sql = []

    # Pass 1: which tables and buckets differ.
    drill = {}
    for table in sorted(set(src["tables"]) | set(dst["tables"])):
        s, d = src["tables"].get(table), dst["tables"].get(table)
        entry = {"status": "same", "gap": [], "target": [], "note": ""}
        report["tables"][table] = entry
        if not d:
            n = sum(v[0] for v in s["buckets"].values())
            entry.update(status="missing on target", note="%d rows" % n)
            if n and not VOLATILE_TABLES.match(table):
                gaps += 1
            continue
        if not s:
            entry.update(status="only on target")
            continue
        if s["columns"] != d["columns"]:
            entry["note"] = "columns differ: source %s, target %s" % (s["columns"], d["columns"])
        diff_buckets = sorted({b for b in set(s["buckets"]) | set(d["buckets"]) if s["buckets"].get(b) != d["buckets"].get(b)}, key=float)
        if not diff_buckets:
            continue
        entry["status"] = "differs"
        rows_differ = sum(abs((s["buckets"].get(b) or [0])[0] - (d["buckets"].get(b) or [0])[0]) for b in diff_buckets)
        if len(diff_buckets) > a.max_buckets or not s["pk"]:
            entry["note"] = ("%d buckets differ (at least %d rows), too many to list" % (len(diff_buckets), rows_differ)) if s["pk"] else "no primary key: rows cannot be matched"
            if not VOLATILE_TABLES.match(table):
                gaps += 1
                entry["gap"].append({"label": entry["note"]})
            continue
        drill[table] = [int(float(b)) for b in diff_buckets]

    # Pass 2: row hashes in the differing buckets, one call per side.
    sr_all, dr_all = {}, {}
    if drill:
        print("Listing rows in %d differing tables..." % len(drill), file=sys.stderr)
        sr_all, dr_all = both((lambda: run("pressable", a.source, "rows", hosts=hosts, size=a.bucket, want=drill)["tables"],),
                              (lambda: run("wpcom", a.target, "rows", hosts=hosts, size=a.bucket, want=drill)["tables"],))
    plan = {}
    for table in drill:
        sr = (sr_all.get(table) or {}).get("rows") or {}
        dr = (dr_all.get(table) or {}).get("rows") or {}
        sr = sr if isinstance(sr, dict) else {}
        dr = dr if isinstance(dr, dict) else {}
        plan[table] = {
            "missing": [k[1:] for k in sr if k not in dr],
            "changed": [k[1:] for k in sr if k in dr and sr[k] != dr[k]],
            "extra": [k[1:] for k in dr if k not in sr],
        }

    # Pass 3: the differing rows in full, one call per side.
    want_src = {t: p["missing"] + p["changed"] for t, p in plan.items() if p["missing"] or p["changed"]}
    want_dst = {t: p["changed"] + p["extra"] for t, p in plan.items() if p["changed"] or p["extra"]}
    fs_all, fd_all = both((lambda: run("pressable", a.source, "fetch", want=want_src)["tables"] if want_src else {},),
                          (lambda: run("wpcom", a.target, "fetch", want=want_dst)["tables"] if want_dst else {},))

    def keyed(res):
        pk = (res or {}).get("pk") or []
        return {chr(31).join(str(row[c]) for c in pk): row for row in (res or {}).get("rows") or []}

    for table, p in plan.items():
        entry = report["tables"][table]
        fs, fd = keyed(fs_all.get(table)), keyed(fd_all.get(table))
        for kind, keys in (("only on source", p["missing"]), ("differs", p["changed"])):
            for k in keys:
                row = fs.get(k, {})
                item = {"kind": kind, "key": k.replace(chr(31), ","), "label": label(table, row)}
                if kind == "differs" and k in fd:
                    cols = [c for c in row if str(row.get(c)) != str(fd[k].get(c)) and not any(h in str(row.get(c)) for h in hosts)]
                    item["columns"] = cols or ["(host names only)"]
                # The admin password is rotated when the site is created; a password-only difference is not data.
                if volatile(table, row) or (table == "users" and set(item.get("columns") or []) <= {"user_pass", "user_activation_key"} and item.get("columns")):
                    entry["target"].append(item)
                    continue
                entry["gap"].append(item)
                gaps += 1
                if a.sql and row:
                    cols = list(row)
                    sql.append("REPLACE INTO `%s%s` (%s) VALUES (%s);" % (
                        dst["prefix"], table, ", ".join("`%s`" % c for c in cols), ", ".join(sql_value(row[c]) for c in cols)))
        for k in p["extra"]:
            entry["target"].append({"kind": "only on target", "key": k.replace(chr(31), ","), "label": label(table, fd.get(k, {}))})
            target_only += 1

    with open(os.path.join(a.out, "diff.json"), "w") as f:
        json.dump(report, f, indent=1)

    lines = ["# Database diff", "",
             "- Source: %s (read %s UTC)" % (a.source, src["collected_at"]),
             "- Target: %s (read %s UTC)" % (a.target, dst["collected_at"]),
             "- Host names treated as the same site: %s" % ", ".join(hosts),
             "- **Result: %s** — %d gap rows or tables, %d target-only or platform rows" % ("GAPS" if gaps else "NO GAPS", gaps, target_only), ""]
    if not report["regexp"]:
        lines += ["Serialized-string lengths could not be normalised on one side (no REGEXP_REPLACE), so rows holding a "
                  "rewritten URL inside serialized data can show as changed.", ""]
    lines += ["## Gaps: on the source, missing or different on the target", ""]
    for table, e in report["tables"].items():
        if e["status"] == "missing on target" and not VOLATILE_TABLES.match(table):
            lines.append("- **%s**: table missing on target (%s)" % (table, e["note"]))
        for g in e["gap"]:
            cols = (" (columns: %s)" % ", ".join(g["columns"])) if g.get("columns") else ""
            lines.append("- **%s** %s: %s%s" % (table, g.get("kind", ""), g.get("label") or g.get("key"), cols))
    if not gaps:
        lines.append("None.")
    lines += ["", "## Target-only and platform differences (not gaps)", ""]
    for table, e in report["tables"].items():
        if e["target"]:
            kinds = {}
            for t in e["target"]:
                kinds.setdefault(t["kind"], []).append(t["label"] or t["key"])
            for kind, labels in kinds.items():
                lines.append("- **%s** %s (%d): %s%s" % (table, kind, len(labels), "; ".join(labels[:8]), " …" if len(labels) > 8 else ""))
        if e["status"] == "only on target":
            lines.append("- **%s**: table only on target" % table)
        if e["note"] and e["status"] != "missing on target":
            lines.append("- **%s**: %s" % (table, e["note"]))
    with open(os.path.join(a.out, "DIFF.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    if a.sql:
        with open(os.path.join(a.out, "delta.sql"), "w") as f:
            f.write("-- GAP rows from the source, for review. Not applied. Host names are the SOURCE's: after applying,\n"
                    "-- run search-replace for the source host on these tables.\n" + "\n".join(sql) + "\n")
    print("\n".join(lines[:7]))
    print("Written: %s" % ", ".join(n for n in ("DIFF.md", "diff.json", "delta.sql" if a.sql else "") if n))
    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
