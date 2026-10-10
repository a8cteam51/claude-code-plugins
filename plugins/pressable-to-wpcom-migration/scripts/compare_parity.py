#!/usr/bin/env python3
"""Compare two parity.php outputs (source first, target second).

    compare_parity.py source-parity.json target-parity.json [--strict]

Exit 0 when the data matches, 1 when it does not. Without --strict, options
that are expected to differ between hosts are reported but do not fail.
"""
import json
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    strict = "--strict" in sys.argv
    if len(args) != 2:
        print(__doc__)
        sys.exit(64)
    src, dst = (json.load(open(p)) for p in args)
    problems, notes = [], []

    for key in sorted(set(src["data"]) | set(dst["data"])):
        a, b = src["data"].get(key) or {}, dst["data"].get(key) or {}
        for field in ("n", "max_id", "latest"):
            if str(a.get(field)) != str(b.get(field)) and (field in a or field in b):
                problems.append("%s.%s: source %s, target %s" % (key, field, a.get(field), b.get(field)))

    for table in sorted(set(src["tables"]) | set(dst["tables"])):
        a, b = src["tables"].get(table), dst["tables"].get(table)
        if a is None:
            notes.append("table only on target: %s (%s rows)" % (table, b))
        elif b is None:
            problems.append("table missing on target: %s (%s rows on source)" % (table, a))
        elif a != b:
            # options and usermeta legitimately move a little on a running site.
            (notes if table in ("options", "usermeta") and abs(a - b) <= max(25, a // 200) else problems).append(
                "table %s: source %s rows, target %s rows" % (table, a, b))

    so, do = src["options"], dst["options"]
    for key in ("stylesheet", "template", "permalinks", "admin_email"):
        if so.get(key) != do.get(key):
            problems.append("option %s: source %r, target %r" % (key, so.get(key), do.get(key)))
    missing = sorted(set(so["active_plugins"]) - set(do["active_plugins"]))
    extra = sorted(set(do["active_plugins"]) - set(so["active_plugins"]))
    if missing:
        (problems if strict else notes).append("active on source only: " + ", ".join(missing))
    if extra:
        notes.append("active on target only: " + ", ".join(extra))
    for key in ("jetpack_blog_id", "blog_public", "environment"):
        if so.get(key) != do.get(key):
            notes.append("%s: source %r, target %r" % (key, so.get(key), do.get(key)))
    if so.get("jetpack_blog_id") and so.get("jetpack_blog_id") == do.get("jetpack_blog_id"):
        problems.append("target reports the SOURCE Jetpack blog ID (%s): its own connection was overwritten" % so["jetpack_blog_id"])

    refs = dst.get("other_host_references")
    if refs and (refs["posts"] or refs["postmeta"] or refs["options"]):
        notes.append("target still references %(host)s: %(posts)s posts, %(postmeta)s postmeta rows, %(options)s options" % refs)

    for label, side in (("source", src), ("target", dst)):
        after = {k: v for k, v in (side.get("after_since") or {}).items() if k != "since" and v}
        if after:
            problems.append("%s has writes after %s: %s" % (label, side["after_since"]["since"], after))

    print("Source: %s (%s)\nTarget: %s (%s)\n" % (src["home"], src["collected_at"], dst["home"], dst["collected_at"]))
    print("MISMATCHES (%d)" % len(problems))
    for p in problems:
        print("  - " + p)
    print("\nNOTES (%d)" % len(notes))
    for n in notes:
        print("  - " + n)
    print("\nRESULT: " + ("PARITY" if not problems else "NOT IN PARITY"))
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
