#!/usr/bin/env python3
"""Pull the migration-relevant sentences out of saved P2 posts.

    p2_extract.py <saved posts-text result.json> [more.json ...] [--extra "word|word"]

Project posts run to tens of thousands of words of support history. This prints
only sentences that mention things a migration cares about (DNS, registrar,
email, payments, earlier migrations, redesigns, access), each with its date
and author, so the context step can be done without reading everything.
It selects; it does not judge. Read the output and keep what matters.
"""
import json
import re
import sys

KEYWORDS = (r"dns|domain|registrar|name ?server|\bmx\b|spf|dkim|dmarc|proton|google workspace|gmail|titan|email|smtp|sendgrid|mailgun|mailchimp|"
            r"migrat|lift.and.shift|dreamhost|wp\.?com\b|wordpress\.com|wpcomstaging|atomic|pressable|"
            r"payment|square|woopay|stripe|paypal|braintree|shipstation|gateway|sandbox|"
            r"redesign|relaunch|launch|videopress|subscri|membership|donation|staging|deploy|github|"
            r"credential|1password|1pw|login|access|squarespace|directnic|godaddy|namecheap|cloudflare|"
            r"store admin|jetpack (complete|security|backup|search)|blog id|cron|webhook|api key|integration")


def main():
    args = sys.argv[1:]
    extra = None
    if "--extra" in args:
        i = args.index("--extra")
        extra = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        sys.exit(64)
    pattern = re.compile(KEYWORDS + ("|" + extra if extra else ""), re.I)
    for path in args:
        data = json.load(open(path))
        if data.get("unresolved_slugs"):
            print("not found: " + ", ".join(data["unresolved_slugs"]))
        for post in data.get("posts", []):
            comments = post.get("comments") or []
            print("\n== %s | %s | %s | %d comments" % (post.get("title"), (post.get("date") or "")[:10], post.get("link"), len(comments)))

            def emit(who, when, text):
                for sentence in re.split(r"(?<=[.!?])\s+|\n+", text or ""):
                    sentence = sentence.strip()
                    if len(sentence) > 25 and pattern.search(sentence):
                        print("  [%s %s] %s" % (when, who, sentence[:340]))

            emit("post", "", post.get("content_text"))
            for c in sorted(comments, key=lambda c: c.get("date", "")):
                emit((c.get("author") or {}).get("username", "?"), (c.get("date") or "")[:10], c.get("content_text"))


if __name__ == "__main__":
    main()
