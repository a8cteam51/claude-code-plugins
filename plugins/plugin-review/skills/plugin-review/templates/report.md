# Plugin Security Review: {plugin_name}

**Date:** {date}
**Reviewed Version:** {version}
**Slug:** {slug}
**Reviewer:** Automated (Claude Code plugin-review skill v1.0.0)

---

## Summary

| Metric | Value |
|--------|-------|
| **Overall Risk** | **{LOW/MEDIUM/HIGH/CRITICAL}** |
| Active Installs | {active_installs} |
| WP.org Rating | {rating}/100 ({num_ratings} ratings) |
| Last Updated | {last_updated} ({days_ago} days ago) |
| Tested Up To | WordPress {tested} |
| Requires PHP | {requires_php} |
| Known CVEs | {cve_count} |
| PHPCS Findings | {phpcs_errors} errors, {phpcs_warnings} warnings |

## Risk Signals

### Maintenance & Popularity
{Analysis of update frequency, install count, ratings, author track record.}

### Support Forum Activity
{Analysis of recent support threads, resolution rate, any security-related complaints.}

### Compatibility
{WordPress version compatibility, PHP version requirements, any noted incompatibilities.}

### User Reviews
{Summary of notable themes from wp.org reviews. Highlight any security warnings, abandonment concerns, upselling/pricing complaints, compatibility issues, or other red flags. If reviews are uniformly positive with no concerns, say so briefly.}

### GitHub Repository
{If found: URL, stars, open issues, last push date, archived status, security-related issues, latest release vs wp.org version. If not found: "No public GitHub repository found."}

---

## Security Findings

### Critical
{Findings or "None."}

### High
{Findings or "None."}

### Medium
{Findings or "None."}

### Low / Informational
{Findings or "None."}

{Each finding should follow this format:}
{- **Title** — description of the issue}
{  - File: `filename.php:line_number`}
{  - Evidence: `relevant code snippet`}
{  - Found by: PHPCS / Grep scan / Manual review}
{  - Assessment: Analysis of actual risk — is this a true positive or false positive? What is the real-world impact?}

---

## Known Vulnerabilities

{List vulnerabilities from all sources checked, or "No known vulnerabilities found."}
{If WPScan was skipped, note: "WPScan was not checked (no API key). Coverage may be incomplete."}

{For WPScan findings:}
{- **{Title}** (WPScan ID: {id})}
{  - Type: {vuln_type}}
{  - CVE: {cve_id if available}}
{  - Fixed in: {version, or "NOT PATCHED"}}
{  - Assessment: Does this affect the current version?}

{For NVD findings:}
{- **CVE-YYYY-NNNNN** (CVSS score)}
{  - Description}
{  - Affected versions}
{  - Status: Patched in version X / Unpatched / Not applicable to current version}

---

## Files Reviewed

{List of files that were directly read and analyzed during manual review, with brief notes on what was checked.}

---

## Methodology

This review was performed by the plugin-review skill (v1.0.0) using:
- PHPCS with WordPress security sniffs
- Grep-based scanning for {pattern_count} vulnerability signatures
- WPScan vulnerability database {if checked: "({N} vulnerabilities found)" / if skipped: "(not checked — no API key)"}
- NVD CVE database lookup
- WordPress.org API metadata analysis
- Support forum RSS feed analysis
- GitHub repository analysis (issues, activity, releases)
- Manual code review of flagged files and key entry points (AJAX handlers, REST routes, form processors)

**Disclaimer:** This is an automated review. For HIGH or CRITICAL findings, manual verification by a security engineer is recommended. A LOW risk rating does not guarantee the absence of all vulnerabilities.

---

## Opinion

{Your honest, plain-spoken assessment of whether this plugin should be added to the Approved Plugins list. Write in first person. Consider the full picture — not just the raw risk rating, but the practical impact of findings given the plugin's scope, attack surface, and real-world usage. If the risk rating feels too harsh or too lenient for this specific plugin, say so and explain why. Be direct and specific about any caveats.}
