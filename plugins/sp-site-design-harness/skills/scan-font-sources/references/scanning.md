# Scanning font sources

Read before running `/scan-font-sources`, and whenever a lookup misses a
font the user says is present.

## 1. Resolve the sources

Read `~/.claude/local-font-sources/config.json`: `{"sources": [{"name":
"...", "path": "..."}]}`. If the file is missing, or has the old single-
key shape (`{"font_dir": "..."}`), migrate it in place to one source named
`default` using that path, then continue — don't ask the user to re-enter
a path you already have.

If there are no sources at all, ask for a path once, name it `default`,
and write the config.

Never scan a path still under active cloud sync (iCloud, Dropbox, Google
Drive, OneDrive, etc.) — the user should point a source at a copy on local
disk specifically so scanning doesn't fight sync conflicts or on-demand-
download placeholder files. If a source's path resolves to a known
cloud-sync location (e.g. `~/Library/Mobile Documents/`, `~/Dropbox/`),
stop and say so rather than scanning it.

## 2. Walk each source directory

Process every entry in `sources` in turn; tag every result from that pass
with that source's `name`. Within a source: collect every file matching
`*.ttf`, `*.otf`, `*.ttc`, `*.woff`, `*.woff2`, skipping `.DS_Store` and
any dotfile. Whatever folder structure the source already uses is fine to
walk as-is — don't try to reorganize it; this only reads it.

For each file, compute a fast change-detection key: `mtime + size` is
enough (a full hash of thousands of font files is unnecessary I/O; use
`sha256` only if `mtime+size` ever proves to miss a real change).

## 3. Parse each font's own metadata

Prefer a real font-table read over guessing from the filename — foundries
are inconsistent about naming files, but the font's own `name` table is
authoritative.

- If `fonttools` is available (`python3 -c "import fontTools"`), use it
  to read the `name` table: nameID 1/16 (family), 2/17 (subfamily/style),
  8 or 9 (foundry/designer), 13 (license description), 14 (license URL).
- If not available, install it into a throwaway venv rather than the
  system Python (`python3 -m venv`, `pip install fonttools`), or fall
  back to filename parsing and mark that entry's `family_source:
  "filename"` so low-confidence parses are visible later.

Never fall back silently — a family name guessed from a filename like
`Some-Font-Bold-Italic.ttf` is a real source of bad catalog data if it's
indistinguishable from a verified one.

## 4. Bundled description and specimen detection

Free signal that costs no rendering, no research, and no judgment call —
read it, don't interpret it. For each family folder (the folder directly
containing that family's font files, before any `otf/`/`ttf`/`webfonts`
subfolder split):

- **Description text**: look for a `README`, `DESCRIPTION`, or `ABOUT`
  file (any common extension) in that folder. Skip anything that's a
  license file in disguise (`LICENSE*`, `OFL*`, `COPYRIGHT*`) — those are
  legal text, not descriptive. Strip markdown image/link syntax and take
  roughly the first 500 characters of remaining prose. Store verbatim, as
  `bundled_description` — don't summarize or tag it; that's classification's
  job, not scanning's.
- **Specimen image**: look recursively under that folder for image files
  (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`). Prefer one whose filename
  suggests it's a specimen/poster (`specimen`, `preview`, `poster`,
  `sample`, `github_`, `view-`, `all-`); otherwise take the largest image
  file found, since a tiny one is more likely an icon than an actual
  specimen. Store its path (relative to the source's own path) as
  `bundled_specimen`.

Both fields are `null` when nothing suitable exists in that folder — that
is a normal, common result, not a failure. This never touches `status` —
a family with rich bundled text and a specimen image is still
`unscanned` until something actually classifies it.

## 5. License detection

A font counts as **OFL confirmed** only when at least one of these holds:

- nameID 13/14 (license description/URL) contains "SIL Open Font
  License" or "OFL" or links to `scripts.sil.org/OFL`.
- Any file that looks like a license file (`OFL*`, `LICENSE*`,
  `COPYING*`, any extension) sits alongside the font file in the same
  folder, **and its contents** contain "SIL Open Font License" or a link
  to `scripts.sil.org/OFL` or `openfontlicense.org`. Check content, not
  just filename — foundries (FontStruct exports in particular) routinely
  ship the actual OFL text inside a generically-named `license.txt`, and
  a filename-only check misses those.

Otherwise, mark `license: "unknown"`. Never infer OFL from the file just
sitting in an OFL-labeled source, and never infer it from a license
filename alone without reading what's actually in it — not every font in
a directory is actually OFL, and not every "license.txt" says OFL either.

## 6. Diff against the existing index

For each file: new path → add with `status: "unscanned"` and its source
`name`. Existing path with an unchanged mtime+size → leave its `status`
alone (don't reset a `classified` entry back to `unscanned`). Existing
path with a changed mtime+size → keep `status`, but flag
`needs_reclassification: true` since the underlying file changed. Path in
the old index but no longer on disk → mark `missing_on_disk: true` rather
than deleting the entry outright; a temporarily unmounted cloud-sync path
or a mid-move shouldn't silently destroy classification work already done.

Re-check `bundled_description`/`bundled_specimen` for every family every
run, even when its font files' change keys are unchanged — a README or
preview image can be added to a folder independently of the font files
themselves, and re-checking costs nothing.

## 7. Report

State the delta, not the whole index: new files found, files flagged
`needs_reclassification`, files now `missing_on_disk`, the running
totals by license status, and how many families now have a
`bundled_description` and/or `bundled_specimen` — broken out per source
if there's more than one. If a source's scan touches a suspiciously small
number of files relative to what's expected, say so rather than treating
it as a normal result — it usually means the path is wrong or a cloud
sync hasn't finished downloading.
