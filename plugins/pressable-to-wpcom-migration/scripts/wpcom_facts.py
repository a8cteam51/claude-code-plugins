#!/usr/bin/env python3
"""WordPress.com-side facts for a blog ID, merged into wpcom.json.

    wpcom_facts.py <blog id or domain> --out migrations/<domain>/wpcom.json

Reads the public WordPress.com REST API without authentication. Keys already in
the file that this script does not set (for example `existing_sites`) are kept.

`subscribers_count` is the WordPress.com figure. On some sites it has included
social followers, so it can read higher than email and Reader subscribers.
A private site returns nothing here; the value is then left as null.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://public-api.wordpress.com/rest/v1.1/sites/%s?fields=ID,URL,name,subscribers_count,jetpack,is_private"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("--out")
    a = ap.parse_args()
    facts = {"subscribers": None, "subscribers_source": None}
    try:
        with urllib.request.urlopen(urllib.request.Request(API % a.site, headers={"User-Agent": "t51-migration-audit"}), timeout=20) as res:
            data = json.load(res)
        facts.update(blog_id=data.get("ID"), url=data.get("URL"), subscribers=data.get("subscribers_count"),
                     subscribers_source="public-api sites/%s subscribers_count (may include social followers)" % a.site)
    except urllib.error.HTTPError as err:
        facts["subscribers_source"] = "public API returned %s (private site or not found); check wordpress.com/subscribers/<domain>" % err.code
    except Exception as err:  # noqa: BLE001
        facts["subscribers_source"] = "lookup failed: %s" % type(err).__name__
    if a.out:
        existing = json.load(open(a.out)) if os.path.exists(a.out) and os.path.getsize(a.out) else {}
        existing.update(facts)
        with open(a.out, "w") as fh:
            json.dump(existing, fh, indent=2)
            fh.write("\n")
    json.dump(facts, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
