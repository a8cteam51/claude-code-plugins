#!/usr/bin/env python3
"""Compare a zone's answers from two name servers before switching name servers.

    dns_compare.py example.com --old ns1.openhostingservice.com --new ns1.wordpress.com \
        [--names a,b,c] [--names-from DIR] [--ignore-site-records]

Names come from --names and from --names-from: a migration folder (the
`records` of any dns-*.json, a zone export zone-export.*, *.zone or
zone-*.records.json) or one of those files. Exit 1 if any name answers
differently, or if a name has more than one SPF or DMARC record on the new
server (WordPress.com adds its own defaults when a domain is connected).

--ignore-site-records skips A/AAAA on the apex and every type on www, which
are expected to differ once the site has moved (www often becomes a CNAME, and
dig then answers every type with the apex's records).

`atomic-domain-…` TXT values are left out on both sides: each host has its own,
and the export leaves them out on purpose.
"""
import argparse
import glob
import json
import os
import subprocess
import sys

TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV", "CAA"]


def dig(name, rtype, server):
    out = subprocess.run(["dig", "+short", "+time=3", "+tries=2", "@" + server, rtype, name], capture_output=True, text=True).stdout
    return sorted(line.strip().lower() if rtype != "TXT" else line.strip() for line in out.splitlines()
                  if line.strip() and not line.startswith(";") and not line.startswith('"atomic-domain-'))


def bind_names(text, apex):
    """Owner names in a BIND file: $ORIGIN, relative names, @ and blank owners."""
    origin, names, last = apex, set(), apex
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith(";"):
            continue
        if line.startswith("$ORIGIN"):
            origin = line.split()[1].rstrip(".").lower()
            continue
        if line.startswith("$"):
            continue
        if not line[0].isspace():
            tok = line.split()[0]
            last = origin if tok == "@" else tok.rstrip(".").lower() if tok.endswith(".") else "%s.%s" % (tok.lower(), origin)
        names.add(last)
    return names


def file_names(path, apex):
    text = open(path).read()
    if path.endswith(".json"):
        data = json.loads(text)
        recs = data.get("records", data) if isinstance(data, dict) else data
        if isinstance(recs, dict):
            return {k.lower().rstrip(".") for k in recs}
        return {(r.get("name") or "").lower().rstrip(".") or apex for r in recs if isinstance(r, dict)}
    return bind_names(text, apex)


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
        if os.path.isfile(a.names_from):
            files = [a.names_from]
        elif os.path.isdir(a.names_from):
            files = [p for pat in ("dns-*.json", "zone-export.*", "*.zone", "zone-*.records.json")
                     for p in glob.glob(os.path.join(a.names_from, pat))]
        else:
            sys.exit("--names-from: no such file or folder: %s" % a.names_from)
        before = len(names)
        for path in files:
            names.update(file_names(path, apex))
        if len(names) == before:
            sys.exit("--names-from %s gave no names beyond the apex and www" % a.names_from)
    names = sorted(n for n in names if "*" not in n and n.endswith(apex))

    diffs = 0
    print("Comparing %d names for %s: %s vs %s" % (len(names), apex, a.old, a.new))
    for name in names:
        # A CNAME name has no other records, and dig follows the chain differently per server: compare the CNAME only.
        cname = dig(name, "CNAME", a.old) or dig(name, "CNAME", a.new)
        for rtype in (["CNAME"] if cname else TYPES):
            if a.ignore_site_records and (name == "www." + apex or (rtype in ("A", "AAAA") and name == apex)):
                continue
            old, new = dig(name, rtype, a.old), dig(name, rtype, a.new)
            if old != new:
                diffs += 1
                print("  DIFF %s %s\n       old: %s\n       new: %s" % (name, rtype, old or "-", new or "-"))
            if rtype == "TXT":
                for kind, label in (("v=spf1", "SPF"), ("v=dmarc1", "DMARC")):
                    dup = [t for t in new if t.strip('"').lower().startswith(kind)]
                    if len(dup) > 1:
                        diffs += 1
                        print("  DUPLICATE %s on %s at %s: %s\n       Receivers treat two as an error. Delete WordPress.com's default."
                              % (label, a.new, name, " | ".join(dup)))
    print("RESULT: %s (%d differences)" % ("ZONES MATCH" if not diffs else "ZONES DIFFER", diffs))
    sys.exit(1 if diffs else 0)


if __name__ == "__main__":
    main()
