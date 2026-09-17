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
