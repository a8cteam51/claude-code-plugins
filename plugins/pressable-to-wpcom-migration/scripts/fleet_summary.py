#!/usr/bin/env python3
"""One row per audited site, for a portfolio view.

    fleet_summary.py migrations/ > fleet.csv
"""
import csv
import glob
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "migrations"
w = csv.writer(sys.stdout)
w.writerow(["site", "blockers", "decisions", "manual", "videopress", "woocommerce", "woopayments", "db_mb", "dns_access_needed",
            "deploy_state", "blocker_ids"])
for path in sorted(glob.glob(os.path.join(root, "*", "findings.json"))):
    d = os.path.dirname(path)
    findings = json.load(open(path))
    m = json.load(open(os.path.join(d, "manifest.json")))
    ids = {f["id"] for f in findings}
    count = lambda s: sum(1 for f in findings if f["severity"] == s)  # noqa: E731
    woo = (m["site"].get("woocommerce") or {})
    w.writerow([os.path.basename(d), count("blocker"), count("decision"), count("manual"),
                "yes" if "videopress.in-use" in ids else "no", "yes" if woo.get("active") else "no",
                "yes" if "woo.woopayments" in ids else "no", (m["site"].get("database") or {}).get("total_mb"),
                "yes" if any(z.get("access_needed_from_partner") for z in m.get("dns") or []) else "no",
                ((m.get("deploy") or {}).get("production") or {}).get("state", "not-checked"),
                " ".join(sorted(f["id"] for f in findings if f["severity"] == "blocker"))])
