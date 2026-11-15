#!/usr/bin/env python3
"""Compare what the source and the target serve from outside wp-content.

    web_root_compare.py webroot.json webroot-target.json [--paths-out FILE]
        [--fetch-out FILE --source-url https://example.org]

Both files are web_root.php output. Prints each web-root folder or file on the
source with its file count and size on both sides, and lists files missing or
a different size on the target. With --paths-out, writes the paths to check
over HTTP with url_check.py --paths: every linked file found in the source's
web root, plus the redirect rules from file paths. With --fetch-out, writes the
T51_ARGS for web_root_fetch.php: the files the target lacks, plus each plain
redirect source path (the fetch follows the redirect and places the file at
the old path; it never overwrites a file inside wp-content).
Exit 1 if anything on the source is missing or smaller on the target.
"""
import argparse
import json
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--paths-out")
    ap.add_argument("--fetch-out")
    ap.add_argument("--source-url", help="the source's public address, for --fetch-out")
    a = ap.parse_args()
    src, dst = json.load(open(a.source)), json.load(open(a.target))
    there = {e["name"]: e for e in dst.get("entries") or []}
    bad = 0
    for e in src.get("entries") or []:
        t = there.get(e["name"])
        s_files, t_files = e.get("files", 1), (t or {}).get("files", 1 if t else 0)
        s_bytes, t_bytes = e.get("bytes", 0), (t or {}).get("bytes", 0)
        ok = t is not None and t_files >= s_files and t_bytes >= s_bytes
        bad += not ok
        print("%-4s %-40s source %6d files %12d bytes   target %s" % (
            "ok" if ok else "DIFF", e["name"] + ("/" if e["type"] == "dir" else ""), s_files, s_bytes,
            "%6d files %12d bytes" % (t_files, t_bytes) if t else "missing"))
    if not src.get("entries"):
        print("Nothing in the source's web root.")
    # Per file, where both sides listed their files (web_root.php lists up to 5000 per folder).
    have = {p: b for e in dst.get("entries") or [] for p, b in e.get("list") or []}
    have.update((e["name"], e.get("bytes", 0)) for e in dst.get("entries") or [] if e["type"] == "file")
    lack = []
    for e in src.get("entries") or []:
        for p, b in e.get("list") or ([[e["name"], e.get("bytes", 0)]] if e["type"] == "file" else []):
            if have.get(p) != b:
                lack.append(p)
        if e.get("list") is not None and len(e["list"]) < e.get("files", 0):
            print("     %s/: only %d of %d files listed; compare the rest by hand" % (e["name"], len(e["list"]), e["files"]))
    for p in lack[:20]:
        print("     missing or different on the target: %s" % p)
    if len(lack) > 20:
        print("     ...and %d more" % (len(lack) - 20))
    red = src.get("redirects") or {}
    old_paths = red.get("from_static_paths")
    if old_paths is None:  # webroot.json from before from_static_paths
        old_paths = [x.split(": ", 1)[1].split(" -> ")[0] for x in red.get("from_static_examples") or []]
    if a.fetch_out:
        if not (a.source_url or "").startswith("https://"):
            sys.exit("--fetch-out needs --source-url https://<the source's public address>")
        fetch = list(dict.fromkeys(lack + [p.lstrip("/") for p in old_paths]))
        with open(a.fetch_out, "w") as fh:
            json.dump({"source": a.source_url.rstrip("/"), "paths": fetch, "max": 200}, fh, indent=1)
        print("%d paths to fetch written to %s (%d missing files, %d old redirected paths)" % (len(fetch), a.fetch_out, len(lack), len(old_paths)))
    if a.paths_out:
        paths = [p for l in (src.get("links") or {}).get("by_dir") or [] for p in l.get("paths") or []]
        paths += old_paths
        with open(a.paths_out, "w") as fh:
            fh.write("\n".join(dict.fromkeys(paths)) + ("\n" if paths else ""))
        print("%d paths written to %s" % (len(paths), a.paths_out))
    sys.exit(1 if bad or lack else 0)


if __name__ == "__main__":
    main()
