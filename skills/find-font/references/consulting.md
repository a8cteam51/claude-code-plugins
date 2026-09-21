# Consulting the local font catalog

Read this at the one moment a design task actually needs a typeface —
this is not a workflow of its own, it's a lookup another process (usually
`consistent-high-quality-design`'s DEFINE step) performs in passing.

## Core rule

A local font file is not usable for design until it has a **point of
view**: what it looks like, what mood it carries, what license it ships
under, and what it's good for. Never hand a font to a design task on
filename alone. Either the catalog already has that point of view
(`status: classified` in `~/.claude/local-font-sources/catalog/`), or
classify the font before recommending it — see `classification.md`.

## When this applies at all

Only when no font has already been supplied or chosen for the project.
A project's own supplied font files or named licensed fonts are binding
and checked first, elsewhere, before this ever gets read — see
`consistent-high-quality-design`'s intake step. When a font is supplied,
this file, and the catalog it points at, should never be touched.

## 1. Search — one combined pool, not source-then-fallback

The local catalog is not a fallback and not a first choice — it's one of
two pools a typeface search draws from, the other being Google Fonts
(model knowledge, not a directory here).

1. Scan `~/.claude/local-font-sources/catalog/*.json` for
   `status: classified` families matching the need (mood words, use case,
   structural traits — see `classification.md` for the tag vocabulary),
   and gather Google Fonts candidates in the same pass. Weigh both sets
   together against the project's voice and pick on fit alone — a local
   font never gets a bonus for being local, and Google Fonts never gets
   one for being the default.
2. If nothing classified fits, look for plausible unscanned candidates in
   `~/.claude/local-font-sources/index.json` — match against the family
   name **and** its `bundled_description` where one exists (a foundry's
   own words are a far better signal than the name alone; see
   `classification.md`), then classify the top 2-3 candidates before
   deciding rather than dropping them from consideration. Most of the
   collection will have no `bundled_description` and nothing suggestive
   in the name either — that's expected, not a gap to force a match for.
3. Only OFL-confirmed fonts are eligible for anything that leaves the
   user's own machine (a shipped site, a shared deliverable). Unknown-
   license fonts may be used for internal exploration only — say so
   explicitly if one is used that way. License facts come from the
   catalog entry (`license` field) — never infer or assume.

## 2. Embed the chosen font

Picking a family isn't the end of the job — it has to actually render in
the deliverable:

1. Copy the chosen family's files (the catalog entry's `files`, resolved
   against its source's `path` in `config.json`) into the project.
2. Write the `@font-face` rule(s) — family name, each weight/style file,
   `font-display` as appropriate.
3. Verify it renders during the project's existing browser-validation
   step — don't assume a copied file plus a written rule is enough; check
   the page actually shows the intended font, not a silent fallback.

Google Fonts, by contrast, costs only a `<link>` — no copy, no embedding
step. That asymmetry is real and is exactly why a local font needs this
step spelled out here rather than assumed.

## 3. Report

State which family was chosen, which source it came from (a local source
`name`, or "Google Fonts"), and why (the one line: the tags or reasoning
that matched) — the same way a design process reports a visual thesis
rather than narrating the search. Any time an unknown-license font is
used, say so and where. Don't narrate scan or classification mechanics
unless something failed.
