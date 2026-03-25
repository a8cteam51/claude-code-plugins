# Risk Rating Criteria

Use this rubric to assign an overall risk rating after reviewing all findings.

## Rating Levels

### LOW — Approve

Assign LOW when **all** of the following are true:
- No confirmed security vulnerabilities after manual review
- PHPCS/grep findings are false positives or informational only
- No unpatched CVEs affecting the current version
- Actively maintained (updated within the last 12 months)
- Reasonable adoption (1,000+ active installs OR the plugin is from a known author)
- Positive ratings (80%+ or very few ratings with no security complaints)
- Compatible with current WordPress and PHP versions
- Support forum shows no unresolved security-related threads

**Recommendation: APPROVE** — safe to install.

### MEDIUM — Conditional Approve

Assign MEDIUM when **any** of the following are true:
- Minor findings that are low-impact or require authentication to exploit (e.g., missing escaping in admin-only pages)
- Plugin has weak maintenance signals but code review is clean (e.g., not updated in 12-24 months)
- Low adoption (under 1,000 installs) with limited review data
- Historical CVEs that have been patched in the current version
- Some PHPCS findings that are technically violations but low risk in context
- Support forum has unresolved complaints but none are security-related

**Recommendation: CONDITIONAL APPROVE** — safe to install with noted caveats. List specific conditions or items to monitor.

### HIGH — Reject

Assign HIGH when **any** of the following are true:
- Confirmed security vulnerabilities, even if they require authentication to exploit
- Unpatched CVEs affecting the current version
- Abandoned (no updates in 2+ years) AND has any code quality concerns
- Obfuscated or encrypted code with no clear justification
- Direct database queries without prepared statements that could be reached via user input
- Missing nonce/capability checks on actions that modify data
- Support forum reports security issues that are unresolved
- Plugin loads external code at runtime (remote includes, eval of fetched content)

**Recommendation: REJECT** — do not install. List specific issues that must be resolved.

### CRITICAL — Reject Immediately

Assign CRITICAL when **any** of the following are true:
- Confirmed remote code execution (RCE) vulnerability
- Confirmed SQL injection reachable by unauthenticated users
- Backdoor or deliberately malicious code
- Known actively exploited vulnerability (check CVE details)
- Code that exfiltrates data to external servers
- Code that creates hidden admin accounts
- Multiple layers of obfuscation hiding functionality

**Recommendation: REJECT** — do not install. This plugin may be malicious.

## Balancing Signals

When signals conflict (e.g., clean code but abandoned), weight **code findings over metadata**:

1. **Code security** — most important. A well-coded plugin with low installs is safer than a popular plugin with vulnerabilities.
2. **Known CVEs** — second. Unpatched CVEs are concrete, documented risks.
3. **Maintenance status** — third. Abandoned plugins won't get patched when new vulnerabilities are discovered.
4. **Popularity/ratings** — least weight. Popular plugins can still have vulnerabilities, and new plugins may just be new.

## Special Cases

- **Brand new plugin** (< 1 month old, < 100 installs): Rate based on code quality alone. Note the limited track record.
- **Plugin by major company** (Automattic, Yoast, WP Engine, etc.): Same scrutiny on code, but maintenance risk is lower.
- **Plugin removed from wp.org**: Automatic HIGH minimum. Plugins are removed for violations.
- **Commercial/freemium plugin**: Check if the free version contains any license-enforcement code that has security implications.
