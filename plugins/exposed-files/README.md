# exposed-files

Finds files on Team51 sites that anyone can download and that may hold private data: database dumps, WordPress exports, backups, logs and CSV exports. Then explains what was found and helps clean it up.

The scanning is done by the [team51 CLI](https://github.com/a8cteam51/team51-cli); this plugin's skill runs it and interprets the results.

## Requirements

- The team51 CLI, with 1Password unlocked.
- The `site:scan-exposed-files` and `site:quarantine-exposed-files` commands, added to the team51 CLI in a8cteam51/team51-cli#213.

## Use

Ask Claude, for example:

- "Scan example.com for exposed files."
- "Check this site for public backups before handover."
- "Run the exposed files sweep across production and compare it with last month's."
- "Clean up what the scan found on example.com." (Claude previews first and asks before deleting anything.)

## Install

```bash
/plugin marketplace add a8cteam51/claude-code-plugins
/plugin install exposed-files@a8cteam51-claude-code-plugins
```
