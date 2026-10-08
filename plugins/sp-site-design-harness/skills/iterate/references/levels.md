# Classifying a request

Read this only when the level isn't obvious from the request. When it's
borderline, pick the **lower** level and say so. Escalating after a quick
attempt costs less than running the heavier path for nothing.

## Examples

| Request | Level | Why |
|---|---|---|
| "Swap the border color to `--stone`" | L0 | One token, named by the user |
| "The CTA copy should say 'Book a visit'" | L0 | Copy only |
| "Headings feel a bit big" | L0 | Adjust the type-scale tokens, don't restructure |
| "Make the accent warmer" | L0 | One palette value (then check contrast) |
| "More breathing room between sections" | L0 | Spacing token or one section-gap rule |
| "The hero feels cramped on mobile" | L1 | One section, responsive behavior, needs a screenshot |
| "Cards should feel less boxy" | L1 | One component's treatment |
| "Can the nav be sticky?" | L1 | Behavior change, needs a sticky/scroll check |
| "Add a testimonials section" | L1 | New section inside the existing design language |
| "Swap the display typeface" | L1 | One token, but it reflows every heading, so take a screenshot |
| "It feels too corporate" | L2, unless it points at something specific | Emotional-target miss means the concept is off |
| "Combine option 1's layout with option 3's colors" | L2 | A new direction |
| "None of these are right" | L2 | Back to DISCOVER |

## Signals

- **L0:** the user names a variable, selector, value, or exact copy; the change
  doesn't move layout.
- **L1:** the change moves layout or behavior but stays inside one section or
  component, and the visual thesis still holds.
- **L2:** the feedback is about identity, mood, or concept, or it touches the
  whole page's structure.

A vague note can still be L0/L1. Turn it into a written principle first, as
`create-design` DISCOVER 4 describes ("too heavy" → "reduce border and rule
weight"), then apply the principle at the lowest level that satisfies it.

## Theme phase specifics

- L0 in a theme: `theme.json` `settings.color.palette`, `settings.typography`,
  `settings.spacing`, or a `styles.elements` / `styles.blocks` value; or a
  literal string in a pattern.
- L1 in a theme: edit one pattern or template part (`patterns/*.php`,
  `parts/*.html`, `templates/*.html`). If WordPress Studio tools are available,
  use them to screenshot the affected page and to validate block markup after
  editing.
- Never hand-write hex values into block markup when a preset exists. Use the
  preset slug (`var:preset|color|border` / `has-border-color`).
