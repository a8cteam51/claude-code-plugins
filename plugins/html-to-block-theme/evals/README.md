# html-to-block-theme evals

These evals answer one question: **on the model this plugin is pinned to, which of its passages does the model need, and which does it already do unaided?** Run them when the model changes, to decide what to delete and what to fix, and when a guide changes, to check the new text earns its place.

```bash
cd plugins/html-to-block-theme/evals
npm install
npm run site              # once: create the Studio eval site and install the fixture theme
npm run check -- --site   # no model: pins, registry, graders, facts about the tools
npm run eval              # the model. Resumable. About 370 answers: 75 minutes at xhigh, 13 at medium
npm run report            # writes reports/<model>@<effort>.md
npm run routing           # does SKILL.md send its reader to the right guide?
```

Requires Claude Code signed in (`claude auth status`), the `studio` CLI, and Node 22. The model calls go through the Agent SDK, which bundles its own Claude Code: one too old for the pinned model fails every call with `does not support this model`, so run `npm install` again after a model change.

`npm run report` writes the report for the current pin to `reports/`. Reports and the answers behind them (`results/`) stay on the machine that ran them: both directories are ignored by git. Keep them when the pin moves, so the next model's report can be read against the last one.

## What is measured, and what is not

A plugin's text is not all one kind of thing, and only some of it is a question about the model. `registry/kinds.yaml` gives every section of every file in scope a kind:

| Kind | What it is | What can judge it |
|---|---|---|
| `platform` | A fact about WordPress: an attribute form, what core prints, what it drops. | **A probe.** A newer model may know it. |
| `decision` | A decision of this team: the homepage is a page, pixels are whole, blocks come from the monorepo. | **A probe**, for whether the plugin gets it followed. No model knows it; one may happen to default to it. |
| `environment` | A fact about a tool: Studio, the Chrome extension, the shell, a third-party plugin. | **A script** (`registry/environment.yaml`), tried on the eval site. It goes stale with the tool, not the model. |
| `process` | How a run is organised: phases, serial builders, hand-backs, gates. | A scenario run. Not built. |
| `steering` | Wording that corrects a habit of the model: when to end a turn, when to look closer. | A scenario run, and the model's own prompting guide. Not built. |
| `reference` | Orientation: inputs, pointers, output formats. | Nothing. It is not a rule. |

So a verdict of "the model knows this" is only ever given to `platform` and `decision` passages. The report's coverage table shows how much of each file is each kind, and how much of the judgeable part has a probe. **A passage with no probe is untested, not unneeded.**

### A probe is a task with three arms

A probe (`registry/probes/*.yaml`) is a small piece of real work: a fragment of a design to convert, a plan to list. It is anchored to the passages that state its rule, and it is asked three ways:

| Arm | The model has | It asks |
|---|---|---|
| `bare` | The task, the WordPress version and the theme's `theme.json`. Nothing of the plugin. | Does the model do this unaided? |
| `guided` | What the rule's reader has loaded in a real run: the builder's instructions with the mapping and standards guides, or the skill with the mapping guide. | Does the plugin get it done? |
| `ablated` | The same, with the probe's passages cut out. | Would the plugin still get it done without them? |

The answers are graded by checks on the block markup, by the plugin's own `standards-audit.sh`, and by `render-probe.sh` on the eval site, which shows what WordPress prints for the answer.

### Verdicts

| Verdict | Means | Do |
|---|---|---|
| **needed** | Unaided the model does not do it; with the plugin it does. | Keep. |
| **known** | Unaided it does it every time, and still does with the passage cut. | Delete the passage. Keep the probe: a later model that fails it is the signal to restore the text from history. |
| **counterweight** | Unaided it passes, but inside the plugin without the passage it fails. Something else in the plugin pulls the other way. | Keep. |
| **partly known** | Unaided it passes some of the time. | Keep; perhaps shorten. |
| **not followed** | It fails even with the plugin. | The passage is unclear, or the probe is wrong. Read the failures in the report. |
| **worse with plugin** | Unaided it passes every time, and with the plugin it does not. | Find what in the plugin misleads. |

"Every time" is deliberate. Keeping a passage the model did not need costs tokens. Deleting one it did need costs a build.

### Sampling

Each arm starts with three answers. A clear **needed** (0 of 3 unaided, 3 of 3 with the plugin) stops there. Anything else goes to five, and a probe that passes unaided five times out of five gets the ablated arm, five times. Thresholds and counts are in `eval.config.json`.

Answers are stored as they come back (`results/<model>@<effort>/samples.jsonl`) and graded when read. A run that stops is started again and asks only for what is missing. A grader that turns out wrong is fixed and `npm run report` grades the stored answers again; no model is called.

## When the model changes

1. `bash ../scripts/model-pin.sh --set <model-id> [--effort <level>]` moves every pin: both subagents, the skill's precondition, `eval.config.json`, the README.
2. `npm install`, then `npm run check -- --site`.
3. `npm run eval`, then `npm run report -- --compare <old-model>@<old-effort>`. The comparison reads the old report from `reports/` on this machine. Without one, run the old pin again first with `--model` and `--effort`.
4. Act on the report. Delete **known** passages and keep their probes. Fix what is **not followed**. Re-examine a fact about a tool that is **not reproduced**.
5. Read the model's prompting guide against the `steering` passages. No eval here judges those.

