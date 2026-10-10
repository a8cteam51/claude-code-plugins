---
name: migration-dns
version: 0.1.0
description: Handle the DNS side of moving a site from Pressable to WordPress.com - audit registrar, name servers and records, work out whether the partner's registrar access is needed, plan the cutover of site records, compare the old and new zones before switching name servers, and check propagation. Use this whenever a migration question is about DNS, domains, name servers, registrars, MX/SPF/DKIM/email records, TTLs, pointing a domain at the new site, or moving a DNS zone out of Pressable.
argument-hint: "<domain>"
---

# Migration DNS

Two separate DNS changes happen in a migration. Keep them apart.

1. **Cutover: repoint the site's own records** (apex and `www`) at
   WordPress.com, inside whatever zone is authoritative today. Fast, and
   rolled back by changing the records back.
2. **Zone move: host the zone somewhere else.** Zones hosted at Pressable move
   to WordPress.com DNS, because the Pressable site is going away. This
   carries every record - mail, verification, subdomains - and ends with a
   name server change at the registrar. It happens after cutover, without
   time pressure, and should change nothing a visitor can see.

Doing the cutover inside the existing zone first means the later name server
change is a no-op for the site.

## Setup

```bash
PLUGIN_DIR="<absolute path two levels above the directory holding this SKILL.md>"
S="$PLUGIN_DIR/scripts"; D="migrations/<domain>"
```

## Audit a domain

```bash
python3 "$S/dns_audit.py" <apex> --site-ips <source ip1>,<source ip2> --names <known subdomains> > "$D/dns-<apex>.json"
```

Read `case` and `access_required`:

| Registrar | DNS hosted at | What changes | Access needed |
|---|---|---|---|
| Automattic / WordPress.com | Pressable | Zone moves to WordPress.com; we switch name servers | Which WordPress.com account holds the domain |
| Automattic / WordPress.com | WordPress.com | Records change in place | None |
| Third party | Pressable | Zone moves to WordPress.com; name servers change at the registrar | **Partner's registrar login** |
| Third party | Third party | Site records change at that DNS host; no zone move | **Partner's DNS host login** |
| Third party | WordPress.com | Records change in place | None |

When partner access is needed, the migration is not scheduled until someone
with the login is confirmed and available for the window. Record it:

```bash
python3 "$S/state.py" --dir "$D" decide registrar_access.<apex> confirmed
python3 "$S/build_audit.py" --dir "$D"
```

**The audit cannot list a zone.** DNS has no "show everything" query, so the
script asks about common names and selectors. Treat its record list as a
floor. DKIM selectors in particular are arbitrary strings chosen by the mail
provider.

## Get the full zone

For a Pressable-hosted zone, export every record from Pressable: the API
(`GET /zones` then `GET /zones/{zone_id}/records`; the zone ID is on each
record returned by `mcp__team51__pressable_list_site_domains`) or the DNS tab
of the Pressable dashboard. The team51 CLI has no command for this yet. Save
the export as `$D/zone-export.json` or, as a BIND file, `$D/zone-export.txt`.

Check the export against the audit: every name the audit found must be in it.
If the audit found a name the export lacks, the export is incomplete.

## Cutover: repoint the site records

1. A day or more ahead, lower the TTL on the apex and `www` records to 300.
2. Attach the domain to the WordPress.com site as a connected domain. The
   dashboard shows the record values to use.
3. In the current DNS host, change only the apex and `www` records. Touch
   nothing else: not name servers, not MX, not TXT.
4. Check from several resolvers:

   ```bash
   for r in 1.1.1.1 8.8.8.8 9.9.9.9; do echo "$r: $(dig +short <domain> @$r | tr '\n' ' ') | www: $(dig +short www.<domain> @$r | tr '\n' ' ')"; done
   curl -sI https://<domain> | head -n 12
   ```

Rollback: put the old values back. With a 300-second TTL that takes minutes.

Where a subdomain in the same zone points at a different Pressable site (the
audit lists these under `points_at_other_wpcloud_site`), leave it alone at
cutover. It is a separate site with its own migration.

## Zone move: Pressable to WordPress.com

1. Import the zone: WordPress.com dashboard → Domains → the domain → DNS
   records → menu → **Import BIND file**. It accepts A, AAAA, CNAME, MX, SRV,
   TXT and NS, and errors when a record conflicts with one already there.
   Other record types (CAA, for example) are added by hand.
2. Compare the two zones by asking each set of name servers directly, before
   anything is switched:

   ```bash
   python3 "$S/dns_compare.py" <apex> --old ns1.openhostingservice.com --new ns1.wordpress.com --names-from "$D"
   ```

   It takes names from the audit files and from `zone-export.*`. Add
   `--ignore-site-records` only if the old zone has not yet been repointed.
3. When it reports `ZONES MATCH`, change the name servers at the registrar.
   For a third-party registrar this is the partner's login.
4. Afterwards:

   ```bash
   dig +short NS <apex>
   dig +short MX <apex>; dig +short TXT <apex>
   ```

   Ask the partner to confirm that email is arriving and sending.
5. Delete the Pressable zone only after the name servers have fully moved and
   mail is confirmed.

Do not change name servers while `dns_compare.py` shows differences. A missing
MX or DKIM record stops the partner's email, and nobody notices until mail
bounces.

## What to tell the user

For an audit: the case, whether partner access is needed and for what, the
mail provider, anything pointing at other sites, and that the record list is a
floor. For a cutover or zone move: the exact records or name servers changing,
who has to make the change, and the rollback.
