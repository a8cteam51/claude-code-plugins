# Plugin Review Skill

## Project Overview

A Claude Code skill that automates WordPress plugin security review and risk assessment. Replaces the current manual process where Technical Account Managers open issues for Engineers to review plugins not on an "Approved Plugins" list.

### Usage

```
/plugin-review akismet
/plugin-review https://wordpress.org/plugins/contact-form-7/
/plugin-review                  # reviews the plugin in the current working directory
```

### What This Skill Does

1. **Downloads plugin** via WordPress.org API (zip download + metadata)
2. **Static Code Analysis** — PHPCS with WordPress security sniffs + grep-based vulnerability pattern scanning
3. **Manual Code Review** — Claude reads flagged files and high-risk entry points (AJAX handlers, REST routes, etc.)
4. **Risk Signal Assessment** — Update history, install count, ratings, support forum activity, compatibility
5. **Vulnerability Database Check** — NVD CVE database lookup
6. **Risk Report** — Structured assessment with approve/conditional/reject recommendation

### Target Users

- **Technical Account Managers** — Trigger reviews when clients request new plugins
- **Engineers** — Review flagged findings, handle edge cases

## Dependencies (auto-installed by check-deps.sh)

- curl, unzip (pre-installed on macOS/Linux)
- jq (`brew install jq`)
- PHP (`brew install php`)
- PHPCS + WordPress standards (`composer global require squizlabs/php_codesniffer wp-coding-standards/wpcs dealerdirect/phpcodesniffer-composer-installer`)

## Project Structure

```
plugin-review-skill/
├── CLAUDE.md                     # This file
├── skill.md                      # Skill definition
├── lib/
│   ├── check-deps.sh             # Verify/install required dependencies
│   ├── fetch-plugin.sh           # Download zip + wp.org API + support RSS
│   ├── static-analysis.sh        # PHPCS security sniffs + grep patterns (PHP + JS)
│   ├── vuln-check.sh             # NVD CVE database lookup
│   └── github-check.sh           # Find and analyze GitHub repository
├── references/
│   ├── security-patterns.md      # Manual code review guide for Claude
│   └── rating-criteria.md        # Risk rating rubric (LOW/MEDIUM/HIGH/CRITICAL)
└── templates/
    └── report.md                 # Report output template
```

## Development Guidelines

- Keep the skill focused: input is a plugin identifier, output is a risk report
- Prefer conservative risk ratings — false positives are better than missed vulnerabilities
- All network calls should handle timeouts and missing data gracefully
- Plugin source is downloaded to `/tmp/plugin-review-{slug}/` and cleaned up after
- Reports are saved to `/tmp/plugin-review-{slug}-{date}.md`
- Never execute plugin PHP code — only read and analyze
- Reports should be actionable — specific file:line references, not vague warnings

## WordPress.org Plugin API

- Plugin info: `https://api.wordpress.org/plugins/info/1.2/?action=plugin_information&slug={slug}`
- Plugin zip: extracted from API response `download_link` field
- Support forum RSS: `https://wordpress.org/support/plugin/{slug}/feed/`
