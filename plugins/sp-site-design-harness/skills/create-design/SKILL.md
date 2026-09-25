---
name: create-design
description: Design process for producing distinctive, art-directed digital design instead of generic AI-default interfaces. Use whenever building or refining the visual design of a marketing site, landing page, product interface, web app, mobile UI concept, interactive experience, or design prototype — including any request to "make it look good," "design a page," "improve the UI," or "make this less generic." Governs design thinking, direction-setting, critique, reduction, and polish; framework- and style-agnostic. Phase 2 (Design) of the sp-site-design-harness pipeline — ported from consistent-high-quality-design.
---

# Create Design

Phase 2 of the sp-site-design-harness pipeline (Research → **Design** → Dev
Handoff). This skill is `consistent-high-quality-design`, kept close to
as-is and renamed for this plugin — its DISCOVER→DEFINE→DELIVER engine,
seed/risk-ladder variety mechanism, critique pass, and anti-slop audit are
the actual "quality" differentiator in this system and nothing else
reproduces them. See `../../references/instruction-priority.md` for the
harness-wide priority order this skill reconciles brief constraints against
its own creative judgment with — brief constraints beat an unstated
stylistic default, explicit brand rules beat the brief's own goals, and
nothing beats accessibility.

## Core rule

Do not design by predicting the safest conventional interface. Explore, select,
deepen, critique, reduce, and refine until the result has a coherent identity and
a convincing level of polish.

Your failure mode is making individually reasonable decisions that are
collectively predictable. Check for it at every phase.

## Workflow

```
DISCOVER  (expand)   → intake, seed, explore in prose, select N (default 3)
DEFINE    (commit)   → visual thesis + design language, then build composition
DELIVER   (reduce)   → critique, delete, polish, validate in a browser
```

DISCOVER runs once; DEFINE and DELIVER run once per selected direction.

Never jump from requirements to implementation. A supplied brand, palette,
typeface or reference is a **constraint to explore within**, never a reason to
stop exploring: it fixes the visual identity and says nothing about composition,
structure or density — which is where the design actually gets decided.

Skip to DEFINE only when the **composition itself is locked** — settled page
templates, or "match this existing page." Having brand guidelines is not that.

Pass each gate before advancing — see `references/gates.md`.

Load references on demand:

| File | Read before |
|---|---|
| `references/intake.md` | Starting any design work (DISCOVER 1) |
| `references/gates.md` | Advancing phases; declaring the work done |
| `references/critique.md` | Running the independent design critic (DELIVER 2) |
| `references/craft-corrections.md` | Running the critic (DELIVER 2) and the craft pass (DELIVER 6) — accumulated craft judgment |
| `references/typography.md` | Choosing and embedding a typeface (DEFINE 2) |
| `references/polish.md` | The craft, responsive, and accessibility passes (DELIVER 6-8) |
| `references/generated-media.md` | Generating any image or video asset (OPTIONAL techniques) |

---

## PHASE 1 — DISCOVER (be expansive)

### 1. Intake — REQUIRED

Read `references/intake.md` and fill the brief before designing anything.
**If `research/brief.md` exists (relative to the current project), consume
it directly instead of conducting the ad-hoc conversational intake** — see
`references/intake.md` for the exact procedure and what still gets asked.

Derive every field you can from what the user already said. Then ask — **once,
at most four questions, using AskUserQuestion** — only for fields that are both
unstated and would change the design. Never re-ask something you were told.

**Ask about facts and inputs. Never about taste.** Whether a brand exists, real
or placeholder copy, the emotional target — facts, ask them. Which typeface,
which palette, which composition — taste, never ask. That is the judgment this
skill exists to supply.

Write the filled brief down before choosing a direction. Separate three
requirement types and do not conflate them:

| Type | Question |
|---|---|
| Functional | What must the design accomplish? |
| Emotional | How should using it feel? |
| Visual | What existing identity or asset must inform it? |

### 2. Seed and risk ladder — REQUIRED

Draw design characteristics from outside your own judgment. This does not widen
the set the user sees — it stops every run of a brief returning the same menu.

Draw **one set per option to be built**, and keep every draw internal.

```bash
printf '%s\n' 'dense|sparse' 'modular|flowing' 'sharp|soft' 'restrained|saturated' 'narrow type|expansive type' \
  'regular rhythm|irregular rhythm' 'grid|asymmetric' 'mechanical|organic' 'flat|layered' 'quiet|loud' \
| sort -R | head -4 | while IFS='|' read -r a b; do
    [ $((RANDOM%2)) -eq 0 ] && pole="$a" || pole="$b"; echo "$pole $((RANDOM%31+60))"
  done
```

