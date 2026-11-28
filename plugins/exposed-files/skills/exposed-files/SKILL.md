---
name: exposed-files
description: Scan Team51 sites for database dumps, WordPress exports, backups, logs and CSV exports that anyone can download, explain what was found and how serious it is, and guide the cleanup. Use when asked to "scan a site for exposed files", "check for public backups / SQL dumps / exports", "run the exposed files scan", "check this site before launch or handover", "run the monthly exposed-files sweep", "what did the scan find", or to clean up files a scan found. Runs the team51 CLI's site:scan-exposed-files and site:quarantine-exposed-files commands; the commands do the scanning, this skill reads their output and decides what it means.
argument-hint: "<site> [more sites] | --fleet"
---

# Exposed files

The Team51 CLI finds the files; you interpret them. Never scan sites yourself over SSH or curl: the commands are the fixed, reviewed way to do it, and they handle credentials, both platforms and the edge cases below.

| Command | What it does | Writes to sites? |
|---|---|---|
| `team51 site:scan-exposed-files <site>...` | Lists candidate files under the web root, rates each one's risk, and asks for one byte of each over HTTPS to see whether it is public. | No |
| `team51 site:quarantine-exposed-files <site>...` | Downloads each public file, verifies the copy's SHA-256, deletes the file from the site, purges the edge cache and confirms it is gone. | **Yes** |

Both need the team51 CLI set up with 1Password unlocked. If a command stops with "1Password CLI timed out", ask the user to unlock 1Password and run it again. Connecting to a site rotates its SFTP password; that is normal for the CLI and does not affect anyone's access.

## 1. Scan

**One or a few sites** (the usual case). Ask for JSON so you can read it, and save it in a scratch folder, never in a repository:

```bash
team51 site:scan-exposed-files example.com --all --no-interaction \
  --export=<scratch>/example-scan.json --export-format=json
```

`--all` includes files that aren't public and those known to be harmless, so you can say what was ruled out. The terminal output also shows a one-line summary per site. The JSON is a list of objects with `Site ID`, `Site`, `Public`, `Risk`, `Type`, `Path`, `Size`, `Modified` and `Why`.

**The whole fleet** (the regular sweep; takes a few hours). Give it a dated ledger and report so the next sweep can be compared:

```bash
team51 site:scan-exposed-files --sites=production \
  --log=<scratch>/scan-YYYY-MM-ledger.jsonl --report=<scratch>/scan-YYYY-MM.csv --yes
```

If it stops, run the same command again: finished sites are skipped. The report has one row per site: `status` (`exposed`, `unconfirmed`, `present`, `clean`, `failed`), `public`, `public_high`, and the files in `public_files` and `other_files`, one per line as `<risk> <type>:<path> (<size>, <date>, <state>)`. Sites to look at are also in `scan-YYYY-MM-follow-up.csv`.

To compare with the last sweep, match sites by `id` and report what is new: sites newly `exposed`, and public files that weren't in the previous report.

## 2. Read the results

`Public` is `yes` (anyone can download it), `no`, `unconfirmed` (couldn't tell) or `skipped` (harmless, not checked). Only `yes` and `unconfirmed` need anything done.

**Risk**, as the command rates it from the path and type:

| Risk | What it usually is |
|---|---|
| `high` | Database dumps (`.sql.gz`, `.sql.zip`), WordPress exports (XML: authors' and commenters' emails, IPs, drafts), backup and migration archives, plugin exports and imports (WP All Export/Import, WP Migrate DB, WebToffee, Duplicator, WPvivid, BackUpWordPress), copies of `wp-config.php`, files whose names suggest lists of people |
| `medium` | Spreadsheets, files sent through forms (Gravity Forms and similar), renamed PHP files served as readable source |
| `low` | Logs, other media library files, archives with unknown contents |
| `harmless` | WP Rollback packages, demo content, Complianz vendor lists, Yoast sitemap copies, build logs |

The risk is a guess from the name. Say so when it matters: a "users" export may hold only ID numbers, and an innocently named CSV may hold a donor list. To know, see step 4.

**`Why` explains special cases.** Pass these on to the user:

- **"the plugin keeps writing new ones, so change its storage first"**: a backup plugin is still running. Deleting its files does nothing until its storage is moved off the site, or it's turned off in favour of the host's backups.
- **"media library file; may be linked from a post on purpose"**: check with the user or partner before removing it.
- **"file someone sent through a form"**: it belongs to a form entry. Removing it breaks the entry's link.
- **"the site answers every check with blocked (403)"** (or 428, 429...): the site's firewall or bot check refuses the requests, so nothing could be confirmed public. Don't report these as safe. The files exist on the server either way.
- **"its URL serves the site's own uploads folder instead"**: a leftover copy under a path like `old-site/wp-content/uploads/...` that isn't really reachable. Not public.

## 3. Report to the user

Lead with the answer: how many public files, how many high risk, and on which sites. Then a short table of the public files, high risk first, with what each one probably is and what to do. Leave out the harmless ones unless asked.

Paths can point at personal data, so don't paste them into public channels, GitHub issues or the CLI repository. Internal P2 posts and DMs to the people handling it are fine.

## 4. Clean up (only with the user's go-ahead)

The quarantine command deletes files from live sites. Suggest it; never run it without the user saying so for those sites. Always preview first:

```bash
team51 site:quarantine-exposed-files example.com --dry-run
team51 site:quarantine-exposed-files example.com --backup-dir="$HOME/exposed-files-quarantine"
```

- Naming the site scans it again and handles every public file except harmless ones. Narrow it with `--risk=high` or `--risk=high,medium`.
- To handle only some files, export the scan as CSV (`--all --export=<scratch>/example-scan.csv --export-format=csv`), keep only the rows to remove, and pass it with `--files=<csv>`. It needs the `Site ID` and `Path` columns. `Risk` is filtered by `--risk`, and rows whose `Public` is `no` or `skipped` are left alone. Don't pass the JSON export or a fleet report: neither is a list of files in this shape.
- `--download-only` copies without deleting, so the partner can decide first.
- The copies hold personal data. Keep `--backup-dir` on an encrypted disk and out of synced folders (iCloud, Dropbox, Google Drive). Every file is recorded in `<backup-dir>/manifest.jsonl`, and the run's report goes in the same folder.
- `still-served` after a delete usually means a cache. With "Cloudflare" in the message, the site has its own Cloudflare account: someone with access purges the URL, or it expires. Otherwise check again in a few minutes.
- Skip scheduled backup folders until the plugin's storage is changed, and media library or form files until the user or partner has agreed.

**To find out what a copy really holds,** inspect the local copy in a new, empty folder with a short Python script run with `python3 -I`, using the standard library only. Print counts and column names, **never values**: rows, distinct emails, phone numbers, IP addresses, columns that look personal (name, email, phone, address, birth date, donation, payment), and, in user exports, `user_pass` values that look like password hashes (`$P$`, `$wp$`, `$2y$`). For zips and `.gz`, read the entries as streams rather than extracting them.

## 5. When to escalate

Tell the user to raise it with security, not just clean it up, when a public file held any of:

- password hashes (`user_pass`) or a `wp-config.php` copy;
- customer, donor, member or order lists with contact details;
- data about children (youth sports, schools);
- health, financial or other special-category data.

Give security the site, file type, what was in it (counts and kinds of data, no values), how long it was public (the `Modified` date) and that a copy was kept.
