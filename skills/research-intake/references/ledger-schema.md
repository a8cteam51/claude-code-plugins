# Ledger Schema

Defines how `research/ledger.md` is built and how every item under
`research/inputs/` reaches a terminal disposition. Adapted from
`sp-design-system`'s Input Ledger mechanics
(`brand-extraction-schema.md`'s "Input Ledger" section), same rules, applied
to this plugin's `research/` folder shape instead of `projects/<slug>/inputs`.

## Why a ledger, not just reading files

Normalizing straight into `brief.md` measures completeness against *the
brief schema* — that's necessary but not sufficient. A supplied file only
enters the brief if some schema field happens to reach for it. A file
nothing reaches for is invisible to the rest of the pipeline unless
something is specifically watching the raw input tree. That's the ledger's
job: it runs over the supplied material, not over the schema.

This is not hypothetical — a real engagement (`mostly-human`, the source
this mechanism was mined from) left a professional client photo unexamined
in `inputs/` from intake until it was noticed by accident a week later,
while the build filled its slot with a placeholder. Everything else supplied
had a field pulling it; the photo had none.

## Building the ledger

Enumerate the input tree with `find` — do not infer contents from folder
names, and do not work from memory of what the user said they sent:

```bash
find "research/inputs" -type f | sort
```

Record the result in `research/ledger.md`, one line per **ledger item** —
not necessarily one line per raw file.

**Ledger items, not raw files.** A recognized bundle collapses to a single
entry — a font family folder is one item, not thirty font files; a `photos/`
folder full of one photographer's shoot is one item, not forty JPEGs, if
they share one obvious disposition. Without this the ledger is unusable
noise; with it, a large input tree resolves to a handful of real items, most
of them obvious.

## Dispositions

Every item carries exactly one:

- **Used** — names where it landed: a `brief.md` field, section, or asset
  reference. "Used" without a named destination is not a disposition, it's a
  guess.
- **Dismissed** — with a stated reason. Bulk dismissal under one shared
  reason is fine when the reason genuinely covers the group.
- **Deferred** — examined and understood, but deliberately not used *yet*.
  **Requires a pointer to a `BACKLOG.md` line owning the deferral.** A
  `Deferred` entry with no backlog pointer is not a disposition either — it's
  an `Unaccounted` item wearing a better word, and gets treated as the hard
  blocker it is.
- **Unaccounted** — the default state, and a **hard blocker**. See Gap-Check
  below.

**Why `Deferred` exists as its own state.** `Used` and `Dismissed` alone
force a false choice on material that is neither used nor rejected — e.g.
supplied photography that's examined and rights-checked but left unused by
editorial choice, or supplied font files examined in full and then
deliberately parked pending licensed webfonts. Calling either `Used` would
overclaim; calling either `Dismissed` would imply a rejection that never
happened. `Deferred` with a backlog pointer is the honest third state, and
the pointer is what keeps it a real terminal state rather than an escape
hatch — nothing supplied goes unexamined, but not everything supplied has to
get used.

## Standing auto-dismiss list

These may be dismissed without asking, so the ledger stays worth reading:

| Pattern | Reason |
|---|---|
| `.DS_Store`, `Thumbs.db` | OS noise |
| `README.txt`, `OFL.txt` | Bundled documentation |
| `*.zip` where a folder of the same stem exists | Duplicate of extracted contents |
| `*EULA*`, `LICENSE*` | Not a design input — **but see below** |

**License files are dismissed as design inputs and routed onward, not
discarded.** Any `*EULA*` or `LICENSE*` file gets flagged in `brief.md`'s
"things to avoid" or "existing assets" section as a licensing constraint to
carry forward — these files constrain what may be redistributed and where
the eventual build may be hosted. Dismissing one silently is how a licensing
constraint gets discovered after it's already been violated.

Anything not matching a pattern above is `Unaccounted` until a human says
otherwise.

## Gap-Check output (Step 3 of `SKILL.md`)

Every `Unaccounted` ledger item goes into the same batched question round as
the field gaps from `brief-schema.md` — not a separate round. Name the file
and ask what it is:

> **Unaccounted input file:** `brand-deck-v3.pdf` (2.1MB). This was supplied
> but nothing in the brief refers to it yet. Is it meant to be used, and if
> so where — or should I dismiss it?

**An `Unaccounted` item is the one hard blocker in this entire phase.** The
pipeline does not advance past Step 1 with one outstanding. This is
different from — and stricter than — the "proceed regardless of how much
gets answered" rule for field gaps in Step 3: field gaps get a stated
fallback and the pipeline moves on; an unexamined file does not get that
option, because filling a slot with a placeholder while a real supplied
asset sits unlooked-at is the exact silent-default failure this ledger
exists to prevent.

Only after every ledger item reaches `Used`, `Dismissed`, or `Deferred` does
Step 2 (Normalize) proceed to completion and Step 3's field-gap fallback
logic apply.
