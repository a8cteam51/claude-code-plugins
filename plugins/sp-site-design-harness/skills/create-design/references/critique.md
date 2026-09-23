# Independent Design Critic

You must not be the sole judge of your own design. Use a subagent or
fresh-context agent whenever available.

## Critic isolation — mandatory

Give the critic only:

- Representative screenshots (not code)
- What the product is
- The intended aesthetic / design direction
- Relevant user goals
- Any supplied visual references

Withhold:

- Source code
- Implementation difficulty
- Previous critiques or previous scores
- Time or effort invested
- Any rationale defending the current solution

This exists to defeat sunk-cost bias. A critic told how hard something was will
grade it generously.

## Accumulated craft judgment

Before writing the critic's brief, skim `references/craft-corrections.md`.
Include its **generalized principles only** (not the full log — not the
originating symptom or the "why," just the one-line principle from each
entry) as a short list in the critic's brief, alongside the design direction.

This is judgment for the critic to weigh, not a checklist to grade against.
Do not let it substitute for the critic's own eye, and do not tell the critic
which entry (if any) you expect to apply.

## Critic prompt

Use essentially the same criteria every iteration so scores are comparable.

> You are a demanding, visually literate design critic. You are shown
> screenshots of [PRODUCT], intended to read as [DESIGN DIRECTION]. Users come
> to it to [PRIMARY USER GOAL].
>
> 1. Identify the aesthetic and design language this work appears to be
>    pursuing.
> 2. Imagine how a top-tier design studio would execute that same idea.
> 3. Compare these screenshots against that bar — assess both macro composition
>    and micro detail.
> 4. Name the 3-5 changes with the highest visual impact.
> 5. Explicitly flag any of: generic AI patterns, visual clichés, unnecessary
>    decoration, weak hierarchy, inconsistent spacing, timid decisions,
>    overdesigned elements, underdeveloped ideas, awkward typography, poor image
>    treatment, weak interaction affordances.
> 6. Separately from taste: flag anything that could be mistaken for an
>    unintentional rendering artifact rather than a deliberate design choice —
>    something a viewer might read as "this looks broken" rather than "this
>    was designed this way," even if it would be defensible in isolation.
>    You have also been given a short list of standing craft principles this
>    team has learned from past work; weigh them if relevant, but do not
>    force-fit one onto something it doesn't actually describe.
> 7. Give a score from 1 to 10.
>
> Be specific, concise, and opinionated. Do not soften findings.

Never tell the critic what score is required. Treat ~9/10 as your own
aspirational bar only.

## Feedback quality

- Reject: "make it more polished."
- Want: "The hero has a strong asymmetrical premise, but the feature section
  collapses into a conventional three-card SaaS grid. Extend the asymmetric
  rhythm into the secondary sections."

If the critique comes back vague, re-ask for specifics before revising.

## Reference-based comparison — preferred whenever references exist

Give the critic the professional references as a **quality baseline, moodboard,
and craft reference — explicitly not a composition to copy.**

With several references, ask the critic to rank the implementation against them
on: polish, coherence, typography, composition, detail, restraint. Ranking
against real work produces sharper findings than open-ended aesthetic judgment.

## Loop and stopping rules

```
IMPLEMENT → RUN → SCREENSHOT → CRITIC → PICK HIGHEST-IMPACT GAPS → REVISE → RUN
```

Default budget:

1. One critique once the major composition exists (after Gate 2).
2. One substantial revision addressing the highest-impact gaps.
3. One final critique.

Continue past that only if meaningful gaps remain **and** successive iterations
are converging.

Stop and re-diagnose when:

- Scores plateau across two iterations
- Successive critiques contradict each other
- Findings shift to trivia while the earlier structural notes are unresolved

A plateau means the concept is the problem, not the execution — go to the
Failure recovery table in `SKILL.md`.
