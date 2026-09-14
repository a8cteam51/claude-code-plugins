#!/usr/bin/env python3
"""Find pages that exist on BOTH the before and after sites, and rank them.

A launch comparison is only meaningful for URLs present on both sides, so this
intersects the two sites rather than trusting either one alone. It pulls from
sitemap.xml (authoritative but sometimes missing) and from homepage nav links
(always present, catches the pages humans actually care about).

Ranking is heuristic and deliberately opinionated: a reviewer wants the home
page, a template of each major type (product, listing, article), and the
conversion path — not 300 blog posts. Claude should treat the output as a
proposal to show the user, not a final answer.

Usage:
  python3 discover_pages.py BEFORE_URL AFTER_URL [--limit 14] [--out config.json]
"""
import argparse
import gzip
import json
import re
import sys
import urllib.error
import urllib.request
from collections import OrderedDict
from urllib.parse import urljoin, urlparse

# Discovered paths and titles can carry non-ASCII, and the progress log goes to
# stderr — don't let a C/POSIX locale turn that into a crash.
for _stream in (sys.stdout, sys.stderr):
    _stream.reconfigure(encoding="utf-8", errors="replace")

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
TIMEOUT = 25
# Consecutive failed reachability checks before concluding the problem is the
# host rather than the individual URLs.
DEAD_STREAK_LIMIT = 10

# (category, friendly label, regex, priority) — lower priority sorts first.
# Ordered so one representative of each template type outranks a second of any.
RULES = [
    ("home", "Home", r"^/$", 0),
    ("shop", "Shop / Listing", r"^/(shop|store|products|collections|catalog|all-products)/?$", 10),
    ("category", "Category / Collection", r"^/(product-category|collections|category|shop)/[^/]+/?$", 20),
    ("product", "Product", r"^/(product|products|shop|item)/[^/]+/?$", 30),
    ("blog", "Blog Index", r"^/(blog|news|articles|insights|journal|resources)/?$", 40),
    ("post", "Article", r"^/(blog|news|articles|insights|journal)/.+", 50),
    ("about", "About", r"^/(about|about-us|our-story|company|who-we-are)[^/]*/?$", 60),
    ("cart", "Cart", r"^/cart/?$", 70),
    ("checkout", "Checkout", r"^/checkout/?$", 75),
    ("contact", "Contact", r"^/(contact|contact-us|get-in-touch)[^/]*/?$", 80),
    ("pricing", "Pricing", r"^/(pricing|plans|membership)[^/]*/?$", 85),
    ("faq", "FAQ", r"^/(faq|faqs|frequently-asked|help|support)[^/]*/?$", 90),
    ("account", "Account", r"^/(my-account|account|login|sign-in)/?$", 95),
    ("legal", "Legal", r"^/(privacy|terms|shipping|returns)[^/]*/?$", 120),
]
DEFAULT_PRIORITY = 100

SKIP = re.compile(
    r"(\.(?:xml|json|css|js|png|jpe?g|gif|svg|webp|pdf|zip|ico|woff2?)$"
    r"|/wp-(?:admin|content|json|includes)/|/feed/?$|/comments/feed"
    r"|^/(?:wp-login|xmlrpc)|/page/\d+)", re.I)

# Taxonomy archives and plugin-generated URLs match the "article" and "category"
# shapes but are terrible comparison subjects — they're thin list pages, not real
# templates. Demote rather than skip, so they're still available if nothing else
# exists on the site.
DEMOTE = re.compile(
    r"(/sc_[a-z_]+/|/(?:tag|author|attachment|embed|amp|type|format|label)/"
    r"|/product-tag/|-\d+/$|/(?:page|paged)/"
    # Retired, duplicated or internal variants — real but not what a reviewer
    # wants to see representing a template.
    r"|legacy|deprecated|\bold\b|-copy|-backup|-temp|-draft|-test\b|hidden"
    r"|sample|placeholder|do-not-use|archive[sd]?-)", re.I)


