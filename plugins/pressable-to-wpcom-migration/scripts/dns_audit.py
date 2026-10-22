#!/usr/bin/env python3
"""Snapshot a domain's public DNS and registrar for the migration audit.

    dns_audit.py example.com [--names extra1,extra2] [--site-ips 199.16.172.1,...]

Prints JSON. Uses `dig` and `whois`. It can only see names it asks for: DNS has
no "list everything" query, so the record list is a floor, not the full zone.
The full zone comes from the DNS host's own export.
"""
import argparse
import json
import re
import subprocess
import sys

PRESSABLE_NS = "openhostingservice.com"
WPCOM_NS = ("wordpress.com", "wordpress.net", "wordpress.org")
AUTOMATTIC_REGISTRARS = ("automattic", "wordpress.com", "sawbuck")
# Pressable and WordPress.com both sit on WP Cloud address space.
WPCLOUD_PREFIXES = ("199.16.172.", "199.16.173.", "192.0.78.", "192.0.79.")

COMMON_SUBDOMAINS = [
    "www", "mail", "webmail", "email", "smtp", "imap", "pop", "autodiscover", "autoconfig",
    "shop", "store", "blog", "app", "api", "cdn", "static", "assets", "media", "files",
    "staging", "stage", "dev", "test", "beta", "old", "new", "portal", "members", "community",
    "help", "support", "docs", "status", "go", "link", "links", "click", "track", "em",
    "newsletter", "news", "events", "learn", "courses", "archive", "donate", "pay", "billing",
    "ftp", "cpanel", "calendar", "drive", "sites", "lyncdiscover", "sip", "enterpriseregistration",
    "enterpriseenrollment", "msoid", "m", "mobile", "video", "podcast", "forum", "wiki",
]
DKIM_SELECTORS = [
    "google", "default", "selector1", "selector2", "k1", "k2", "k3", "s1", "s2", "mail", "dkim",
    "protonmail", "protonmail2", "protonmail3", "mx", "smtp", "mandrill", "mailjet", "sendgrid",
    "sg", "pm", "postmark", "zoho", "fm1", "fm2", "fm3", "mte1", "mte2", "krs", "cm", "klaviyo",
    "kl", "kl2", "mailo", "amazonses", "ses", "titan1", "titan2", "wpcloud1", "wpcloud2", "hs1", "hs2",
]
SERVICE_NAMES = ["_dmarc", "_mta-sts", "_smtp._tls", "_domainconnect", "_acme-challenge", "_github-pages-challenge"]


def dig(name, rtype, server=None):
    cmd = ["dig", "+short", "+time=3", "+tries=1", rtype, name]
    if server:
        cmd.insert(1, "@" + server)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=12).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
    return [line.strip() for line in out.splitlines() if line.strip() and not line.startswith(";")]


def whois(domain):
    try:
        out = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=25).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return {"error": "whois unavailable"}
    def first(pattern):
        m = re.search(pattern, out, re.I | re.M)
        return m.group(1).strip() if m else None
    return {
        "registrar": first(r"^\s*Registrar:\s*(.+)$"),
        "registrar_url": first(r"^\s*Registrar URL:\s*(.+)$"),
        "expires": first(r"^\s*(?:Registry Expiry Date|Registrar Registration Expiration Date|Expiry Date):\s*(.+)$"),
        "status": sorted(set(re.findall(r"^\s*Domain Status:\s*(\S+)", out, re.I | re.M)))[:6],
        "name_servers": sorted(set(n.lower().rstrip(".") for n in re.findall(r"^\s*Name Server:\s*(\S+)", out, re.I | re.M))),
    }


def apex_of(domain):
    """Naive registrable-domain guess; good enough for two-level public suffixes we see."""
    parts = domain.lower().strip(".").split(".")
    two_level = {"co.uk", "org.uk", "com.au", "co.nz", "com.br", "co.za", "com.mx", "co.jp", "org.au", "net.au"}
    if len(parts) >= 3 and ".".join(parts[-2:]) in two_level:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def classify_ns(nameservers):
    joined = " ".join(nameservers).lower()
    if PRESSABLE_NS in joined:
        return "pressable"
    if any(("ns%d.%s" % (i, d)) in joined for d in WPCOM_NS for i in range(1, 5)):
        return "wpcom"
    return "third-party" if nameservers else "unknown"


def classify_registrar(name):
    if not name:
        return "unknown"
    low = name.lower()
    return "automattic" if any(k in low for k in AUTOMATTIC_REGISTRARS) else "third-party"


