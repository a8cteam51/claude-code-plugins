# poseidon-local

Run the [Poseidon](https://github.com/a8cteam51/poseidon-actions) **plan** and
**implement** agents locally in your Claude Code session instead of via GitHub
Actions — on the model you choose.

In CI, each Poseidon agent is a composite action wrapping
`anthropics/claude-code-action` (the Claude Code CLI, headless) with a fixed
model and a hard turn cap. This plugin runs the same agents in your session so
you pick the model (`/model`), with no turn cap.

## Always up to date — nothing cached

Neither skill stores the Poseidon instructions. Each run **fetches the upstream
`action.yml` live** from `poseidon-actions@trunk` with `gh`, and follows both
embedded instruction blocks — the `prompt:` task input and the
`--append-system-prompt` operating contract. The plugin ships only a thin local
override layer (the fetch step + the local deltas below), so behavior always
tracks the deployed Poseidon version.

## Skills

| Command | Ports | What it does |
|---|---|---|
| `/poseidon-plan [owner/repo] <issue> [site:<blog-id>]` | `issue-plan` | Reads the issue, gathers site context via the `team51` MCP, posts a build-ready `### Poseidon plan` comment. |
| `/poseidon-implement [owner/repo] <issue>` | `issue-implement` | Reads the approved plan, implements on `fix/issue-N` (Git Flow aware), lints, opens the PR(s). |

## Requirements

- `gh` authenticated with access to **`a8cteam51/poseidon-actions`** (to fetch
  the instructions) and to the target repo (read issues, post comments, push,
  open PRs).
- For site-specific tickets: the `team51` MCP server (tools
  `mcp__team51__wpcom_*` / `pressable_*`). If not yet in your permission
  allowlist, allow them when prompted or add `mcp__team51__*` to
  `~/.claude/settings.local.json`.
- `poseidon-implement` must run from inside a clone of the target repo.

## Model

The only knob. Runs on your current session model — set it with `/model`
(e.g. `/model opus`) before invoking, or pin a default by adding
`model: <id>` to a skill's `SKILL.md` frontmatter.

## Local deltas vs CI

- **Instructions:** fetched from `poseidon-actions@trunk` every run — nothing
  cached to drift.
- **MCP:** your local `team51` MCP replaces the OpsOasis credential-brokering
  `gateway`.
- **Identity:** you act as your own `gh` user (CI used the
  `t51eng-poseidon[bot]` App).
- **Questions:** if the plan agent needs clarification, it asks you in-session
  and continues, instead of posting a questions comment and waiting for a
  label re-add.
- **Dropped:** run-tokens, progress pings, cost telemetry, `poseidon-pr`
  labeling, and the `pr-review-fix` auto-chain.
- **Not ported:** `issue-implement-v2` (Pressable clone + Playwright verify).