Set `head -4` to the level's count and the degree to its band — low
`$((RANDOM%26+45))`, medium as written, high `$((RANDOM%16+85))`. The pole sets
the direction, the degree how far from neutral. Commit to what you draw; resolve
a draw's tensions, don't average them.

**Spread risk across the options; never run one level for all of them.**
N=1 ask the user · N=2 low·high · N=3 low·medium·high · N≥4 split as evenly as N
allows, remainder to low and high before medium. Re-draw any option whose
characteristics duplicate another's.

| Level | characteristics | degree | edge-of-feasibility directions | font families |
|---|---|---|---|---|
| low | 3 | 45-70 | none | 2-3 max |
| medium | 4 | 60-90 | one | 2-3 max |
| high | 5 | 85-100 | two, one beyond what review would pass — explored, not always chosen | 3-4 max |

The font-family cap is a ceiling, not a target — see `references/typography.md`.

- **Risk sets ambition, never rigor or conviction.** Critique, deletion, craft,
  accessibility and the anti-slop audit run identically at every level. The low
  option is quiet, never unfinished or uncommitted — "low risk" is never the
  AI-defaults list's exception.
- Never show a draw, make it decoration, or let it override usability.

A supplied brand does not switch this off — dense vs sparse, grid vs asymmetric,
quiet vs loud all live inside any brand. Skip only when composition is locked.

### 3. Explore directions in prose — REQUIRED

Prose is cheap; building is not. Explore **roughly 5-7 directions per option to
be built** — 15-20 for the default three — in **one pooled round, not a round
per option**, which would re-tread ground and could not see what the last round
picked.

Ask "what is the strongest interpretation of this product's personality?" — not
"what is the safest attractive solution?"

Directions must differ **conceptually**, not cosmetically.

- Bad set: blue version / green version / dark version
- Good set: editorial archive · industrial instrumentation · cinematic title
  sequence · tactile physical object · scientific field notebook · immersive
  spatial interface · civic signage · handmade zine · trading terminal

Define each direction in ~4 lines:

- Central concept and emotional tone
- Composition strategy (grid, rhythm, density, asymmetry)
- Typography behavior and color philosophy
- Image/graphic strategy · motion and interaction character
- Why it fits this product

Edge-of-feasibility directions are set by each option's risk level (step 2), not
applied to the pool as a whole. Ask of them: *what would sound slightly too
ambitious or uncomfortable, yet be excellent if executed with discipline?*

### 3b. Select N, then build them all — REQUIRED for any new artifact

| Situation | Deliverable |
|---|---|
| New artifact, composition not settled | **Build all N selected** directions as real pages. Present them. Stop. The user chooses. |
| Existing design, or a direction already chosen | Single build — continue to DEFINE as normal |

**N is three unless the user asked otherwise** — intake records it.

Select **one direction per risk slot**, then on conceptual strength, suitability,
memorability, clarity and whether you can execute it well. The ladder carries
distance between options; still reject a set crowding one territory.

Then run each selected direction through the **full DEFINE → DELIVER cycle**.
Finished options to choose between, not sketches — the saving is in exploring
once, never in shipping rough comps.

File layout, token lists and the rest of the output shape are in
`references/intake.md`. Two rules that must not be lost:

- **Do not pick for the user.** Present them all and stop. If a direction isn't
  working, say so and why rather than quietly polishing it.
- A supplied brand constrains every option identically; they differ in
  composition, structure, density and imagery. N colourways of one layout is a
  failure.

### 4. Treat user reactions as primary design data

Any reaction — "I like this," "too corporate," "feels tacky," "that feels
AI-generated," "more like this," "this feels expensive" — is high-value. Convert
it into an explicit written principle, then apply the principle. Do not
regenerate from scratch.

Example — user says *"the industrial direction is interesting but the
skeuomorphic knobs feel cheesy"*:

- Keep: utilitarian, instrument-like structure and information density
- Drop: literal retro skeuomorphism
- Express tactility instead through spacing, type, micro-interaction, material
  texture, and component behavior

### 5. When references ARE supplied

Analyze them before designing. Extract **principles**, never layouts. Read for
density, rhythm, typography, contrast, geometry, color behavior, imagery,
material quality, interaction style, and level of restraint. Then build an
interpretation appropriate to this project.

Copying a reference section-for-section is prohibited. Ask "what design
principles make this reference successful?" and reuse those.

---

## PHASE 2 — DEFINE (be opinionated)

### 1. Write the visual thesis

One or two sentences naming the concept and what makes it recognizable. Check
every later decision against it.

### 2. Derive the design language from the concept

Define these before polishing any individual section. The concept determines the
system — do not start by generating a generic token set.

- Layout principles · grid behavior · spacing rhythm · density
- Type hierarchy and type personality — see `references/typography.md` for
  where to search and how to ship the chosen typeface, unless intake already
  recorded a supplied font
