---
name: find-font
description: Browse the local font catalog for a family matching a mood/use-case description, classifying candidates on demand
---

# Find font

Standalone browsing of the local font catalog, outside any design task —
"what do I have that's warm and editorial," "find me a technical
monospace," etc. Read `${CLAUDE_PLUGIN_ROOT}/skills/find-font/references/
consulting.md` and `${CLAUDE_PLUGIN_ROOT}/skills/find-font/references/
classification.md` and follow them; this skill is the trigger, those
files are the mechanics.

Arguments (required): `$ARGUMENTS` — a free-text mood/structure/use-case
description, e.g. `"warm editorial serif for body text"`.

## Steps

1. Read `~/.claude/local-font-sources/catalog/*.json` and match
   `status: classified` families against `$ARGUMENTS` on `structure`,
   `mood`, and `use_cases` (per `classification.md`'s tag vocabulary and
   matching guidance).
2. If nothing classified fits, scan `~/.claude/local-font-sources/
   index.json` for plausible unclassified families — matching on the
   family name **and** `bundled_description` where one exists, not name
   alone — and classify the top 2-3 before answering. Don't report
   "nothing found" when unclassified candidates exist; also don't force a
   match when nothing in the index is actually plausible.
3. Report the best match: family, source (`name` from `config.json`),
   license, and why (the matching tags/reasoning) — plus the runner-up if
   one exists.

This is a lookup, not a design decision — it doesn't copy files, write
`@font-face`, or touch any project. That embedding step only happens
inside a real design task; see `consulting.md`.
