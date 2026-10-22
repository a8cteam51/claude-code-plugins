#!/usr/bin/env python3
"""Fetch the same paths from two hosts and compare status codes and redirects.

    url_check.py https://source.example https://target.example [--limit 150] [--paths file]

Paths come from the source's sitemap (wp-sitemap.xml, sitemap_index.xml,
sitemap.xml) plus a few fixed ones, or from --paths (one path per line).
GET requests only. Exit 1 if any path that works on the source fails on the target.
"""
import argparse
import re
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

UA = "Mozilla/5.0 (compatible; t51-migration-check/1.0)"
FIXED = ["/", "/wp-login.php", "/wp-json/", "/feed/", "/robots.txt", "/favicon.ico", "/?s=test", "/this-page-should-404-t51/"]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


opener = urllib.request.build_opener(NoRedirect)


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with opener.open(req, timeout=timeout) as res:
            return res.status, "", res.read(200000)
    except urllib.error.HTTPError as err:
        return err.code, err.headers.get("Location", ""), b""
    except Exception as err:  # noqa: BLE001
        return 0, type(err).__name__, b""


def sitemap_paths(base, limit):
    paths, seen, queue = [], set(), [base + p for p in ("/wp-sitemap.xml", "/sitemap_index.xml", "/sitemap.xml")]
    while queue and len(paths) < limit and len(seen) < 60:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        status, location, body = fetch(url)
        if status in (301, 302) and location:
            queue.append(location if location.startswith("http") else base + location)
            continue
        for loc in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body.decode("utf-8", "replace")):
            if loc.endswith(".xml"):
                queue.append(loc)
            else:
                path = urlparse(loc).path or "/"
                if path not in paths:
                    paths.append(path)
    return paths[:limit]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("target")
    ap.add_argument("--limit", type=int, default=150)
    ap.add_argument("--paths")
    a = ap.parse_args()
    src, dst = a.source.rstrip("/"), a.target.rstrip("/")
    src_host, dst_host = urlparse(src).netloc, urlparse(dst).netloc
    if a.paths:
        paths = [line.strip() for line in open(a.paths) if line.strip()]
    else:
        paths = FIXED + [p for p in sitemap_paths(src, a.limit) if p not in FIXED]
    problems = 0
    print("%d paths: %s -> %s" % (len(paths), src, dst))
    for path in paths:
        s_code, s_loc, _ = fetch(src + path)
        d_code, d_loc, _ = fetch(dst + path)
        same_redirect = s_loc.replace(src_host, "HOST") == d_loc.replace(dst_host, "HOST")
        if s_code == d_code and (s_code not in (301, 302, 307, 308) or same_redirect):
            continue
        # A challenge page or rate limit on either side is not a migration difference.
        bad = s_code in (200, 301, 302, 307, 308) and d_code != s_code or (s_code == d_code and not same_redirect)
        problems += 1 if bad else 0
        print("  %s %s: source %s %s | target %s %s" % ("DIFF" if bad else "note", path, s_code, s_loc, d_code, d_loc))
    print("RESULT: %s (%d differences)" % ("MATCH" if not problems else "DIFFERENCES", problems))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