- Color system and its conceptual reason
- Image treatment · surface treatment
- Border, radius, and shadow strategy (any of these may legitimately be "none")
- Icon behavior
- Interaction language · motion language
- Responsive behavior
- Rules for intentional exceptions

### 3. Build the primary composition

Get the real hierarchy standing before adding detail or effects.

### 4. Pattern-regression check — run repeatedly while implementing

- Did this become hero + CTA + graphic again?
- Did everything become a card?
- Is everything centered?
- Are effects substituting for composition?
- Are gradients covering for a lack of visual ideas?
- Did every component acquire the same border radius?
- Did unnecessary badges, pills, labels, or icons appear?
- Is the interface overexplaining itself?
- Do decorative elements reinforce the concept, or just fill space?

When you find regression, fix the **structure**. Do not add decoration on top.

### Known AI defaults — avoid unless the concept requires it (a risk level is not a reason)

Generic SaaS layouts · centered heroes · text-left/illustration-right ·
purple or blue gradients · card overuse · uniformly rounded containers ·
decorative blobs · gratuitous glassmorphism · meaningless gradients ·
oversized headline type · stock iconography · excessive explanatory copy ·
redundant labels · uniform spacing everywhere · safe symmetry · unrequested
dashboards · three-up feature grids · arbitrary shadows · effects with no
conceptual purpose.

---

## PHASE 3 — DELIVER (be ruthless)

Stop adding ideas. This phase is subtractive: editing, simplifying, tuning,
aligning, correcting, testing — not new concepts.

Steps 1-3, 5, and 6-9 below together make up this phase's design QA pass —
browser validation, critique, deletion, and the craft/responsive/a11y/anti-slop
checks are one connected system, not independent chores. Read them as such.

### 1. Browser validation — REQUIRED

Never judge a visual implementation from source code. Run the app and inspect
the rendered result with the available browser/screenshot tooling.

Validate: actual layout · viewport behavior · type rendering · image loading ·
clipping · overflow · sticky behavior · interactions · animation · responsive
layouts. For motion work, inspect representative frames.

### 2. Independent design critic — REQUIRED when subagents are available

You must not be the sole judge of your own design. Read
`references/critique.md` and follow it — it holds the isolation rules, the
critic prompt, reference-based comparison, and the loop budget.

Default budget: **1 critique after the major composition exists → 1 substantial
revision → 1 final critique.** Continue only if meaningful gaps remain *and*
iterations are converging.

### 3. Post-critique re-validation — REQUIRED

A revision made in response to critique is still an unverified code change.
Re-screenshot after the revision, before moving on.

Default to a **targeted** re-check: the specific views, sections, and
breakpoints the critique or the revision touched, screenshotted and inspected
against the same categories as step 1 (layout, clipping, overflow, sticky
behavior, interactions, responsive behavior — whichever apply to what
changed). Escalate to a **full re-run of step 1** if the revision touched
layout structure, composition, or anything broadly (not a localized spacing
or decoration change).

While reviewing these screenshots, also weigh them against
`references/craft-corrections.md` — does anything here risk reading as an
accident rather than a deliberate choice?

### 4. Deletion pass — REQUIRED

You tend to add; removal is what produces quality here. Inspect every card,
label, badge, button, icon, divider, shadow, border, glow, gradient, background
shape, container, heading, explanatory sentence, animation, and decorative
graphic, and ask:

> What practical, communicative, emotional, or compositional purpose does this
> serve?

No strong answer → remove it. Then inspect the whole design again.

Be especially skeptical of: gratuitous gradients · glowing objects · decorative
pills · unnecessary containers · arbitrary accent colors · excessive section
labels · icon+title+description repeated endlessly · cards around content that
needs no card · duplicate navigation cues · copy explaining an image that
already communicates · oversized spacing that only lengthens the page · novelty
controls that are worse than native ones.

**Native controls.** Do not restyle native controls just to look custom. Prefer
platform conventions when they improve usability, accessibility, or polish.
Customize only for meaningful value.

**Then strengthen what remains** using scale, whitespace, placement, contrast,
typography, imagery, and rhythm. Do not replace deleted elements with different
decoration.

### 5. Post-deletion re-validation — REQUIRED

Deletion has non-local effects — removing one element can leave orphaned
spacing, break an alignment that depended on it, expose an edge case that used
to be covered, or strand hover/empty/error states that referenced what's gone.

Re-run the **full** browser validation from step 1 at wide desktop, laptop,
tablet, and small mobile, plus any interaction state that touched a deleted
element. This one is not targeted — the deletion pass by nature touches the
whole design, not one section.

### 6-8. Craft, responsive, and accessibility passes — REQUIRED

