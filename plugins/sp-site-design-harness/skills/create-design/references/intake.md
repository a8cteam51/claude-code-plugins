# Intake

Read before starting any design work. Produces the filled brief that DISCOVER
works from.

## Step 0 — Check for `research/brief.md` first

Before running the conversational intake below, check whether
`research/brief.md` exists (relative to the current project — this is the
output of this plugin's `research-intake` skill, Phase 1).

- **If present**, consume it directly as the brief. Do not re-run the
  ~4-question intake below. Read every field and its confidence tag
  (`Explicit` / `Inferred` / `Gap`, per
  `../../research-intake/references/brief-schema.md`). Only ask clarifying
  questions — still capped at one batched round via `AskUserQuestion` — for
  fields `brief.md` itself flagged as an unresolved `Gap` (i.e. it says
  something like "no input — Phase 2 will use creative judgment here" rather
  than naming a team default). Do not re-ask anything `brief.md` already
  answered, including anything it resolved via a stated default or team
  fallback — that resolution stands.
- **If absent** (this skill invoked standalone, or Phase 1 was skipped), fall
  back to the intake procedure below, unchanged.

Either path produces the same internal brief shape (see "The brief" below)
before DISCOVER starts.

## The rule

**Derive first, ask second.** Fill every field you can from what the user
already said, from files they pointed at, and from the repo. Then ask — once —
only for fields that are both **unstated** and **would change the design**.

Never re-ask something you were told. A user who hands over a complete brief
should get zero questions and see you start work.

**Ask about facts and inputs. Never about taste.** "Is the copy real or
placeholder?" is a fact. "Do you prefer the serif?" is taste, and asking it
hands back the judgment this skill exists to supply.

**Project-supplied fonts are binding, and checked first.** If the project
ships its own font files or names specific licensed fonts as supplied
identity, that is the typeface decision — full stop. It overrides both the
catalog at `~/.claude/local-font-sources/` and Google Fonts for anything it
covers; do not offer or evaluate alternatives against it. This is a fact
about the engagement (the client has already chosen and cleared the font),
not a taste call, so check for it during intake, before any typeface
search starts. Only when no font is supplied does a typeface search happen
at all — and when it does, see `references/typography.md` (read at DEFINE
2): treat `~/.claude/local-font-sources/`'s catalog (if present) and
Google Fonts as one combined pool of candidates, evaluated together on fit
to the brief. Neither is the default and neither is a fallback for the
other.

## The field set

| Field | Usually | If missing |
|---|---|---|
| What it is · primary user action | Inferable from the request | Ask |
| Primary audience | Inferable | Infer and state the assumption |
| **Emotional target** | **Usually unstated, always material** | **Ask** |
| **Content — real or placeholder** | **Usually unstated, always material** | **Ask** |
| **Supplied identity — brand, type, palette, refs** | **Usually unstated, always material** | **Ask** |
| **Composition — open or already settled** | **Usually unstated, always material** | **Ask** |
| Output shape — **how many (N)**, where, what format | Default: **N = 3**, one self-contained file each, in `./directions/` | Default silently |
| Hard constraints — a11y target, platform, tech | Default: WCAG AA, static HTML/CSS, no framework | Default silently |
| Risk appetite — **only when N = 1** | At N≥2 the ladder spreads it; nothing to ask | Ask (see below) |

The four in bold are the default question set. They are what the model most
often guesses at, and each guess changes the output substantially. Four fits
`AskUserQuestion`'s ceiling exactly.

**Risk appetite is the one addition, and only at N = 1.** With two or more
options the ladder in `SKILL.md` step 2 assigns the levels and nothing is asked.
With a single option there is no ladder to spread, so how bold the work should be
would otherwise be an unstated guess. It is askable because it is a fact about
the engagement — like audience, or whether a brand exists — not a matter of
taste. Which typeface, which palette, which composition remain never-ask.

**It replaces composition in the four-question set, it does not extend it.**
Five questions do not fit `AskUserQuestion`. At N = 1 ask risk appetite and drop
composition: a user whose composition is already settled says so unprompted, and
step 2 already skips the draw in exactly that case. The ceiling stays four.

**If you cannot ask, default to medium** and say so, the same way you state every
other assumption. Never silently pick low — a low option that nobody chose is
indistinguishable from not having a point of view.

## Asking

One round. At most four questions. 2-4 options each; free-text "Other" is added
automatically, so never write your own "something else" option.

**Every question carries a default, including an explicit "you choose" option.**
Resolve that one yourself and say what you assumed. This is what makes a single
round survivable — the user can answer nothing and still get good work.

Build options from real state, never placeholders. If there is a `content.md`
in the directory, the copy question should name it. When `research/brief.md`
exists (Step 0), it is real state too — build options from what it says rather
than from a placeholder.

Suggested defaults when the user picks "you choose":

- **Emotional target** — derive from the product category and the seed's
  characteristics. Name the three adjectives you settled on.
- **Content** — use whatever real copy exists. If none, write realistic
  placeholder copy and note the assumption in the brief/chat only — never
  visibly flag it as placeholder inside the output HTML. The design should
  read as a complete, real website.
- **Identity** — assume none supplied and explore freely.
- **Composition** — assume open, which means N built directions.

**N never needs asking.** Take it from the request — "give me five", "just two"
— and default to three when unstated. Explore roughly 5-7 directions in prose
per option to be built, so N scales the exploration too.

## When you cannot ask

Non-interactive session, the tool is unavailable, or it returns empty answers.
Do not hang, and do not proceed silently. State the assumptions you are making
for each unfilled field, then proceed. The user can correct a stated assumption;
they cannot correct an invisible one.

## The brief

The answers populate this. Keep it internal unless asked — it is the record
DISCOVER works from, not a deliverable. It is also exactly what a user can paste
to skip the interview entirely, and it is the same shape `research/brief.md`
is normalized into when Step 0 finds one.

```
PROJECT
- What it is:
- Audience:
- Primary action:
- Should feel:
- Inputs supplied:
- Content:

OUTPUT
- N distinct directions (N = 3 unless stated), one self-contained HTML file
  each, in ./directions/ as 01-<slug>.html … NN-<slug>.html. CSS inline.
  Identical content across all of them.
- Conceptually different, not N colourways of one layout.
- Each: two-line thesis, plus a token list (type, palette with roles, spacing,
  radius, border and shadow strategy) — written to disk alongside the HTML
  file as `NN-<slug>.tokens.md` (see "Output files" below), not left only in
  chat.
- Each built to completion — craft, responsive and accessibility passes all run.
- Screenshot each at desktop and mobile. Present them all and stop.
- `directions/index.html` — a nav/overview page linking every built
  direction. Required, every run.

CONSTRAINTS
- Brand rules:
- Accessibility: WCAG AA minimum — check contrast numerically, don't eyeball.
- No gradients, glassmorphism, decorative blobs or stock iconography unless the
  concept requires it and you can say why.
```

## Output files

Every selected direction produces two files side by side in `./directions/`,
plus one shared index:

- `NN-<slug>.html` — the self-contained page, as before.
- `NN-<slug>.tokens.md` — the same token list this skill already produces in
  its chat response for that direction, persisted to disk instead of left
  only in conversation. Minimum contents:
  - Type scale (roles → sizes/weights/line-heights)
  - Palette with roles (not just swatches — which token plays which role)
  - Spacing scale
  - Radius convention
  - Border and shadow strategy (state plainly when any of these is "none")
- `directions/index.html` — one nav/overview page linking to every built
  `NN-<slug>.html`, generated once per run. Required output, not optional.

## Gate

Do not start designing until every field is filled — by the user, by inference
you have stated, or by a named default. An unfilled field that nobody noticed is
how a run ends up generic.
