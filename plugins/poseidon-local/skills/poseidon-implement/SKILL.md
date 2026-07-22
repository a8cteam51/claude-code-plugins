---
name: poseidon-implement
description: Run the Poseidon implementation agent on a GitHub issue locally, in the current session, on the session model. Fetches the LIVE upstream implement instructions from a8cteam51/poseidon-actions each run (always up to date), reads the approved "### Poseidon plan" comment, implements on a fix/issue-N branch (Git Flow aware), lints, and opens the PR(s). Use when the user wants to implement an issue the Poseidon way or run poseidon implement locally. Examples - "/poseidon-implement 45", "/poseidon-implement a8cteam51/some-repo 45".
argument-hint: "[owner/repo] <issue>"
---

# poseidon-implement

Local, in-session port of the Poseidon `issue-implement` agent. It does **not**
ship a copy of the Poseidon instructions — it **fetches them live** from
`a8cteam51/poseidon-actions@trunk` every run, so you always match the deployed
version. It then follows those instructions with a thin set of local overrides,
running on the model you've selected with no turn cap.

This ports the plain `issue-implement`, not `implement-v2` (the Pressable clone +
Playwright verification flow), which is tied to OpsOasis provisioning.

## Inputs

`$ARGUMENTS`: `45` or `a8cteam51/some-repo 45` (bare `N` resolves the repo from the
current directory).

Requires: the issue already has an approved `### Poseidon plan` comment (run
`/poseidon-plan` first); `gh` with access to `a8cteam51/poseidon-actions` (fetch)
and write access to the target repo (branches + PRs); and **the current directory
must be a clone of the target repo** (this agent creates branches, commits, and
pushes).

## How it runs

1. **Resolve** `OWNER/REPO` and issue number `N` from `$ARGUMENTS`. Confirm you are
   inside a clone of the target repo; if not, STOP and ask the user where their
   clone lives (or whether to clone it, and where) before continuing.

2. **Fetch the live upstream instructions:**
   ```bash
   mkdir -p /tmp/poseidon
   gh api repos/a8cteam51/poseidon-actions/contents/issue-implement/action.yml \
     -H "Accept: application/vnd.github.raw" > /tmp/poseidon/issue-implement.action.yml
   ```
   If this fails (e.g. 404 / no access), **STOP and tell the user** — do not fall
   back to remembered or guessed instructions.

3. **Read `/tmp/poseidon/issue-implement.action.yml`.** The *Run Claude Code*
   step carries TWO instruction blocks — extract and follow BOTH:
   - the `prompt:` input — the task itself (implement the plan, branch, PR),
     including the rule that newer post-plan human comments beat stale details
     in the plan;
   - the `--append-system-prompt "<PROMPT>"` value inside `claude_args` — your
     authoritative operating contract, **including its untrusted-input and
     production-read-only safety rules**.
   Read both in full and **follow them exactly**, with the local overrides
   below. You are NOT executing the YAML's steps; you only extract and follow
   those two embedded prompts. If the fetched file no longer matches this
   layout, find the embedded prompts wherever they now live, follow them, and
   tell the user the upstream layout changed.

4. **Apply these LOCAL overrides** (they win wherever they conflict with the
   upstream CI prompt):
   - **Environment:** you run locally in an interactive Claude Code session. Ignore
     the "no human in the loop / never ask" framing to the extent that you MAY ask
     the user when genuinely blocked. Your final text is your summary to the user
     (not a comment a workflow posts). The push/PR confirmation rule is step 5 below.
   - **Templating:** substitute the real issue number for
     `${{ steps.prep.outputs.issue }}` = `N` everywhere (branch names `fix/issue-N`,
     commit trailers, PR bodies), and the real title/body from
     `gh issue view N --repo OWNER/REPO --json title,body` for
     `${{ inputs.issue_title }}` / `${{ inputs.issue_body }}`. The upstream prompt
     expects `DEFAULT_BRANCH` and `HAS_DEVELOP` to be pre-set as env vars —
     compute them yourself instead:
     `DEFAULT_BRANCH = gh api repos/OWNER/REPO --jq .default_branch`, and
     `HAS_DEVELOP = true` iff `git ls-remote --heads origin develop` finds it. Use
     those values wherever the prompt references `$DEFAULT_BRANCH` / `$HAS_DEVELOP`.
   - **Plan source:** the upstream reads the pre-staged `/tmp/poseidon-plan.md`.
     Instead fetch it yourself: from `gh api repos/OWNER/REPO/issues/N/comments
     --paginate`, take the latest comment whose body starts with `### Poseidon plan`.
     If none exists, STOP and tell the user to run `/poseidon-plan` first.
     "Approved" locally means the user invoked this skill after reviewing that
     plan — but if multiple plan comments exist, or later human comments dispute
     or supersede the latest plan, confirm with the user which plan (and scope)
     to implement before writing code. The upstream's post-plan-comments file =
     comments created AFTER that plan comment, whose `user.type` is not `Bot`,
     and not themselves starting with `### Poseidon plan` — read those as newer,
     authoritative context.
   - **PR base branch:** in CI a plan-directed custom base branch travels via
     plumbing that doesn't exist locally. If the plan's *Branch / PR* (or
     *Constraints*) section EXPLICITLY names a target branch other than the
     default, cut `fix/issue-N` from that branch and open the primary PR against
     it. When the plan directs a single PR to only that branch, skip the develop
     cherry-pick flow; if it names a custom base but says nothing about develop
     and `HAS_DEVELOP` is true, ask the user whether the develop PR still
     applies. No explicit directive → normal `$DEFAULT_BRANCH` / `$HAS_DEVELOP` flow.
   - **MCP:** replace the OpsOasis `gateway` MCP (`mcp__gateway__load-provider` /
     `execute-tool`) with your local `team51` MCP — call `mcp__team51__wpcom_*` /
     `mcp__team51__pressable_*` directly for any verification lookups. If a tool is
     denied or unavailable, note it and continue.
   - **Ignore all CI plumbing:** run-tokens, OIDC, progress pings, cost telemetry,
     Node-toolchain auto-select, dependency pre-install, `poseidon-pr` labeling, and
     the `pr-review-fix` auto-chain. Install deps yourself before linting if needed.
   - **Output:** you create the branch/commits/PR(s) yourself as the upstream
     directs. Give your summary as your final message (it's fine to name/link the PRs
     you opened). Override any upstream line saying the workflow posts the summary or
     that you must not list PRs.

5. Because this pushes branches and opens PRs under **your** identity, confirm the
   diff with the user before the final `git push` / `gh pr create`, unless they
   told you to run unattended.
