---
name: fresh-eyes-review
description: Re-examine a change you (or this session) just made — to catch bugs, missed cases, wrong assumptions, and regressions before they ship — then fix what you find. Use whenever the user asks to "recheck with fresh eyes", "double-check", "did we miss anything", "sanity-check this", "look again for bugs", "review the change again", "anything we missed", or similar, especially after implementing a change or opening a PR. Distinct from a first-pass review of unfamiliar code: this skill assumes the work is recent and yours, and its job is skeptical re-derivation from ground truth, not re-confirmation from memory.
---

# fresh-eyes-review

Re-examine a change that was just made, find what was missed, and **fix it** (the user almost always wants fixes, not just a list). The core stance: **distrust your own recent work.** The bugs that survive the first pass are the ones you were confident about — re-derive from ground truth instead of re-confirming from memory.

Work the checks below in order. Skip a check only when it's clearly inapplicable, and say so. Don't declare "looks good" until you've actually run the checks — a clean report you didn't earn is worse than no report.

## Step 1 — Re-read the *real* change, not your memory of it

Pull the actual diff against the base, not just the last commit: `git diff <base>...HEAD` for the whole branch, `git diff` and `git diff --staged` for uncommitted work, or `gh pr diff <number>` for a PR. List every file and hunk that changed. If you're reasoning about what the code does from your mental model, stop and read the bytes. Most missed bugs hide in the gap between "what I meant to write" and "what is actually there."

## Step 2 — Audit callers of everything whose contract changed

For every function, method, hook, constant, schema, or return shape whose **signature or shape changed**, grep for *all* usages and confirm each one still works:

- A signature that gained/lost/reordered a parameter → every call site updated? A missed one is a latent fatal error or a silently-wrong argument.
- A renamed/removed symbol → no dangling references?
- A changed return shape → every consumer handles the new shape?

Explicitly confirm there are **no callers outside the file you edited** that you forgot. "I only changed this one function" is exactly when a missed caller bites.

## Step 3 — Verify every assumption against ground truth

This is where most real misses live. Anything you **guessed** rather than confirmed must be checked against the authoritative source — not assumed:

- Identifier / field / enum / operation / tool / API names → check the real API response, schema, type definition, or doc.
- File paths, config keys, constant values → check the real file.
- "It's probably called `x`" / "it returns roughly `{...}`" → go look. If the real name differs, your code silently no-ops or breaks.

If you cannot verify something, **flag it explicitly as unverified** rather than presenting it as checked. (Example pattern: a hand-written allowlist of operation names that turns out to omit the one operation that actually matters — verifiable in seconds against the real list, invisible if assumed.)

## Step 4 — Confirm the change is additive, not regressive

Trace whether the change *only adds* the intended new behavior, or could alter existing paths. For each existing code path the change touches, ask: **is the new behavior identical for inputs that used to work?** Watch for changes that reclassify, shadow, short-circuit, or reorder existing logic. "Purely additive" is a claim to prove, not assume.

## Step 5 — Re-check security and authorization boundaries

If the change is a gate, allowlist, permission check, validation, or anything that decides *what is allowed*:

- **Fail-closed?** Unknown / unexpected / malformed input → deny, not allow.
- **Over-broad?** Does it grant more than intended (e.g. un-gating a whole multiplexed tool to expose one read, when that also exposes its writes)?
- **Dangerous ops still blocked?** Confirm writes/deletes/escalations remain denied.
- **Confirmation/auth flags honored?** A "read" must not be able to smuggle a write.
- Prefer **allowlist** (enumerate the safe) over **denylist** (enumerate the dangerous) — a denylist silently admits anything you forgot.

## Step 6 — Probe edge cases and fail-closed behavior

Missing fields, wrong types, empty strings, unexpected nesting, case sensitivity, null/zero, oversized input → does each default to the *safe* outcome? Construct the hostile input in your head (or a quick test) and follow it through.

## Step 7 — Verify side effects fire where intended

Logging, audit trails, caching, metrics, notifications, cleanup — do they happen on the **right path** (success vs. failure), the **right number of times** (not zero, not doubled), and never on the path that should stay silent?

## Step 8 — Check the tests actually exercise the risk

Do the tests cover the failure modes and boundaries, or just the happy path? If the risky behavior (the write that must stay blocked, the malformed input, the missed caller) has no test, add one. Re-run the suite.

## Step 9 — Fix, then re-verify

Apply the fixes — don't just report them. Then re-run tests, linter, syntax/type check, and build as applicable, and confirm green. Leave the fixes uncommitted, or commit them locally as a follow-up commit if the user's rules allow it, honoring the repo's branch conventions. **Ask before pushing** — a request to double-check is not permission to push. Never amend or force-push a branch that is already pushed unless the user explicitly approves it, and then only with `--force-with-lease`.

## Step 10 — Report honestly

Separate three buckets clearly:

- **Found and fixed** — what was wrong and the fix applied.
- **Found, needs your decision** — issues where the right call is the user's (scope, trade-off, missing context).
- **Checked, clean** — the load-bearing things you verified and they held (so the user knows the review was real, not perfunctory).

State plainly anything you **could not verify** and why. A faithful "I couldn't confirm X" beats a confident assertion you didn't earn. If you found nothing substantive, say so directly — don't invent issues to look thorough.
