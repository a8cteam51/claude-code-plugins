---
name: poseidon-plan
description: Run the Poseidon planning agent on a GitHub issue locally, in the current session, on the session model. Fetches the LIVE upstream plan instructions from a8cteam51/poseidon-actions each run (always up to date), reads the issue, gathers site context via the local team51 MCP, and posts an architecture-level "### Poseidon plan" comment. Use when the user wants to plan an issue the Poseidon way or run poseidon plan locally. Examples - "/poseidon-plan 45", "/poseidon-plan a8cteam51/some-repo 45 site:212289766".
argument-hint: "[owner/repo] <issue> [site:<blog-id>]"
---

# poseidon-plan

Local, in-session port of the Poseidon `issue-plan` agent. It does **not** ship a
copy of the Poseidon instructions — it **fetches them live** from
`a8cteam51/poseidon-actions@trunk` every run, so you always match the deployed
version. It then follows those instructions with a thin set of local overrides,
running on the model you've selected with no turn cap.

## Inputs

`$ARGUMENTS`, one of:
- `45` — issue #45 in the current directory's repo.
- `a8cteam51/some-repo 45` — explicit repo + issue.
- Optionally append `site:<blog-id>` to pass the production WordPress Blog ID for
  MCP site lookups (e.g. `site:212289766`).

Requires `gh` authenticated with access to `a8cteam51/poseidon-actions` (to fetch
the instructions) and to the target repo (to read the issue and post the plan).
For site-specific tickets, the `team51` MCP server.

## How it runs

1. **Resolve** `OWNER/REPO`, issue number `N`, and optional Blog ID from
   `$ARGUMENTS` (bare `N` → `gh repo view --json nameWithOwner -q .nameWithOwner`).

2. **Fetch the live upstream instructions:**
   ```bash
   mkdir -p /tmp/poseidon
   gh api repos/a8cteam51/poseidon-actions/contents/issue-plan/action.yml \
     -H "Accept: application/vnd.github.raw" > /tmp/poseidon/issue-plan.action.yml
   ```
   If this fails (e.g. 404 / no access to the private repo), **STOP and tell the
   user** — do not fall back to remembered or guessed instructions.

3. **Read `/tmp/poseidon/issue-plan.action.yml`.** The *Run Claude Code* step
   carries TWO instruction blocks — extract and follow BOTH:
   - the `prompt:` input — the task itself (issue framing, comments pointer,
     Blog ID guidance);
   - the `--append-system-prompt "<PROMPT>"` value inside `claude_args` — your
     authoritative operating contract.
   Read both in full and **follow them exactly**, with the local overrides
   below. You are NOT executing the YAML's steps; you only extract and follow
   those two embedded prompts. If the fetched file no longer matches this
   layout, find the embedded prompts wherever they now live, follow them, and
   tell the user the upstream layout changed.

4. **Apply these LOCAL overrides** (they win wherever they conflict with the
   upstream prompt, which is written for CI):
   - **Environment:** you run locally in an interactive Claude Code session, not a
     GitHub Actions job. Ignore the "automated run / no human in the loop / never
     ask" framing to the extent that you MAY ask the user directly when genuinely
     blocked. There is no workflow — **you** post the output (see Posting).
   - **Templating:** substitute real values for GitHub Actions placeholders —
     `${{ steps.prep.outputs.issue }}` = `N`; `${{ inputs.issue_title }}` /
     `${{ inputs.issue_body }}` = the real title/body from
     `gh issue view N --repo OWNER/REPO --json title,body,labels`;
     `${{ steps.comments.outputs.questions_asked }}` = the count of existing
     `### 🔱 Poseidon — clarifying questions` comments on the issue. The
     production Blog ID the CI passes in the prompt is whatever you parsed from
     `site:<blog-id>` (or empty if not given); treat the Pressable site URL
     input as empty (the upstream lookup sequence resolves the URL via wpcom).
   - **Staged files:** the upstream reads pre-staged files like
     `/tmp/poseidon-issue-comments.md` and `/tmp/poseidon-prior-questions.md`. They
     don't exist locally. Instead fetch
     `gh api repos/OWNER/REPO/issues/N/comments --paginate` once and derive both,
     using the upstream's own filters:
     - *comments* = comments whose `user.type` is not `Bot` and whose body does
       not start with `### Poseidon plan`;
     - *prior questions* = the LATEST comment starting with
       `### 🔱 Poseidon — clarifying questions`, regardless of author (in CI
       these are bot-posted, so don't let the bot filter hide them).
   - **Questions mode:** if, per the upstream rules, you land in questions mode,
     do NOT post a questions comment and do NOT emit the "remove and re-add the
     **poseidon** label" footer — that's CI plumbing. Ask the user your 2-3
     questions directly in this session, wait for their answers, then proceed to
     plan mode in the same run.
   - **MCP:** the upstream routes site data through the OpsOasis `gateway` MCP
     server (`mcp__gateway__load-provider` / `mcp__gateway__execute-tool`). That
     server does NOT exist locally. Use the local `team51` MCP instead — it
     exposes per-service tools, so call `mcp__team51__wpcom_*` and
     `mcp__team51__pressable_*` **directly**, with no load-provider/execute-tool
     step. For project-P2 search use the `context-a8c` MCP — that one IS a
     load-provider/execute-tool gateway, so load its `wpcom` provider first,
     then execute-tool. If a tool is denied or unavailable, note it and continue.
   - **Ignore all CI plumbing:** run-tokens, OIDC, progress pings, cost telemetry,
     and the plan-mode / meta marker files — none apply locally.
   - **Posting:** post your final plan yourself as ONE issue comment. The
     upstream says not to start with `### Poseidon plan` because CI prepends
     that header — locally YOU prepend it: first line `### Poseidon plan`, blank
     line, then the plan. Write it to a temp file, then
     `gh issue comment N --repo OWNER/REPO --body-file <file>`. Override any upstream
     line that says the workflow posts it or that you must not post it yourself.
     (The exact header matters: `/poseidon-implement` finds the plan by it.)
