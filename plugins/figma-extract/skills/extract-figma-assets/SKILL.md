---
name: extract-figma-assets
description: Use when the user wants to extract images, assets, or design context from a Figma selection — e.g. "extract images from my current Figma selection", "pull the assets out of this Figma frame", "download the images from this Figma design", "grab the design context for this node". Connects directly to Figma desktop's local Dev Mode MCP server, downloads every referenced image (PNG/JPG/GIF/WEBP/SVG) plus a screenshot, and saves the design context to a local folder.
---

# Extract images & design context from Figma

This skill pulls the assets and design context for a Figma selection out of Figma
desktop's **local Dev Mode MCP server** (the HTTP server at
`http://127.0.0.1:3845/mcp`) and writes them to a folder on disk.

A bundled, zero-dependency Node script (`scripts/extract-figma-assets.mjs`) owns
the whole flow: it opens an MCP session, calls `get_design_context`,
`get_variable_defs`, `get_metadata`, and `get_screenshot`, parses the
`const imgFoo = "http://localhost:3845/assets/<hash>.<ext>"` declarations out of
the returned code, and downloads each asset. Do **not** reimplement any of this
by hand or by calling the MCP tools yourself — just run the script and report
what it produced.

## Prerequisites

- **Figma desktop must be running** with **Dev Mode MCP enabled**
  (Figma → Preferences → "Enable Dev Mode MCP server"), and
- the user must have **selected the frame/node** they want extracted (unless
  they give you an explicit node id or Figma URL).
- **Node.js 20+** must be on `PATH`.

If the script reports `Nothing is selected`, tell the user to select a frame in
Figma desktop (or pass a node id / URL) and try again — don't retry blindly.

## How to run it

Run the script with Bash. Use `${CLAUDE_PLUGIN_ROOT}` so the path resolves
regardless of where the plugin is installed:

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/extract-figma-assets.mjs" --out <dir> --json
```

Decide the arguments from what the user asked:

- **Current selection (default):** pass no `--node`. This is the right choice
  for "extract images from my *current* selection".
- **Specific node:** if the user pastes a Figma URL (e.g. one containing
  `?node-id=1-2`) or a node id like `1:23`, pass it with `--node <id|url>`.
- **Output directory:** default to `./figma-extract` in the current working
  directory. If the user names a destination (e.g. "into ./assets"), pass it via
  `--out`. Mention the resolved path in your summary.
- **Design context:** by default the script saves **images only** (assets +
  screenshot). Only pass `--context` (alias `--full`) if the user also wants the
  design-context files (`code.tsx` / `variables.json` / `metadata.xml`) — e.g.
  they mention variables, tokens, the generated code, or "everything".
- Always pass `--json` so you get a machine-readable manifest on stdout to
  summarise from. Progress lines go to stderr.

Other flags: `--no-screenshot` (skip the screenshot), `--url <mcpUrl>` (override
the MCP server URL — rarely needed).

## What lands on disk

In the output directory:

- `assets/` — every downloaded image, original filename preserved.
- `assets/manifest.json` — maps each `constName` from the design context to its
  downloaded `filename`, `kind` (`raster` | `svg`), source `url`, and relative
  `path`. This is the same JSON printed to stdout with `--json`.
- `screenshot.png` — a render of the selection (unless `--no-screenshot`).
- `code.tsx`, `variables.json`, `metadata.xml` — the design context, written
  **only when `--context` / `--full` is passed**. Figma's trailing
  LLM-instruction text is stripped from `code.tsx` and `metadata.xml`.

Note: the script always calls `get_design_context` internally regardless of this
flag — that response is where the image URLs come from — but it only *writes*
those files when asked.

## Reporting back

Parse the `--json` manifest and give the user a short summary:

- how many assets were downloaded (and the raster/svg split), plus any cached or
  failed counts;
- the absolute output path;
- the list of image filenames (or a count if there are many).

If `counts.referenced` is `0`, say plainly that the selection referenced no image
assets — the design may use only vectors/shapes drawn inline rather than placed
images. The screenshot is still saved (and the design context too, if `--context`
was passed), so point the user at those.

The script exits non-zero only when one or more downloads failed; a clean run
with zero referenced assets is success, not an error.
