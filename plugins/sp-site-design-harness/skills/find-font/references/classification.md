# Classifying a font family

Do this per family, on demand — never as an unprompted bulk pass over any
source (see `consulting.md`).

## 1. Render a specimen

First check `index.json` for that family's `bundled_specimen` — if the
foundry already shipped a specimen/poster image, look at that before
rendering your own; skip straight to step 2 if it's actually legible and
shows the family at more than one size. Only render one yourself when
`bundled_specimen` is `null` or turns out to be unusable (an icon, a
logo, not actually a type specimen).

Build a small local HTML page with an `@font-face` rule pointing at the
family's own file(s) via a `file://` path, then screenshot it with the
Browser tooling. Include, at minimum:

- The family name set at a large display size
- A pangram at a body-text size ("The quick brown fox jumps over the lazy
  dog" or similar) to see lowercase rhythm and x-height
- Numerals and a few punctuation marks (`0123456789 & ? ! @`)
- If more than one weight/style file exists for the family, one line per
  style so weight range is visible in one image

Save the screenshot to `~/.claude/local-font-sources/specimens/<family-
slug>.png`. Actually look at the rendered image before writing any
descriptor — do not classify from the family name alone.

If `file://` + Browser screenshot doesn't render the font (local
`file://` loads have been seen to silently fall back to a system font, or
fail outright above a small combined-file-size threshold, in at least one
environment — see this repo's DECISIONS.md), fall back to rendering the
specimen directly to PNG with Pillow (`ImageFont.truetype` + `ImageDraw`,
in a throwaway venv alongside fontTools) instead of narrating the failure
and stopping.

## 2. Web research

Start from `index.json`'s `bundled_description` for that family, if
present — foundries often state voice, inspiration, or intended use
directly (e.g. "a very heavy/fat font... inspired by bread, pastries and
sweets"), which is real evidence, not a guess, and can shortcut or
sharpen the web search below rather than replace it entirely.

Search the family name plus "font" or "typeface." Prioritize, in order:
the foundry's own specimen/description page, type-specimen sites (e.g.
Fonts In Use), and reviews or write-ups that describe voice/use case in
words. Pull:

- Foundry/designer name, release era if stated
- Descriptive language the foundry or reviewers actually use (prefer
  their words over inventing your own where they exist)
- Documented or commonly cited use cases and notable real-world uses
- Any pairing recommendations already published

Record every URL actually consulted in the entry's `provenance.sources`
— this is what makes a stale or wrong classification checkable later. If
`bundled_description` materially informed the tags, note that too (e.g.
`"bundled README"`) so it's clear the foundry's own words were used, not
just what turned up in a search.

## 3. Synthesize into tags

Combine the specimen read and the research into the schema below.
Where the specimen and the research disagree (foundry markets a font as
"friendly" but the specimen reads as quite formal), trust what's
actually on screen and note the discrepancy in a short internal comment
in `notes`, rather than silently picking one.

### Tag vocabulary (extend as needed, but stay consistent)

- **Structure**: serif · sans · slab · script · handwriting · display ·
  monospace · blackletter
- **Voice/mood**: geometric · humanist · grotesque · elegant · warm ·
  cold · brutalist · playful · technical · editorial · luxury ·
  utilitarian · vintage · futuristic · formal · casual
- **Use case**: display/headline · body text · UI/interface · editorial ·
  branding/logotype · code/mono · signage

## 4. Schema — `catalog/<family-slug>.json`

```json
{
  "family": "Example Serif",
  "slug": "example-serif",
  "source": "<name from config.json's sources this family came from>",
  "foundry": "Example Foundry",
  "files": ["<paths from index.json for this family, relative to its source's path>"],
  "weights": ["Regular", "Bold", "Italic"],
  "license": "ofl-confirmed",
  "structure": ["serif"],
  "mood": ["editorial", "warm"],
  "use_cases": ["body text", "editorial"],
  "pairs_well_with": ["Example Sans"],
  "notes": "one or two sentences, free text",
  "specimen": "specimens/example-serif.png",
  "provenance": {
    "sources": ["https://..."],
    "classified_date": "YYYY-MM-DD",
    "confidence": "high | medium | low"
  },
  "status": "classified"
}
```

`confidence: "low"` is for cases with thin or no web presence — obscure
or self-released fonts — where the entry is mostly specimen-derived.
That's fine; say so rather than inflating confidence.

## 5. Querying the catalog

Match on `structure`, `mood`, and `use_cases` against the actual need —
the same vocabulary a design brief would use ("something warm and
editorial for body text"), not exact-string matching against a single
tag. When several families fit, prefer higher `confidence` and note the
runner-up rather than silently discarding it. See `consulting.md` for how
this fits into a design task and how a chosen local font actually gets
into a deliverable.
