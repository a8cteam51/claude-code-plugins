#!/usr/bin/env python3
"""Compare a zone's answers from two name servers before switching name servers.

    dns_compare.py example.com --old ns1.openhostingservice.com --new ns1.wordpress.com \
        [--names a,b,c] [--names-from DIR] [--ignore-site-records]

Names come from --names, from the `records` of any dns-*.json in --names-from,
and from a BIND or JSON zone export in that folder if present (zone-export.*).
Exit 1 if any name answers differently.

--ignore-site-records skips A/AAAA on the apex and www, which are expected to
differ if the old zone has not been repointed yet.
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA"]


def dig(name, rtype, server):
    out = subprocess.run(["dig", "+short", "+time=3", "+tries=2", "@" + server, rtype, name], capture_output=True, text=True).stdout
    return sorted(line.strip().lower() if rtype != "TXT" else line.strip() for line in out.splitlines() if line.strip() and not line.startswith(";"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apex")
    ap.add_argument("--old", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--names", default="")
    ap.add_argument("--names-from")
    ap.add_argument("--ignore-site-records", action="store_true")
    a = ap.parse_args()
    apex = a.apex.lower().strip(".")
    names = {apex, "www." + apex}
    for n in filter(None, a.names.split(",")):
        n = n.strip().lower().rstrip(".")
        names.add(n if n.endswith(apex) else n + "." + apex)
    if a.names_from:
        for path in glob.glob(os.path.join(a.names_from, "dns-*.json")):
            names.update(json.load(open(path)).get("records", {}).keys())
        for path in glob.glob(os.path.join(a.names_from, "zone-export.*")):
            text = open(path).read()
            for m in re.findall(r"([A-Za-z0-9_*.-]+\." + re.escape(apex) + r")\.?", text):
                names.add(m.lower())
            for m in re.findall(r"^([A-Za-z0-9_*-]+(?:\.[A-Za-z0-9_-]+)*)\s+(?:\d+\s+)?(?:IN\s+)?(?:A|AAAA|CNAME|MX|TXT|SRV|CAA)\s", text, re.M):
                if m != "@":
                    names.add((m + "." + apex).lower())
    names = sorted(n for n in names if "*" not in n and n.endswith(apex))

    diffs = 0
    print("Comparing %d names for %s: %s vs %s" % (len(names), apex, a.old, a.new))
    for name in names:
        for rtype in TYPES:
            if a.ignore_site_records and rtype in ("A", "AAAA") and name in (apex, "www." + apex):
                continue
            old, new = dig(name, rtype, a.old), dig(name, rtype, a.new)
            if old != new:
                diffs += 1
                print("  DIFF %s %s\n       old: %s\n       new: %s" % (name, rtype, old or "-", new or "-"))
    print("RESULT: %s (%d differences)" % ("ZONES MATCH" if not diffs else "ZONES DIFFER", diffs))
    sys.exit(1 if diffs else 0)


if __name__ == "__main__":
    main()