def records_for(name, server, types=("A", "AAAA", "CNAME", "MX", "TXT")):
    found = {}
    cname = dig(name, "CNAME", server)
    if cname:
        return {"CNAME": cname}
    for rtype in types:
        if rtype == "CNAME":
            continue
        values = dig(name, rtype, server)
        if values:
            found[rtype] = sorted(values)
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domain")
    ap.add_argument("--names", default="", help="extra hostnames or labels to query, comma separated")
    ap.add_argument("--site-ips", default="", help="the source site's IPs, comma separated")
    args = ap.parse_args()

    domain = args.domain.lower().strip(".")
    apex = apex_of(domain)
    site_ips = set(filter(None, args.site_ips.split(",")))

    ns = sorted(n.lower().rstrip(".") for n in dig(apex, "NS"))
    authoritative = ns[0] if ns else None
    who = whois(apex)
    ns_host = classify_ns(ns)
    registrar_class = classify_registrar(who.get("registrar"))

    names = {apex: None, "www." + apex: None}
    for label in COMMON_SUBDOMAINS + SERVICE_NAMES + [s + "._domainkey" for s in DKIM_SELECTORS]:
        names[label + "." + apex] = None
    for extra in filter(None, args.names.split(",")):
        extra = extra.strip().lower().rstrip(".")
        names[extra if extra.endswith(apex) else extra + "." + apex] = None

    # A wildcard answers for every name; detect it so the guesses below are not all "found".
    wildcard = records_for("t51-wildcard-probe-zz9." + apex, authoritative, types=("A", "CNAME"))

    records = {}
    for name in names:
        types = ("A", "AAAA", "CNAME", "MX", "TXT", "CAA", "SRV") if name == apex else ("A", "AAAA", "CNAME", "MX", "TXT")
        rec = records_for(name, authoritative, types)
        if not rec or (name not in (apex, "www." + apex) and wildcard and rec == wildcard):
            continue
        records[name] = rec

    def points_at_site(rec):
        ips = set(rec.get("A", []))
        if site_ips:
            return bool(ips & site_ips)
        return any(ip.startswith(WPCLOUD_PREFIXES) for ip in ips)

    site_records, other_wpcloud, mail_records, verification, other = [], [], [], [], []
    for name, rec in records.items():
        if rec.get("MX") or "_domainkey" in name or name.startswith(("_dmarc", "_mta-sts", "_smtp._tls")):
            mail_records.append(name)
        for txt in rec.get("TXT", []):
            low = txt.lower()
            if "v=spf1" in low and name not in mail_records:
                mail_records.append(name)
            if any(k in low for k in ("verification", "verify", "atomic-domain", "ms=", "apple-domain", "stripe-", "klaviyo", "docusign", "atlassian")):
                verification.append({"name": name, "txt": txt[:120]})
        if rec.get("A") or rec.get("CNAME"):
            if points_at_site(rec):
                site_records.append(name)
            elif any(ip.startswith(WPCLOUD_PREFIXES) for ip in rec.get("A", [])):
                other_wpcloud.append(name)
            elif name not in (apex, "www." + apex):
                other.append(name)

    if ns_host == "pressable" and registrar_class == "automattic":
        case, access = "automattic-registrar/pressable-dns", "none: find which WordPress.com account holds the domain"
    elif ns_host == "pressable":
        case, access = "third-party-registrar/pressable-dns", "partner registrar login needed to change name servers"
    elif ns_host == "wpcom":
        case, access = "wpcom-dns", "none"
    elif ns_host == "third-party":
        case, access = "third-party-dns", "partner DNS host login needed to repoint site records"
    else:
        case, access = "unknown", "could not read name servers"

    result = {
        "domain": domain,
        "apex": apex,
        "registrar": who,
        "registrar_class": registrar_class,
        "name_servers": ns,
        "dns_host": ns_host,
        "case": case,
        "access_required": access,
        "access_needed_from_partner": case in ("third-party-registrar/pressable-dns", "third-party-dns"),
        "soa": dig(apex, "SOA", authoritative),
        "wildcard": wildcard or None,
        "records": records,
        "site_records": sorted(site_records),
        "points_at_other_wpcloud_site": sorted(other_wpcloud),
        "mail_related": sorted(set(mail_records)),
        "verification_txt": verification,
        "other_hosts": sorted(other),
        "mail_provider_hint": mail_hint(records.get(apex, {}).get("MX", [])),
        "coverage_note": "Guessed names only. Export the zone from the DNS host for the complete record set.",
    }
    json.dump(result, sys.stdout, indent=2)
    print()


def mail_hint(mx):
    joined = " ".join(mx).lower()
    for needle, label in (("google", "Google Workspace"), ("protonmail", "Proton Mail"), ("outlook", "Microsoft 365"), ("titan", "Titan"), ("zoho", "Zoho"), ("mailgun", "Mailgun"), ("fastmail", "Fastmail"), ("secureserver", "GoDaddy"), ("wordpress.com", "WordPress.com email forwarding")):
        if needle in joined:
            return label
    return "none" if not mx else "other"


if __name__ == "__main__":
    main()