To compare two efforts on one model, run `npm run eval -- --effort medium` and `npm run report -- --effort medium`: each model and effort has its own results and its own report.

## When a guide changes

- A new section fails `npm run check` until it has a kind in `registry/kinds.yaml`.
- A passage that was edited no longer matches its probe's anchor, and `check` says which. Fix the anchor, and the probe if the rule changed. Its stored answers for the plugin arms are then stale and are asked for again.
- A new `platform` or `decision` rule wants a probe. Until it has one, it counts as untested.

## Writing a probe

```yaml
- id: blockgap-drops-functions
  covers:                       # every passage that states the rule
    - { file: mapping-guide.md, match: "It drops any value that contains a parenthesis" }
  consumer: builder             # whose context the rule lives in: builder or orchestrator
  task: |                       # the message the model gets
    Convert this fragment …
  grade:                        # all must hold
    - no_block: { attrs_match: '"blockGap":"[^"]*[()]' }
  pass_example: |               # an answer the checks must accept
  fail_example: |               # what a model writes when it does not know the rule
```

- **A task, never a question.** Present the work as the design would. A question that names the shape of its answer measures the question: in the suite this replaced, the two cases that asked "is X allowed under our policy" and "which function loads the CSS" were the ones an unaided model passed.
- **Never name the rule.** No "per viewport", no "whole pixels", no "policy". The design's own CSS carries the situation.
- **One rule to a probe.** A check for a second rule makes the first look needed when only the second was missed: a probe for "no attribute carries a text shadow" that also wanted a registered style class failed unaided on the class alone.
- **Check the task, not the guide's answer.** Where WordPress offers two right answers, accept both (`any_of`). A probe that wanted only the guide's way of building an accordion failed a model that used core's accordion block.
- **Both examples, always.** `npm run check` runs the checks on them. A check that cannot tell them apart is caught there and not after a run: the old suite carried a pattern that did not compile, and it read as a failing guide.
- **Cover every copy.** A rule stated in three files survives an ablation that cuts one. List each passage under `covers`.
- **Check what WordPress prints** where the rule is about output: a `render` check runs the answer on the eval site.
- **For a plan, ask for a list** with each line starting with a path. A check can then tell a file that is created from one that is named in order to reject it.

The checks: `answer_`, `markup_`, `css_` and `json_` with `matches` or `lacks` (regular expressions; a leading `(?i)` ignores case); `some_block`, `no_block` and `every_block` over the answer's block delimiters (`name`, `attrs_match`, `attrs_lack`, `top_level`); `valid_blocks`; `audit` (counters of `standards-audit.sh` that must be 0); `render` (`html_` and `css_` `matches` or `lacks` on what the eval site prints); and `any_of`, a list of check lists of which one must hold, for a task with more than one right answer. CSS is checked without its comments, where a model explains what it did not do.

## What this does not tell you

- **The arms approximate a run.** The guides are put in the system prompt, where a real builder reads them as files, and the model has no tools, where a real builder can read core's `block.json` and probe. So **needed** means "not in the model's knowledge", which is a little stronger than "not discoverable in a run".
- **Five answers is a small sample.** It separates "never" from "always" well, and the middle badly. That is why only "always" leads to a deletion.
- **A probe speaks for its task.** A model that writes the right attribute for a padding may not for a border. A rule with one probe is tested once.
- **Process and steering are not judged.** Whether serial builders, the hand-back checks or the turn-ending rules earn their place needs scenario runs on a small design, which are not built.
- **Routing is judged only where `registry/routing.yaml` has a case.**
- **Environment facts are tried on one site.** The eval site is new, and runs Studio's native PHP runtime. A fact that is not reproduced there may still hold on a site created by an older Studio or on the sandbox runtime.

## The suite this replaced

Until 0.5.0 this was five recall questions run through promptfoo, each asserting that a skill arm named a rule an unaided arm did not. Its measurements, for the record:

| Case | Claude Sonnet 5, 2026-07-29 | Claude Opus 5.5 at medium, 2026-10-11 |
|---|---|---|
| The homepage is a page, never front-page.html | 0/3 unaided, 3/3 with the skill | 0/3, 3/3 |
| Block style CSS is one file per block type | 3/3, 3/3 | 2/3, 3/3 |
| core/html policy rejects an anchor-wrapped SVG | 1/3, 3/3 | 3/3, 3/3 |
| Custom behaviour checks the blocks monorepo (opens its guide) | not run | opened 3/3, answered 3/3 |
| Template mode keeps only an approved exclusion (opens its guide) | not run | opened 3/3, answered 3/3 |

The first three are probes now (`homepage-is-a-page`, `block-style-css-per-block`, `icon-links-are-social-links`), reworded as tasks. The last two are the routing cases.
