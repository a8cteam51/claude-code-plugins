---
name: change-built-theme
description: This skill should be used when the user asks to change, fix or extend a WordPress block theme that the html-to-block-theme skill built, after its conversion run — "fix the header of the theme we built", "add a block style to the converted theme", "change the content of a page it built", "make the focus ring visible on the dark band" — or any theme in a repository generated from a8cteam51/a8csp-project-template. It covers theme.json, templates, parts, patterns, block styles and their Sass or CSS, theme PHP under includes/, theme JS, and the block markup of pages. It sends each change to the plugin guide that governs it and ends with the plugin's standards audit, which the project template's CI does not run. A new conversion is the html-to-block-theme skill's.
---

# Change a theme the plugin built

A conversion run ends with a theme that passes the standards audit. What follows it, a fix, a design change, a new block style or new page content, is held to the same standards, and nothing checks it: the audit runs only in a run, and the project template's CI does not run it. One fix made weeks after a run shipped three fractions of a pixel. This skill holds a later change to the plugin's guides and ends it with the audit.

The guides are in `${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/references/`, and they are the source of truth: where this skill and a guide differ, the guide holds. They write `<plugin-root>` for `${CLAUDE_PLUGIN_ROOT}`. The plugin's scripts are in `${CLAUDE_PLUGIN_ROOT}/scripts/`.

## Before the first edit

1. **Find the theme and its layout.** For a Studio site, `bash "${CLAUDE_PLUGIN_ROOT}/scripts/detect-project-template.sh" --site-path <site-path>` says whether the theme is in a project repository and, if so, where the repository, the theme and the features plugin are (`project-template-guide.md` § Detect and bind). In template mode, read `project-template-guide.md` first: it says where each piece goes.
2. **Read what the run left, if it is on this machine.** The machine that ran the conversion keeps its records in `<site-path>/.h2bt/`: `run.json` (the theme, the template's prefix and text domains, the widths each view was swept at), `blueprint.md` (the decisions and build notes) and `lessons.md` (what this site taught). Elsewhere there are none: take the same facts from the theme and the repository.
3. **Never run the conversion again over the theme.** A run replaces `theme.json`, the parts and the templates, and every later change with them.
4. **Branch.** In a project repository, start a new branch off `trunk` with the repository's prefixes, never `trunk` or `develop` (`project-template-guide.md` § Preconditions (template mode)).
5. **Check the database before blaming a file.** A `wp_template`, `wp_template_part` or `wp_global_styles` post saved in the Site Editor wins over the theme's file (`${CLAUDE_PLUGIN_ROOT}/skills/html-to-block-theme/SKILL.md`, Preconditions step 10).
6. **Audit once before the change,** as in step 2 of *Before calling it done*. What fails then is not this change's: say so in the pull request rather than fixing it in passing.

## Read the guide the change needs

| Changing | Read |
|---|---|
| block markup, or any styling | `mapping-guide.md`: the escalation ladder, attribute forms, per-viewport values, layout traps, navigation, WooCommerce, starter patterns |
| a registered style or a block stylesheet | `block-styles-guide.md` |
| `theme.json` | `theme-json-guide.md` |
| behaviour: a script, a filter, a block | `custom-blocks-guide.md` |
| a project repository | `project-template-guide.md` |
| what the audit enforces and why, comments, text wrapping, accessibility | `standards.md` |

Before writing a block you have not written on this core, read its `block.json` in the site's core, and probe a form you are unsure of with `render-probe.sh` (`mapping-guide.md` § Read the installed core, then probe).

## Make the change

- **At the lowest rung that does it** (`mapping-guide.md` § The escalation ladder), and at the most global level that is still correct. The pull request names every custom CSS rule the change adds, and why a lower rung could not do it.
- **In its home:** `standards.md` § Theme structure, and in template mode `project-template-guide.md` § Where each piece goes.
- **Under the theme's comment rule** (`standards.md` § Comments): block markup holds no comment but the block delimiters, and CSS and JS get no explanatory comments. The reason for a change goes in its commit and its pull request, not beside the code.
- **What the audit does not check, and later changes have broken:**
  - a hover or focus state changes no box (`block-styles-guide.md` § Icons in buttons);
  - motion has an off switch, focus is visible on every surface, and headings keep their order (`standards.md` § Accessibility);
  - text wrapping is written in the longhand (`standards.md` § Text wrapping);
  - no explanatory comment in the theme's JS, or in the Sass of a project repository, which its linters do not check either (`standards.md` § Comments);
  - Sass arithmetic in pixels is read in its output (`block-styles-guide.md`, template mode);
  - no database id in a theme file: a product collection picks its products by a property, and the pull request says what each environment must hold (`mapping-guide.md` § WooCommerce);
  - classes, custom properties and handles carry the theme slug (`project-template-guide.md` § Permanent identifiers).

## Page content

Page content, media and menus live in the database and reach other environments apart from the code.

- **Change existing content with a script** that replaces exact strings by count, refuses a page whose counts differ, keeps a revision, and runs dry on the dev site first, never on production (`project-template-guide.md` § Content and dependencies). Not with `write-page.sh`, which writes the whole page over what an editor changed since.
- **A new page** is written with `write-page.sh`, as in a run.
- **The pull request lists** each content change, the environments it still has to reach, and the data each environment must hold.

## Before calling it done

1. **Build.** In template mode, run `npm run build`, the whole build (`project-template-guide.md` § Build pipeline), and commit the built files with their sources.
2. **Audit, with the page content as the site holds it now:**

   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/export-pages.sh" --site-path "<site-path>"
   bash "${CLAUDE_PLUGIN_ROOT}/scripts/standards-audit.sh" --theme-dir "<theme-dir>" --content-dir "<site-path>/.h2bt/export"
   ```

   The export writes the block markup of every page and user pattern (`wp_block`, synced or not) to `<site-path>/.h2bt/export/`, and must end `H2BT_EXPORT_OK`. A run's `.h2bt/pages` holds what the run wrote, not what changed since. The audit must end `H2BT_AUDIT_OK`, or fail only on what it failed on before the change. `standards.md` says what each rule is for. With no Studio site, audit the theme alone and say that the page content was not audited.
3. **The repository's gates,** in template mode: `bash "${CLAUDE_PLUGIN_ROOT}/scripts/template-checks.sh" --repo <repo>` must end `H2BT_TEMPLATE_CHECKS_OK` (`project-template-guide.md` § Checks).
4. **Validate** each changed template, part and page with the Studio validator, and open each once in the editor: nothing missing, collapsed or unstyled (`visual-refinement.md` § The editor canvas).
5. **Look at it in a browser** at desktop width, one pixel either side of each breakpoint, the narrowest width and 1900px (`run.json` `widths`, where there is one):
   - no sideways overflow;
   - the largest image of the first screen is not `loading="lazy"`;
   - every hover and focus state the change touched, with no box changing size;
   - keyboard focus through the page, open menus and drawers included.
6. **Record what it taught.** What applies to this site goes in `<site-path>/.h2bt/lessons.md`. What applies to any site built with the plugin goes in `<site-path>/.h2bt/plugin-findings.md`, in the form the html-to-block-theme skill's Phase 4, step 5 gives: what was observed, how it was checked, and which plugin file it changes, naming neither the site nor a design value.

Pushing and opening a pull request wait for the user's approval.
