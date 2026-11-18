#!/usr/bin/env python3
"""Write a zone's records as served by one name server, or compare it with an earlier snapshot.

    zone_snapshot.py <apex> --names <file> [--ns ns1.wordpress.com] --out zone-before.txt
    zone_snapshot.py <apex> --names zone-before.txt --diff zone-before.txt

WordPress.com's DNS screen has no export, and DNS cannot list a zone, so the names come from a
file: one name per line (relative to the apex, `@` for the apex, `*` for a wildcard), or an earlier
snapshot, whose names are reused. Values are queried from the name server, so a name misread from a
screenshot shows up as missing rather than as a wrong value.

Read-only: it only sends DNS queries. Exit 1 when a name has no answer, or with --diff when
anything differs.
"""
import argparse
import datetime
import re
import subprocess
import sys

TYPES = ("A", "AAAA", "CNAME", "MX", "TXT", "NS", "SRV", "CAA")


def dig(ns, rtype, name, authority=False):
    extra = ["+noall", "+authority"] if authority else ["+short"]
    out = subprocess.run(["dig", "+norecurse", rtype, name, "@" + ns] + extra, capture_output=True, text=True).stdout
    return [line.strip() for line in out.splitlines() if line.strip() and not line.startswith(";")]


def read_names(path):
    names = []
    for line in open(path):
        line = line.split(";", 1)[0].strip() if not line.lstrip().startswith(";@") else ""
        if not line or line.startswith("$"):
            continue
        name = line.split()[0]
        if name not in names:
            names.append(name)
    return names


def records(apex, ns, names):
    out, missing = [], []
    probe = "wildcard-probe-%d" % int(datetime.datetime.now().timestamp())
    for name in names:
        fqdn = apex if name == "@" else "%s.%s" % (probe if name == "*" else name, apex)
        found = []
        for rtype in TYPES:
            if rtype == "NS" and name != "@":
                # A delegation answers in the authority section of the parent's referral.
                found += [("NS", r.split()[-1]) for r in dig(ns, "NS", fqdn, authority=True) if re.search(r"\sNS\s", r)]
                continue
            values = dig(ns, rtype, fqdn)
            if rtype == "TXT":
                values = ['"%s"' % "".join(p.strip('"') for p in v.split('" "')) for v in values]
            if rtype == "CNAME":
                values = values[:1]
            found += [(rtype, v) for v in values]
        if any(t == "CNAME" for t, _ in found):
            found = [(t, v) for t, v in found if t == "CNAME"]  # a CNAME name has nothing else of its own
        if not found:
            missing.append(name)
        out += ["%s %s %s" % (name, t, v) for t, v in sorted(set(found))]
    return out, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apex")
    ap.add_argument("--names", required=True, help="a names file, or an earlier snapshot whose names are reused")
    ap.add_argument("--ns", default="ns1.wordpress.com")
    ap.add_argument("--out")
    ap.add_argument("--diff", help="an earlier snapshot to compare with")
    a = ap.parse_args()
    names = read_names(a.names)
    if "@" not in names:
        names.insert(0, "@")
    lines, missing = records(a.apex, a.ns, names)
    if a.diff:
        before = {l.strip() for l in open(a.diff) if l.strip() and not l.startswith(("$", ";"))}
        now = set(lines)
        gone, new = sorted(before - now), sorted(now - before)
        for l in gone:
            print("- " + l)
        for l in new:
            print("+ " + l)
        print("ZONES MATCH" if not (gone or new) else "%d removed, %d added" % (len(gone), len(new)))
        sys.exit(1 if gone or new else 0)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    text = "\n".join(["; %s as served by %s, %s." % (a.apex, a.ns, stamp), "$ORIGIN %s." % a.apex, ""] + lines) + "\n"
    if a.out:
        open(a.out, "w").write(text)
    else:
        sys.stdout.write(text)
    print("%d records from %d names; no answer for: %s" % (len(lines), len(names), ", ".join(missing) or "none"), file=sys.stderr)
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
