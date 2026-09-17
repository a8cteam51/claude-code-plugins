# DECISIONS

Append-only log. Don't rewrite history here — add to it.

## 2026-09-17 — Initialize git repo now, on `main`

The project had accumulated real content (skills, commands, docs) with no
version control. Initialized with `git init`, default branch `main`, before
any further changes, so that future work has history and a diffable base
instead of continuing to edit an untracked directory.

## 2026-09-17 — Add STATUS.md / DECISIONS.md / BACKLOG.md at repo root

The project was missing the three living state files the engineering-principles
skill requires for every project. Added them retroactively, backfilled from the
existing README/ARCHITECTURE rather than starting from a blank state, so the
repo's first commit already carries recoverable project state.

## 2026-09-16 — Package as a Claude Code plugin, phases stay independent skills

Considered: one monolith orchestrator skill, or loose unpackaged commands. Chose
a plugin bundling three separately-invokable skills (`research-intake`,
`create-design`, `dev-handoff`) sharing one `projects/<slug>/` folder as the
contract between them. Reason: each phase already worked independently before
this project existed, and the monolith shape was the specific failure mode
observed in the earlier `quick-site-poc` prototype (bespoke, hardcoded to one
client, unmaintainable). A plugin ships them together, versioned, without
forcing them into one file.

## 2026-09-16 — Rename `consistent-high-quality-design` to `create-design`

Ported near-verbatim (its DISCOVER→DEFINE→DELIVER engine, seed/risk-ladder
variety mechanism, and critique/anti-slop machinery are the actual quality
differentiator and were not reworked). Renamed only for consistency with the
other two phase-skill names in this plugin (`research-intake`, `dev-handoff`).

## 2026-09-16 — Mine `sp-design-system` and `quick-site-poc`, don't adopt either

Both are earlier, single-direction, end-to-end pipelines whose own internal
phase names (Research/Design/Development) collide with this harness's phase
names but mean something narrower — neither produces N real directions to
choose between, and both bundle the WordPress theme-build step this harness
explicitly excludes. Reused as mechanisms instead: the Input Ledger
(Used/Dismissed/Deferred/Unaccounted per input file), Explicit/Inferred/Gap
confidence tagging, the `[Design]`/`[Development]`-tagged accessibility split,
the DESIGN.md schema, and the lesson that tokens must be authored straight into
their destination file, never a `build/`/`handoff/` intermediate (a real past
engagement hit token divergence doing that).

## 2026-09-16 — Fork `design-standards.md` / `accessibility-standards.md`, don't reference `sp-design-system` live

Accepted tradeoff: the two copies can drift and need manual re-sync, in
exchange for not repeating the "one skill living in two places" bug that
already caused a stale-skill near-miss on a real `sp-design-system` engagement
(global `~/.claude/skills/` copy vs. the repo-vendored copy diverging).

## 2026-09-16 — Instruction Priority Order applies harness-wide, not just at Dev Handoff

`Accessibility standards > Explicit brand rules > Project brief > team
design-standards defaults > Claude's own generalist judgment` — originally
only used by `sp-design-system` for DESIGN.md gap-fill. Extended to govern
Phase 1's conflicting-input resolution and Phase 2's brief-vs-creative-judgment
calls too, so all three phases resolve conflicts the same way.

## 2026-09-16 — Dev Handoff stops at `DESIGN.md` + `decisions.md`; theme-build is out of scope by design

Unlike `sp-design-system`, which continues through authoring `theme.json`/
`style.css`/block templates and handing off to a WP build tool directly, this
harness's Phase 3 stops at structured design documents. The actual WordPress
block-theme build happens in a separate, external, TBD system this harness
hands off to — building it here would duplicate work already planned
elsewhere and expand this project's scope well past "design decisions."

## 2026-09-17 — Craft-corrections log (principles), not stricter per-issue rules

A first full pipeline run (research-intake → create-design → dev-handoff, in
throwaway test project `harness-test-1`) produced three complete, correctly
risk-tiered directions that each still had a subtle "reads as broken, not
intentional" issue — e.g. a sticky header's 1px top border sitting flush
against the viewport top with no gap, reading as a rendering glitch rather
than a deliberate border. Not an accessibility or responsive-rule violation;
a judgment call a trained designer's eye catches. Considered codifying a
literal rule (e.g. "top borders need Npx offset from viewport edge") and
rejected it: narrow rules like that risk misfiring in other contexts and
constraining the design space in unintended ways, and each direction's issue
in this test was different in kind, not a repeat of the same bug. Instead
added `skills/create-design/references/craft-corrections.md` — a living log
where each entry is forced into four fields (Symptom observed / Why it read
as unintentional / Generalized principle / Not a rule because), consulted as
advisory judgment by the critic and craft passes, not as a mechanical check.
The "Not a rule because" field (a required counterexample) is the specific
defense against the log calcifying into a rulebook over time. Full design
plan: `~/.claude/plans/okay-so-i-ve-just-shimmering-sun.md`.

## 2026-09-17 — Add mandatory re-validation after critique-revision and deletion pass

Same audit that surfaced the craft-corrections gap also found `create-design`
had no required re-screenshot after the critique-driven revision or the
deletion pass — so a bug introduced or left behind late in DELIVER had no
guaranteed re-check before shipping. Added two new required DELIVER steps:
a targeted-by-default re-validation after critique/revision (full re-run only
if the revision was structural), and an always-full re-validation after
deletion (deletion's effects are non-local — orphaned spacing, broken
alignment, stranded states — unlike a localized revision).

## 2026-09-17 — Rejected: promote critique/polish into a standalone "Design QA" phase

Considered adding a fourth pipeline phase (Design QA) between Design and Dev
Handoff to give QA more visibility. Rejected: this harness's phases are
artifact-transformation boundaries (brief → directions → DESIGN.md), not
quality gates; the critique/polish loop is iterative and tightly coupled to
the build itself, so detaching it into a separate phase would break the fast
screenshot→critique→revise→re-screenshot cycle; today's QA runs per-direction
before selection, which a single post-selection phase would weaken; and
Gate 5 already serves as the final pre-completion checkpoint a QA phase would
otherwise duplicate. Instead added one documentation-only line in
`create-design/SKILL.md` naming DELIVER steps 1-3, 5, and 6-9 as one connected
QA pass, for visibility without the structural cost.
