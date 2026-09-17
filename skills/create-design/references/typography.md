# Typography — search and embedding

Read at DEFINE step 2, when deriving the type hierarchy and personality.

## Skip this entirely if a font was supplied

If intake recorded a project-supplied font (`references/intake.md`), the
typeface decision is already made and binding. Do not read further, do not
search, do not touch the local catalog — this file has nothing to add in
that case.

## Otherwise: one combined search

Weigh two pools together on fit to the visual thesis and voice — neither
gets a bonus:

- **Google Fonts** — model knowledge, no directory involved.
- **The local catalog** at `~/.claude/local-font-sources/catalog/*.json`,
  if that path exists on this machine. Match `status: classified` families
  against the need (mood, structure, use case — see that skill's
  `classification.md` for the tag vocabulary and `consulting.md` for the
  full search/report procedure). If nothing classified fits but a plausible
  unclassified family exists in `~/.claude/local-font-sources/index.json`,
  classify the top 2-3 candidates before deciding rather than dropping them.

If `~/.claude/local-font-sources/` doesn't exist on this machine, Google
Fonts is simply the only pool — don't treat that as a gap to fill.

## Embedding (the step that actually ships the choice)

Google Fonts costs a `<link>`. A local family costs more, and skipping this
is why a chosen local font has previously not made it into a deliverable:

1. Copy the chosen family's font files into the project (paths come from
   the catalog entry's `files`, resolved against its source's path).
2. Write the `@font-face` rule(s) for each weight/style actually used.
3. Verify it renders during DELIVER's browser-validation step — check the
   page actually shows the intended font, not a silent system-font
   fallback.

**License gate, not a suggestion:** only a family with
`license: "ofl-confirmed"` in its catalog entry may ship in anything that
leaves the machine. `license: "unknown"` is internal exploration only —
say so out loud if one is used that way, and swap it before delivery.
License facts come from the catalog entry directly; never infer or assume
a license from where a file happens to sit.

## Report

One line: family, source (a local source name, or "Google Fonts"), and why
— the same way a visual thesis gets stated rather than narrated into
existence.
