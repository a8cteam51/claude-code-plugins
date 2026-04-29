# Automattic Special Projects Claude Code Plugins

Claude Code plugins built by [Automattic's Special Projects team](https://specialprojects.automattic.com/) for WordPress development, security, and client work.

## plugin-review

Automated WordPress plugin security review and risk assessment. Point it at any plugin slug, wordpress.org URL, or local plugin directory and get a structured report with an approve/conditional/reject recommendation.

**What's included:**

- **plugin-review skill** - Full security review workflow: static analysis, vulnerability database checks, manual code review, and risk rating

**What it checks:**

- PHPCS with WordPress security sniffs
- Grep-based scanning for 29 vulnerability signatures (PHP + JS)
- WPScan vulnerability database (optional, requires free API key)
- NVD CVE database
- WordPress.org metadata (installs, ratings, reviews, support forum)
- GitHub repository signals
- Manual code review of AJAX handlers, REST routes, shortcodes, file uploads

**Requirements:**

- PHP, Composer, PHPCS (auto-detected by dependency checker)
- `WPSCAN_API_TOKEN` environment variable (optional, for WPScan lookups — get a free key at https://wpscan.com/register)

```bash
# Install plugin review
/plugin install plugin-review@a8cteam51-claude-code-plugins

# Review a plugin by slug
/plugin-review akismet

# Review a plugin by URL
/plugin-review https://wordpress.org/plugins/contact-form-7/

# Review the plugin in the current directory
/plugin-review
```

## pr-feedback

Address unresolved PR review comments directly from Claude Code. Point it at any GitHub PR URL and it fetches open review threads, evaluates whether the feedback is valid, applies clear fixes automatically, and surfaces questionable feedback for your decision.

**What's included:**

- **pr-addr-feedback command** - Slash command that processes unresolved review threads one by one

**What it does:**

- Fetches unresolved review threads via GitHub GraphQL API
- Reads the relevant code context for each comment
- Evaluates whether feedback is technically valid or a style preference
- Applies valid fixes automatically with minimal changes
- Prompts you on questionable feedback before acting
- Prints a summary table of all actions taken

**Requirements:**

- `gh` CLI authenticated with access to the target repo

```bash
# Install pr-feedback
/plugin install pr-feedback@a8cteam51-claude-code-plugins

# Address feedback on a PR
/pr-addr-feedback https://github.com/org/repo/pull/123
```

## Install the Marketplace

Add this marketplace to Claude Code:

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
