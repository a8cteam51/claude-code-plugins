---
description: Scan all configured font sources and refresh the local-font-sources catalog's index
---

# Scan font sources

Refresh `~/.claude/local-font-sources/index.json` against the current
state of every source in `~/.claude/local-font-sources/config.json`. Read
`${CLAUDE_PLUGIN_ROOT}/commands/font-reference/scanning.md` and follow it —
this command is the trigger, that file is the mechanics; do not duplicate
the procedure here.

Arguments (optional): `$ARGUMENTS` — `<name> <path>` to add or repoint a
single source in `config.json` before scanning (e.g. `default
/Users/allancole/Claude Projects/font-sources`). Omit to scan every
configured source as-is.

## Steps

1. Resolve sources: apply `$ARGUMENTS` if given, else read
   `config.json` as-is; if it's missing or still has the old single-key
   (`font_dir`) shape, migrate it to `{"sources": [...]}` in place. If
   there are no sources at all, ask once and write one named `default`.
2. Refuse to scan any source path under `~/Library/Mobile Documents/`
   (iCloud) or another live cloud-sync location — report that the
   collection needs to be copied to local disk first and stop, for that
   source only (other sources still scan).
3. Run the scan procedure from `${CLAUDE_PLUGIN_ROOT}/commands/font-reference/
   scanning.md` in full for every source: walk, parse, license-check, diff,
   update `index.json`, tagging each result with its source's `name`.
4. Report the delta only, broken out per source if more than one — new
   files, files flagged for reclassification, files now missing on disk,
   and updated totals by license status. Do not print the full index.

This command never classifies anything (no specimen rendering, no web
research) — it only updates `index.json`. Classification happens
on demand, through `/find-font` or through a real design task, per
`${CLAUDE_PLUGIN_ROOT}/commands/font-reference/classification.md`.
