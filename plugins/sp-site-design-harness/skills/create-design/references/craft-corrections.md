# Craft Corrections — accumulated judgment

This is a living log of specific moments where a finished design passed every
gate and still read as broken, accidental, or unintentional to a trained eye —
not because it failed a rule, but because it failed to *register as a choice*.

This file is not a checklist. Nothing here is mechanically checkable, and
nothing here should be turned into one. Each entry exists to sharpen judgment
during the critique and craft passes, the way a designer's own accumulated
experience would. Skim it, hold the principles loosely, and ask whether the
*reasoning* in any entry applies to what you're looking at — never grep the
current design for the literal originating detail.

**Read this before:** the critic pass (`critique.md`) and the craft pass
(`polish.md`, DELIVER step 6). Consult it again during the final polish gate
(Gate 5).

## Entry format

Each entry has four fields. Keep entries short — a paragraph, not a page.

- **Symptom observed** — the concrete instance, specific enough to picture.
- **Why it read as unintentional** — the perceptual reasoning: what made a
  human read "mistake" instead of "choice."
- **Generalized principle** — the takeaway, deliberately abstracted away from
  the specific CSS property, component, or breakpoint involved. This is the
  field that has to generalize, or the entry doesn't belong in this file.
- **Not a rule because** — one line naming a plausible case where following
  the specific fix literally would be wrong. This is what keeps the log from
  hardening into mechanical rules over time.

## Log

### CC-001 — Added 2026-09-17

- **Symptom observed:** A fixed/sticky header had a 1px top border sitting
  flush against the very top of the viewport with zero gap above it. On
  scroll, it read as a rendering glitch or a misplaced stray line rather than
  a deliberate border.
- **Why it read as unintentional:** A thin line with nothing above or around
  it to give it context has no way to signal "this is placed here on
  purpose." The eye needs some breathing room, contrast, or surrounding
  structure to distinguish "deliberate edge" from "artifact of the render."
- **Generalized principle:** Thin or subtle edge elements — borders, rules,
  hairlines, faint shadows — placed flush against a viewport or container
  boundary with no surrounding space or context can read as an accidental
  rendering artifact rather than an intentional design choice. Give them
  enough spatial separation, contrast, or compositional context to register
  as deliberate.
- **Not a rule because:** Plenty of intentional designs *do* run a rule flush
  to an edge on purpose (e.g., a full-bleed underline used as a strong
  compositional device) — the fix isn't "always add a gap above top borders,"
  it's "ask whether this edge reads as chosen," which depends on the
  surrounding composition.

### CC-002 — Added 2026-09-17

- **Symptom observed:** A vertical sidebar nav with rotated text labels had
  thin horizontal rule lines positioned close to each label. Instead of
  reading as separators between nav items, they looked like broken or
  misplaced underlines — as if a text-decoration had leaked or misaligned.
- **Why it read as unintentional:** Rotated text sitting near a short rule
  line pattern-matches to "underlined text" before it pattern-matches to
  "list divider." Without consistent spacing, equal-length treatment, or a
  clear grid relationship to the items they're supposedly separating, the
  lines don't signal "structural divider" — they signal "stray line
  associated with that specific word."
- **Generalized principle:** Thin rule lines used as separators next to text
  (especially rotated or otherwise non-standard text orientation) need
  enough visual distinction from text-decoration conventions — spacing,
  consistent length/alignment to a grid, or clear separation from the text
  baseline — or the eye will read them as a broken/accidental underline
  rather than an intentional layout device.
- **Not a rule because:** Vertical dividers between nav items are a
  legitimate, common device (especially in editorial/gallery-style layouts)
  — the failure mode here is proximity/alignment ambiguity with underline
  conventions, not the presence of rules themselves.

### CC-003 — Added 2026-09-17

- **Symptom observed:** A two-column numbered list (item 02, item 03) had the
  left column left-aligned with a divider rule on its left, but the right
  column was right-aligned with body text ragging left — so both columns'
  ragged edges pointed inward at each other across the gutter, instead of
  matching alignment/divider treatment.
- **Why it read as unintentional:** Repeated items in a list are expected to
  share the same structural logic (alignment, divider placement, rag
  direction) so the eye can parse them as instances of one pattern. Mirroring
  only the text alignment — while the divider, numeral, and heading
  positioning don't mirror along with it — breaks that shared logic. The two
  rags pointing at each other reads like a copy-paste/RTL mistake rather than
  a deliberate symmetric composition.
- **Generalized principle:** In a repeated set of items (cards, list entries,
  columns), keep alignment and rag direction consistent across instances
  unless full mirroring is applied systemically to *every* structural
  element (divider, numeral, heading, spacing) — partial mirroring, where
  only body-text alignment flips, reads as broken rather than intentional.
- **Not a rule because:** Deliberate mirrored/facing-page layouts are a
  legitimate device (e.g., a true symmetric spread where both dividers,
  numerals, and headings mirror too) — the failure isn't rag-pointing-inward
  per se, it's applying that mirroring inconsistently to only one element of
  the pattern.

<!-- Append new entries below this line, oldest first, sequential IDs. -->

## Adding a new entry

This is a lightweight, conversational process — it does not require a new
skill or command.

When a designer flags something post-hoc (a screenshot plus "this looks
wrong" or similar), do the following inline:

1. **Capture the specific instance** — what they saw, and what about it read
   as wrong, in their words.
2. **Ask yourself explicitly:** "What is the general perceptual or design
   principle here — not just the specific CSS property, component, or
   breakpoint involved?" Do not stop at the literal fix (e.g., "add 8px of
   margin"). Push to the level of *why the eye reads this as an accident*.
3. **Draft the entry** using the four fields above. If you're unsure whether
   the principle is generalized enough (or too generalized to be useful), say
   so to the user and ask.
4. **Append it** to the bottom of the Log section with the next sequential
   `CC-NNN` ID and today's date.

## Maintenance

If this log grows past roughly 20-25 entries, do a consolidation pass before
adding more:

- Merge entries that express the same underlying principle from different
  instances.
- Promote any principle that has proven stable and broadly true across many
  instances into the prose of `polish.md` or `critique.md` directly, and
  remove it from this log — this file is for accumulating and testing
  judgment, not a permanent archive.
- Retire entries that, on reflection, were too narrow or turned out to be
  one-off preferences rather than a general principle.
