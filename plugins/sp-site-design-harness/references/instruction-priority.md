# Instruction Priority Order

This order applies harness-wide, across all three phases, not just at Dev
Handoff. When sources conflict, resolve in this order — higher items always
win:

```
Accessibility standards > Explicit brand rules > Project brief
> team design-standards defaults > Claude's own generalist judgment
```

1. **Accessibility standards** — the `[Design]`/`[Development]`-tagged
   criteria in `skills/dev-handoff/references/accessibility-standards.md`.
   Never overridden, by anyone, for any brand, except the explicit AA→AAA
   toggle documented in that file, which itself must be a logged,
   user-confirmed decision.
2. **Explicit brand guideline rules** — anything the client/partner's own
   brand source states directly (`Explicit`-confidence fields, per
   `skills/research-intake/references/brief-schema.md`).
3. **Project brief goals and content requirements** — what the site needs to
   accomplish and contain, as captured in `research/brief.md`.
4. **Team design-standards defaults** —
   `skills/dev-handoff/references/design-standards.md`. Fills any gap the
   brand source and brief leave open.
5. **Claude's own generalist design judgment** — lowest priority. Only
   invoked when nothing above has an opinion. Never silently fills a gap
   that should have gone through gap-check first.

## How each phase applies it

**Phase 1 — `research-intake`.** Uses this order to resolve conflicting
inputs during normalization: if two supplied files disagree (a brand PDF says
one thing, a live URL shows another), the more explicit/authoritative source
wins per this order, and the resolution — plus which source lost — is
recorded in `brief.md` with its confidence tag. Accessibility standards are
not a normalization input as such, but any brief field that would conflict
with a non-negotiable accessibility criterion (e.g. a "no visible focus
state" brand rule) is flagged as a conflict for Phase 2/3 to resolve in favor
of accessibility, not silently normalized away.

**Phase 2 — `create-design`.** Uses this order when reconciling brief
constraints against its own creative judgment. A brief constraint (level 3)
beats an unstated stylistic default Claude would otherwise reach for (level
5), but an explicit brand rule (level 2) beats the brief's own goals where
the two are in tension, and nothing beats an accessibility requirement (level
1) — if a design direction would violate one, change the direction, not the
requirement.

**Phase 3 — `dev-handoff`.** Uses this order when gap-filling `DESIGN.md`:
anything neither the chosen direction nor the brief specifies falls back to
`design-standards.md` (level 4) before any untethered aesthetic call (level
5) — and the `[Development]`-tagged accessibility gate (level 1) is a hard
stop regardless of what any lower-priority source prefers.