Run all three from `references/polish.md`. Accessibility is decided throughout
the process, not bolted on at the end.

### 9. Anti-slop audit — REQUIRED before declaring done

- **Concept** — could this exact visual language appear on hundreds of unrelated
  AI-generated sites? If yes, deepen the concept.
- **Composition** — did it default to standard website structure without reason?
- **Typography** — merely competent, or contributing to the identity? Within
  the risk level's font-family cap?
- **Color** — a conceptual reason, or just "attractive"?
- **Imagery** — avoiding imagery because code was easier?
- **Decoration** — are effects compensating for weak composition?
- **Components** — did everything become a card, pill, or rounded rectangle?
- **Copy** — is the interface saying more than necessary?
- **Motion** — contributing meaning or delight, or filler?
- **Restraint** — what can still be removed?
- **Identity** — **if the logo disappeared, would this still feel like this
  specific product?** Weight this question heavily.

---

## OPTIONAL techniques — generated imagery and video

Both are optional, and both are worth considering rather than defaulting to what
CSS can make. Read `references/generated-media.md` before generating any asset.

- **Imagery.** You overuse gradients, blobs, noise, and abstract SVGs. Before
  settling for those, ask whether purpose-built imagery would make the design
  substantially stronger. Every asset needs a stated design role, and must be
  validated inside the real interface — not in isolation.
- **Video.** Consider it only where motion is central and code alone could not
  convincingly produce the result. Never when CSS motion communicates better,
  when it harms performance, or when it creates accessibility problems.
- **Credentials.** If generation needs API keys: environment variables and a
  gitignored env file only. Never hardcoded, committed, or client-side.

---

## Failure recovery — abandon weak concepts, don't polish them

Diagnose before iterating again:

| Symptom | Action |
|---|---|
| Concept is generic | Return to DISCOVER — generate new directions |
| Concept is good, execution is weak | Stay in DEFINE — fix the design language |
| Result is cluttered | Move aggressively into DELIVER reduction |
| Motion is incoherent | Simplify or remove it |
| Imagery feels pasted on | Rethink the image strategy, not the image |
| Critic scores plateau across iterations | The concept is the problem, not the polish |

Do not preserve work because effort was already invested.

## Communicating with the user

Surface only decisions that need their attention:

- The built options when exploring, for them to choose between
- The chosen visual thesis
- Major critic findings and significant tradeoffs
- Points where their taste is genuinely needed

Do not narrate internal design reasoning or minor CSS decisions.

## Default autonomy

"Make it look good" is not permission to use AI design conventions. Run the
process: understand the product → explore distinct directions → establish a
visual thesis → build → inspect → critique → refine → reduce → polish. Make
strong decisions rather than asking for approval at every step.

Intake (DISCOVER 1) is not an exception to this. It asks only for **facts you
cannot infer**, never for which design to make. Choosing among the built
options is the user's call; every decision inside each one is yours.

## Completion criteria

Working code, complete sections, responsiveness, and a clean console are not
sufficient. Ship only when the design also demonstrates a coherent identity,
strong hierarchy, intentional composition, disciplined typography, meaningful
visual choices, restraint, appropriate interaction, thoughtful responsive
behavior, accessibility, and strong execution of the original concept.

The result must read as deliberately art-directed, not procedurally assembled.

**Output requirements (`directions/`):** for each selected direction, write
`NN-<slug>.html` *and* `NN-<slug>.tokens.md` — the same token list (type scale,
palette with roles, spacing, radius, border/shadow strategy) already produced
in conversation, persisted to disk so Phase 3 (`dev-handoff`) has something
machine-readable to read. See `references/intake.md` for the exact shape.
Also write `directions/index.html` — a nav/overview page linking every built
direction. This is a **required** output of every run, not an inconsistent
one, and it must be the shared house template, not an improvised page.

Before filling it, check `../publish-design-options/templates/MANIFEST.md`: if a
`.design-template` file already exists at this project's scope root (`projects/<slug>/`
when working inside this harness, otherwise the project's own top-level
folder — this run, or an earlier run against that same root), reuse it.
Otherwise present the available templates (name + one-line description,
default pre-selected) and ask which to use — a bare confirmation picks the
default. This is the same choice `/publish-design-options` presents, so ask
it once per project rather than twice; if the user later runs
`/publish-design-options` first, it asks instead and this skill should reuse
whatever was picked there.

Fill the chosen template exactly as `/publish-design-options` does for its
packaged index, with `{{OPTIONS}}` hrefs pointing at the sibling
`NN-<slug>.html` files directly rather than staged per-option directories.
Same template either way — the point is that a teammate opening this folder
and a partner opening the published link see an identical page.

When the run produced options for side-by-side review, offer
`/publish-design-options` — it packages them behind one private shareable link.
Do not publish without being asked.
