# Craft, Responsive, and Accessibility Passes

Run all three. Screenshot to verify — do not assess from source.

## 1. Craft polish

Before this pass, skim `references/craft-corrections.md` — a living log of
specific past instances where a finished design read as accidental rather
than deliberate. Ask whether the *reasoning* in any entry applies to what
you're looking at now, not whether the literal originating detail recurs.

**Typography**
- Intentional font choice, not a default stack by accident. If the
  project supplies its own fonts, that choice is already made and final —
  don't reconsider it here. Otherwise, if `~/.claude/local-font-sources/`
  is present, its catalog and Google Fonts are one combined candidate
  pool (see `references/typography.md`): re-check that the chosen font is
  still the best fit for the voice among both, not just a Google Fonts
  default that went unquestioned.
- Appropriate weights; no faux bold/italic
- Line length (~45-75 characters for body)
- Leading and letter-spacing tuned per size, not globally
- Clear hierarchy; optical rather than mathematical balance
- Check wrapping, widows, orphans, and hyphenation at each breakpoint
- Consistent alignment; no drifting optical edges

**Spacing**
- Section rhythm reads as intentional
- Related elements grouped tighter than unrelated ones
- Consistent spacing for repeated components
- Exceptions exist on purpose, and you can say why
- Edge alignment holds across sections
- Every border, rule and container earns its place; delete any that separates
  what space already separates
- No rule or border crowding the text it encloses
- Content never touches the edge of a bounded/colored container — interior
  padding is present on every side, even when the container's background
  differs from the page background

**Composition**
- Visual balance and clear focal point per view
- Negative space used deliberately, not left over
- Tension or asymmetry where the concept calls for it
- Sections relate to each other rather than sitting as independent bands

**Color**
- Clear hierarchy; contrast supports it
- Restraint: count the colors actually in use
- Semantic meanings consistent (error, success, interactive)
- Palette consistent with the stated conceptual reason

**Images**
- Crop, alignment, scaling, resolution (check at 2x)
- Integrated with the layout, not floated on top of it

**Components** — verify every state: default, hover, focus, active, selected,
disabled, loading, empty, error.

**Motion**
- Easing and duration match the motion language
- Continuity between states
- Sensible interruption behavior (does it cancel cleanly?)
- Reduced-motion path tested

## 2. Responsive pass

Do not simply stack desktop sections vertically. Evaluate every major
composition at:

- Wide desktop
- Laptop
- Tablet
- Small mobile

Preserve the design idea at each breakpoint. Recompose where stacking would
destroy it — a composition whose premise is asymmetry should not become a
centered column on mobile.

Also check: reflow at 320px, long content, short content, and orientation change.

## 3. Accessibility

Decided throughout the design process, not added afterward. Verify:

- Semantic structure (landmarks, heading order, lists, tables)
- Full keyboard navigation, sensible tab order, no traps
- Visible focus indicator with sufficient contrast
- Color contrast: 4.5:1 body text, 3:1 large text and UI boundaries
- Target sizes at least 44x44 CSS px for touch
- Readable type size and line length
- Meaningful `alt` for informative images; empty `alt` for decorative
- `prefers-reduced-motion` honored
- 200% zoom without loss of content or function
- Responsive reflow without horizontal scrolling
- Every form control labeled
- Errors communicated in text, not by color alone, and associated with fields

If an accessibility requirement conflicts with a visual choice, change the
visual choice.
