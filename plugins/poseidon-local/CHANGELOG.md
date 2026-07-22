# Changelog

## [0.1.0] - 2026-07-21

### Added
- Initial release. Local, in-session ports of two Poseidon agents from
  `a8cteam51/poseidon-actions`:
  - `poseidon-plan` — GitHub issue → architecture-level `### Poseidon plan`
    comment.
  - `poseidon-implement` — approved plan → PR(s), Git Flow aware.
- **Live instructions.** Neither skill caches the Poseidon prompts. Each run
  fetches the upstream `action.yml` from `poseidon-actions@trunk` via `gh` and
  follows both embedded instruction blocks — the `prompt:` task input and the
  `--append-system-prompt` operating contract — so behavior always tracks the
  deployed version. The plugin ships only a thin local override layer
  (fetch step + local deltas).
- Local deltas vs CI: the OpsOasis `gateway` MCP is swapped for your local
  `team51` MCP; the agent posts its own output (plan comment / PRs) under your
  `gh` identity; GitHub Actions templating is resolved locally; clarifying
  questions are asked in-session instead of via a questions comment + label
  re-add; a plan-directed custom PR base branch is honored from the plan text
  (CI carries it via plumbing that doesn't exist locally); and all CI plumbing
  (run-tokens, OIDC, progress pings, cost telemetry, auto-chain) is ignored.

### Model
- Runs on your current session model (`/model`), or pin one with a `model:`
  frontmatter field. No other tuning — no turn cap, no config file.

### Not included
- `poseidon-review` (dropped) and `issue-implement-v2` (Pressable clone +
  Playwright verify — tied to OpsOasis provisioning).
