---
description: Extract images and design context from the current Figma selection (or a given node id / URL) over Figma desktop's local Dev Mode MCP, into a local folder.
argument-hint: [node-id|figma-url] [--out <dir>] [--context]
allowed-tools: Bash
---

# /figma-extract:extract

Extract the images, screenshot, and design context for a Figma selection by
running the bundled, zero-dependency extractor. All MCP transport, asset
parsing, and downloading is delegated to
`${CLAUDE_PLUGIN_ROOT}/scripts/extract-figma-assets.mjs` — do **not** reimplement
it or call the Figma MCP tools yourself. This command mirrors the
`extract-figma-assets` skill; the skill's body has the full reference.

## Inputs

Parse `$ARGUMENTS` (all optional):

- A bare **node id** (`1:23` / `1-23`) or a **Figma URL** (contains
  `?node-id=…`) → pass as `--node <value>`. If absent, the script uses the
  **current selection** in Figma desktop.
- `--out <dir>` → output directory. If the user didn't specify one, default to
  `./figma-extract`.
- The script saves **images + screenshot only** by default. Pass `--context`
  (alias `--full`) through to the script only if the user also asks for the
  generated code, variables, or metadata.

## Run

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/extract-figma-assets.mjs" \
  [--node <id|url>] --out <dir> --json
```

Progress goes to stderr; a JSON manifest is printed to stdout.

## Report

Summarise from the JSON manifest: number of assets downloaded (raster/svg split),
any cached/failed counts, the absolute output path, and the image filenames.

If the script reports `Nothing is selected`, tell the user to select a frame in
Figma desktop (or pass a node id / URL) and re-run — do not retry blindly. If
`counts.referenced` is `0`, say the selection referenced no placed images; the
screenshot and design context were still saved.

Requires Figma desktop running with **Dev Mode MCP enabled** and Node.js 20+.
