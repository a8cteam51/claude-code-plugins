# html-to-block-theme evals

Promptfoo evals for the `html-to-block-theme` skill. Each case asks one design question and
asserts that the skill's rule wins over the model's default instinct.

```bash
cd plugins/html-to-block-theme/evals
npm install
npm run eval        # 3 repeats
npm run eval -- 1   # 1 repeat, for a quick check
```

Requires Claude Code installed and signed in (`claude auth status`), or `ANTHROPIC_API_KEY`.

Run it through `npm run eval`, not bare `promptfoo eval`. The config reaches its workspaces
through `{{ env.H2BT_WORKSPACES }}`, which `scripts/run-eval.mjs` sets; without it the
template is left unrendered and the providers get a junk working directory.

## What is measured

Two arms, same prompt:

| Arm | Skill |
|---|---|
| `Claude Code with no skill` | none discovered — no `setting_sources`, no `skills` |
| `Claude Code with html-to-block-theme` | the skill, copied from `../skills/` |

**A case earns its slot only when the skill-off arm fails it.** If both arms pass, the base
model already knows the rule and the case measures nothing. `run-eval.mjs` prints the split
per case and labels dead-weight cases and regressions explicitly rather than leaving them to
be spotted in a green table.

## Cases

| Case | Rule under test | Source |
|---|---|---|
| The homepage is a page, never front-page.html | Homepage is content, not a view: a WP page plus `show_on_front`/`page_on_front`; own chrome means a `customTemplates` entry | `references/mapping-guide.md` § The homepage rule |
| Block style CSS is one file per block type | `register_block_style()` + `assets/css/blocks/core-button.css` + `wp_enqueue_block_style()`, never a monolithic stylesheet | `references/block-styles-guide.md` § The rule |
| core/html policy rejects an anchor-wrapped SVG | Bare inline SVG is allowed; wrapping it in `<a>` is not, and icon links belong in `core/social-links`. Real embeds stay allowed | `references/mapping-guide.md` § core/html policy |
| Build-less custom block registration | Progressive disclosure — does SKILL.md's pointer actually retrieve? See below | `references/custom-blocks-guide.md` |

### The disclosure case is not an A/B

The first three cases ask whether the skill knows a rule. The fourth asks something different:
**does SKILL.md's pointer to a reference file work?** Every fact it asserts lives only in
`custom-blocks-guide.md` — `viewScriptModule`, `editorScript`, the no-JSX global-`wp`
registration, and the `GLOB_ONLYDIR` loop appear nowhere in SKILL.md.

`assertions/opened-reference.cjs` checks the retrieval itself by reading
`metadata.toolCalls` for a read of the named file. That splits the result four ways:

| | correct | wrong |
|---|---|---|
| **opened** | pointer works, guide is clear | pointer works; the guide's wording is the problem |
| **not opened** | base knowledge — proves nothing about disclosure | **the pointer failed** — what this case exists to catch |

**Do not read this case as skill-vs-no-skill.** The baseline has no reference file in its
workspace, so it can never pass the retrieval assertion — scoring it as "separates" would be
a tautology. `run-eval.mjs` detects the `Opened the guide` metric and prints the quadrant
instead of a separation verdict.

The first version of this case made exactly that mistake. It asserted only
`viewScriptModule` / `editorScript` / `createElement` / `wp.blocks`, and the unaided arm
passed all four without opening anything — those are standard WordPress knowledge. The
`GLOB_ONLYDIR` assertion was added because registering blocks with a glob loop over
`blocks/*` is a house convention rather than public knowledge: an unaided model writes an
explicit `register_block_type()` per block. It is the only content assertion in the case
that discriminates.

## Measured separation

3 repeats, Claude Opus, 2026-07-29. Case-level pass rate, skill-off vs skill-on:

| Case | skill-off | skill-on | Verdict |
|---|---|---|---|
| The homepage is a page, never front-page.html | 0/3 | 3/3 | Separates cleanly |
| Block style CSS is one file per block type | 3/3 | 3/3 | Dead weight — base model knows this |
| core/html policy rejects an anchor-wrapped SVG | 1/3 | 3/3 | Separates, noisier |
| Build-less custom block registration | — | — | Disclosure case, added later; not an A/B (see below) |

Read it per assertion, not just per case. In case 1 the work is done by `Avoids
front-page.html` (0/3 → 3/3) and `customTemplates` (0/3 → 3/3); `show_on_front` /
`page_on_front` is 6/6 on both arms. In case 3 only `Anchor-wrapped SVG rejected` (1/3 → 3/3)
carries signal — `core/social-links` is 3/3 unaided.

The block-style case is worth reconsidering. An unaided Opus reproduces
`assets/css/blocks/core-button.css` + `register_block_style()` + `wp_enqueue_block_style()`
verbatim, because it is the Twenty Twenty-Four convention rather than anything specific to
this skill. It still guards against a bad edit to `block-styles-guide.md`, but it does not
show the skill earning its context. Rules with no public equivalent would separate better —
the SQLite-serial subagent constraint or the `studio wp eval-file -` stdin no-op and its
sentinel grep, neither of which a base model can know.

## Design notes

Three of these were learned by running the suite and reading what came back. They are worth
keeping in mind before adding a fourth case.

**Workspaces live outside the repo.** They are created under `os.tmpdir()`. When they sat in
`evals/.workspaces`, the skill-off arm walked up out of its working directory, found
`plugins/html-to-block-theme/skills/.../references/mapping-guide.md`, and answered from the
file under test — citing line numbers. Every case looked like the base model already knew the
rule. A baseline arm must have nothing to find.

**Negative assertions punish correct answers.** `not-icontains: front-page.html` failed a
skill-arm answer that opened with "**Not `templates/front-page.html`.**" — naming the
anti-pattern in order to reject it. `assertions/homepage-rule.cjs` checks for *endorsement*
instead: every mention must carry a rejection cue tight against it. The window is small on
purpose; a wider one passed an answer that recommended the file outright, because unrelated
prose drifted into range.

**Path rewriting.** `SKILL.md` addresses its references through `${CLAUDE_PLUGIN_ROOT}`, which
only resolves when Claude Code loads the skill as an installed plugin. `reset-workspaces.mjs`
copies the skill into `.claude/skills/` and rewrites those paths to `${CLAUDE_SKILL_DIR}`. It
exits non-zero if any `${CLAUDE_PLUGIN_ROOT}` reference survives, because a dangling path
means the agent cannot open the references and the run measures a broken copy. The provider's
`plugins:` config key is the alternative — it loads the plugin directly and makes
`${CLAUDE_PLUGIN_ROOT}` resolve natively. Worth switching to if the rewrite list grows.

**No side effects.** With `working_dir` set and no tool overrides, this provider allows only
`Read`, `Grep`, `Glob`, and `LS`. The skill's `studio` preconditions cannot run.

**Regex assertions compile with no flags.** No `i`, no `s`. Spell case out as `[Ww]rapp`, and
use `[\s\S]{0,240}` rather than `.{0,240}` for proximity across line breaks.

**Scope.** These are recall cases: they test whether the skill's rules survive an edit to
`SKILL.md` or its references. They do not test Phase 1–4 orchestration, block markup
generation, or whether the skill triggers on a given user request — all of which need a
running Studio site, a fixture-driven generation case, or different harness plumbing.
