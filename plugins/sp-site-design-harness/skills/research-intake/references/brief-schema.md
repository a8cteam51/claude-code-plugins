# Brief Schema

Defines how raw input — in any format, or none at all — gets normalized into
`research/brief.md`. Read at Step 2 (Normalize) of `SKILL.md`, after the
Input Ledger (`ledger-schema.md`) has been built.

Adapted from `sp-design-system`'s `brand-extraction-schema.md`, with field
names changed to match this harness's brief shape (brand guidance, website
goals, content/copy, existing assets, things to avoid,
references/context) rather than that skill's WordPress-build-specific
DESIGN.md schema. The confidence-tagging mechanism (Explicit / Inferred /
Gap) is unchanged.

## Rule

Normalize into this schema before writing any brief prose. The schema is the
intermediate structure; `brief.md` is the output format. Do not skip straight
to writing brief prose without populating the fields below first.

## `brief.md` section order

1. Goals — what the site needs to accomplish, for whom
2. Audience
3. Brand guidance — identity, voice, palette, typography, any explicit rules
4. Content/copy — what exists, what's placeholder, what's missing
5. Existing assets — graphics, photography, fonts, an existing `theme.json`
   or codebase
6. Things to avoid — explicit negative constraints
7. References/context — reference URLs, moodboards, competitor sites,
   anything supplied as inspiration rather than as identity

Sections may be thin. A thin section is not an omitted one — every section
appears, even if every field in it is tagged `Gap`.

## Field-by-field extraction targets

For each field, capture **value**, **source** (where it came from), and
**confidence** (see below).

### Goals
- Primary purpose of the site / primary user action
- Success criteria, if stated (leads, sales, information, portfolio, etc.)
- Any stated timeline or launch constraint

### Audience
- Primary audience description
- Secondary audiences, if any
- Anything stated about how the audience finds or uses the site

### Brand guidance
- Brand personality/voice in 1–3 sentences (the "why," not just adjectives —
  push back on inputs that only say "modern" or "clean" with nothing else)
- Palette, if specified (hex or named colors, with role if stated)
- Typography, if specified (named fonts, supplied font files, or a stated
  typeface restriction)
- Logo/wordmark constraints, if any
- Any explicit brand rules ("never use drop shadows," "always sentence
  case")

### Content/copy
- Real copy supplied, and where (name the file/doc)
- Explicitly placeholder copy, marked as such
- Content inventory — what pages/sections are expected to exist

### Existing assets
- Graphics/imagery supplied (name each, or the ledger item covering them)
- Photography supplied
- Fonts supplied (file or named licensed font — see the note below)
- An existing `theme.json`, codebase, or live site to draw from

**A supplied font is binding, not a candidate.** If the project ships its
own font files or names a specific licensed font as supplied identity,
record it as `Explicit` and flag in `brief.md` that Phase 2's typeface search
should be skipped entirely for anything it covers.

### Things to avoid
- Explicit negative constraints from the brand source or the user directly
- Competitor aesthetics or patterns the user explicitly wants distance from

### References/context
- Reference URLs, and what principle each one was cited for (not "copy
  this," see the note below)
- Moodboard images
- Any stated industry/competitive context

**References are principles to extract, never layouts to copy.** Note *what*
about each reference was cited (density, tone, a particular pattern) rather
than just linking it — this is what Phase 2 actually needs to act on it.

## Confidence levels

Every extracted field gets one of three tags:

- **Explicit** — the source stated this directly (a hex code in a brand PDF,
  a sentence of prose naming a font, a line in a brief document).
- **Inferred** — reasonably deduced but not directly stated (e.g. "the
  screenshot shows a sans-serif font that looks like it could be X" — visual
  inference from an image always starts here, never at Explicit; a
  computed style pulled from a live URL is the same case).
- **Gap** — no information available at all.

**Inferred fields must be surfaced in the Step 3 gap-check round for
confirmation before being treated as settled.** `Gap` fields go through the
same round and, if still unresolved afterward, get one of the two fallback
outcomes described in `SKILL.md` Step 3 (a named team default, or an
explicit "Phase 2 will use creative judgment here" flag) — never silently
left blank.

## Handling by input format

**PDF brand guidelines** — extract text and any embedded color
swatches/hex values directly as Explicit. Brand PDFs are frequently
incomplete outside logo/color/primary type; expect heavy gaps elsewhere and
flag them as `Gap`, not `Inferred`.

**Plain text / prose (including what the user types directly in
conversation)** — parse explicit values (hex codes, named fonts, pixel
sizes) as `Explicit`. Descriptive language ("warm," "bold," "editorial")
supports the Brand guidance section's prose but does not by itself populate
a hard field like a hex value.

**JSON / token file** — map keys directly where they align with the schema
(highest-confidence format; treat direct key matches as `Explicit`). Any
schema field with no corresponding key is a `Gap`.

**Screenshot / moodboard image** — treat all visual reads (colors, fonts,
spacing impressions) as `Inferred`, never `Explicit`, regardless of how
confident the visual match seems. Surface for confirmation before treating
as settled. If multiple images conflict, do not average or guess — surface
the conflict at gap-check.

**Live URL / existing site** — same treatment as screenshot: computed
styles and visible layout are a starting point, not a final source. The
visible site may reflect years of drift, not the current stated brand.

**Existing codebase / `theme.json`** — treat as `Explicit` for any token
that maps directly (same logic as a JSON token file). Often the most
reliable non-PDF source when it exists.

**Nothing supplied at all** — every field is `Gap`. This is not a failure
state; see `SKILL.md`'s note that an empty `inputs/` folder is never a stop
condition. Proceed straight to Step 3's fallback logic for every field.