def fetch(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw if binary else raw.decode("utf-8", "replace")


def host_key(netloc):
    """Host identity for same-site tests, ignoring a leading www.

    Sites canonicalise between the apex domain and the www subdomain and then
    emit the canonical host in every sitemap <loc>. Comparing raw netlocs means
    invoking this script with the non-canonical form rejects every candidate and
    reports "no overlap" — which reads as a broken site rather than a typo.
    """
    return netloc.lower().removeprefix("www.")


def normalize(href, base):
    """Turn any href into a same-site absolute path, or None if off-site/junk."""
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    absolute = urljoin(base, href)
    parts = urlparse(absolute)
    if parts.netloc and host_key(parts.netloc) != host_key(urlparse(base).netloc):
        return None
    path = parts.path or "/"
    if SKIP.search(path):
        return None
    if not path.endswith("/") and "." not in path.rsplit("/", 1)[-1]:
        path += "/"
    return path


def from_sitemap(base, budget=3000):
    """Walk sitemap.xml, following sitemap-index files one level deep."""
    found, queue, seen = set(), [], set()
    for candidate in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/sitemap-index.xml"):
        queue.append(base + candidate)
    while queue and len(found) < budget:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            body = fetch(url)
        except Exception:
            continue
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, re.I)
        is_index = "<sitemapindex" in body.lower()
        for loc in locs:
            if is_index:
                if len(seen) < 40:
                    queue.append(loc)
            else:
                p = normalize(loc, base)
                if p:
                    found.add(p)
    return found


def from_nav(base):
    try:
        html = fetch(base + "/")
    except Exception:
        return set()
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html)
    return {p for p in (normalize(h, base) for h in hrefs) if p}


def classify(path):
    for cat, label, pattern, prio in RULES:
        if re.match(pattern, path, re.I):
            return cat, label, prio
    depth = path.strip("/").count("/")
    return "page", "Page", DEFAULT_PRIORITY + depth


def title_for(path, label, seen_labels):
    if path == "/":
        return "Home"
    slug = path.strip("/").split("/")[-1] or "home"
    pretty = re.sub(r"[-_]+", " ", slug).strip().title()
    pretty = re.sub(r"\bFaq\b", "FAQ", pretty)
    if label in ("Product", "Article", "Category / Collection"):
        return f"{label} — {pretty}"
    if label in ("Page",) or label in seen_labels:
        return pretty
    return label


