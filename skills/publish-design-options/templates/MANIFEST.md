# Index page templates

Shared house templates for the design-options index/nav page. Both
`create-design` (`directions/index.html`, written after every design run) and
`/publish-design-options` (the packaged `index.html` sent to partners) fill
one of these — never improvise a nav page ad hoc. Using the same template in
both places is the point: a partner clicking the shared link and a teammate
opening the project folder locally see the same page.

| id | file | description |
|---|---|---|
| `deck` | `design-options-index.html` | Full-bleed blue cover with the Automattic wordmark and an oversized tight-tracked headline, then a numbered table of contents in black on white, then a provenance footer. Matches the team's Figma presentation-deck cover. **Default — use this unless asked for another.** |

## Choosing a template

This is a PM-facing choice, not a silent default — present it every time,
at both call sites (`create-design` writing `directions/index.html`, and
`/publish-design-options` packaging the partner-facing page):

List every row in the table above (name + one-line description), mark the
row flagged **Default** as the pre-selected option, and ask which to use.
Accept a bare confirmation (enter, "yes", "the default") as picking the
default — this must never turn into a multi-question gate when there's only
one template. As more templates are added, the same prompt naturally becomes
a real choice among several without any code change here.

Once chosen for a project, record the template id as plain text in
`.design-template` at the project's **scope root** — `projects/<slug>/` when
the project lives inside this harness's own working area, or the project's
own top-level folder (sibling to `.spacefast/`) when it doesn't. Resolve the
scope root the same way `/publish-design-options` step 1 does: an explicit
path if given, else `git rev-parse --show-toplevel`, else `$PWD`. Reuse the
recorded choice for later runs against that same root without re-asking,
unless the user brings it up — consistency across runs in one project still
matters more than re-litigating the pick every time.

## Adding a template

Drop a new `*.html` file in this directory and add a row above. It must
implement the same token contract as every other template here, so either
call site can fill any of them without special-casing:

| Token | Value |
|---|---|
| `{{PROJECT}}` | Project or client name |
| `{{VERSION}}` | `Version 1.0`, or the round of review this is |
| `{{DATE}}` | Long-form date, e.g. `January 1, 2026` |
| `{{COUNT}}` | Number of options/directions |
| `{{OPTIONS}}` | One `<li>` per option (see `design-options-index.html` for the expected markup shape) |
| `{{PROVENANCE}}` | `<dt>`/`<dd>` pairs: a timestamp, then one per option naming its source |

HTML-escape every substituted value, and assert no `{{` remains in the output
before writing it.