def check(base, path):
    """True only if the URL returns 200 *and* still serves that path.

    urlopen follows redirects silently, so a retired page that now 301s to the
    homepage would report 200. A relaunch is exactly where that happens, and the
    result is a comparison row whose after-side screenshot is the homepage under
    a misleading title — so compare the final URL too. Host canonicalisation
    (apex <-> www) is not a real move, hence host_key.
    """
    target = base + path

    def still_there(final):
        got, want = urlparse(final), urlparse(target)
        return (host_key(got.netloc) == host_key(want.netloc)
                and got.path.rstrip("/") == want.path.rstrip("/"))

    for method in ("HEAD", "GET"):
        req = urllib.request.Request(target, headers={"User-Agent": UA}, method=method)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.status == 200 and still_there(r.url)
        except urllib.error.HTTPError as e:
            # Plenty of servers and WAFs refuse HEAD outright. Retry once with
            # GET before concluding the page doesn't exist.
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return e.code == 200
        except Exception:
            # Refusal at the connection level — a reset socket or a timeout — is
            # the same story one layer down, and equally not evidence that the
            # page is missing. Only a failed GET settles it.
            if method == "HEAD":
                continue
            return False
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--limit", type=int, default=14)
    ap.add_argument("--out", default="")
    ap.add_argument("--max-per-category", type=int, default=2)
    args = ap.parse_args()

    before = args.before.rstrip("/")
    after = args.after.rstrip("/")

    sets = {}
    for name, base in (("before", before), ("after", after)):
        paths = from_sitemap(base) | from_nav(base)
        sets[name] = paths
        print(f"[discover] {name}: {len(paths)} candidate paths", file=sys.stderr)

    shared = sorted(sets["before"] & sets["after"])
    print(f"[discover] shared by both: {len(shared)}", file=sys.stderr)
    if not shared:
        print("[discover] WARNING: no overlap. URLs may have changed between "
              "the two sites — ask the user for a path list.", file=sys.stderr)

    scored = []
    for p in shared:
        cat, label, prio = classify(p)
        if DEMOTE.search(p):
            prio += 500
        # What counts as a good representative differs by template. For articles,
        # a descriptive multi-word slug means a real post rather than a stub or
        # archive. For products and marketing pages it's the reverse — the
        # flagship has the short clean URL and the long ones are variants.
        last = p.rstrip("/").rsplit("/", 1)[-1]
        words = min(len(re.findall(r"[a-z0-9]+", last)), 8)
        quality = -words if cat == "post" else words
        scored.append((prio, quality, len(p), p, cat, label))
    scored.sort()

    chosen, per_cat, tried, seen_labels = [], {}, {}, set()
    dead_streak = 0
    for prio, _, _, path, cat, label in scored:
        if len(chosen) >= args.limit:
            break
        # A host that blocks this IP fails every check. Because a failure no
        # longer spends the category budget, nothing else would stop us probing
        # every shared path at TIMEOUT seconds a piece, so bail once the pattern
        # is unmistakable — and say why, since the config comes out empty.
        if dead_streak >= DEAD_STREAK_LIMIT:
            print(f"[discover] {dead_streak} candidates in a row failed to verify — "
                  "the sites are probably blocking this IP, or the URLs changed "
                  "wholesale. Stopping; ask the user for a path list.", file=sys.stderr)
            break
        cap = 1 if cat in ("home", "shop", "blog", "cart", "checkout") else args.max_per_category
        if per_cat.get(cat, 0) >= cap:
            continue
        # Bound the probing per category as well as overall: the slot stays
        # unspent on failure, so without this a single dead category could
        # absorb the entire run on its own.
        if tried.get(cat, 0) >= cap * 3:
            continue
        tried[cat] = tried.get(cat, 0) + 1
        # Only verify the ones we intend to keep — HEAD-ing 300 URLs is wasteful.
        if not (check(before, path) and check(after, path)):
            print(f"[discover] skip {path} (not 200 on both)", file=sys.stderr)
            dead_streak += 1
            continue
        dead_streak = 0
        # Spend the category budget only once a path has actually resolved. The
        # capped categories (home, shop, blog, cart, checkout) allow exactly one
        # entry, so charging a dead URL would drop that template type entirely.
        per_cat[cat] = per_cat.get(cat, 0) + 1
        chosen.append({"path": path, "category": cat,
                       "title": title_for(path, label, seen_labels)})
        seen_labels.add(label)

    pages = []
    for i, c in enumerate(chosen, 1):
        stem = re.sub(r"[^a-z0-9]+", "-", c["path"].strip("/").lower()).strip("-") or "home"
        if len(stem) > 40:  # trim at a word boundary so filenames stay readable
            stem = stem[:40].rsplit("-", 1)[0]
        pages.append(OrderedDict([
            ("slug", f"{i:02d}-{stem}"),
            ("title", c["title"]),
            ("path", c["path"]),
            ("category", c["category"]),
        ]))

    config = OrderedDict([
        ("project", "Site launch comparison"),
        ("before", {"base": before, "label": "Before", "sublabel": ""}),
        ("after", {"base": after, "label": "After", "sublabel": ""}),
        ("viewports", [
            {"id": "desktop", "width": 1440, "height": 1000, "mobile": False},
            {"id": "mobile", "width": 390, "height": 844, "mobile": True},
        ]),
        ("out", "/tmp/shots"),
        ("pages", pages),
    ])

    text = json.dumps(config, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[discover] wrote {args.out} with {len(pages)} pages", file=sys.stderr)
        other = [p for p in shared if p not in {c["path"] for c in chosen}]
        print("[discover] other shared paths not selected (sample): "
              + ", ".join(other[:25]), file=sys.stderr)
    else:
        print(text)


main()
