# figma-extract

Extract images and design context from the **current Figma selection** straight
out of Figma desktop's local **Dev Mode MCP** server — no Figma API token, no
cloud round-trip.

Say to Claude:

> Extract images from my current Figma selection

…and the plugin connects to the local MCP server, downloads every referenced
image, and grabs a screenshot — into a folder on disk. (Pass `--context` if you
also want the generated code, variables, and metadata.)

## What it does

Given a selection (or an explicit node id / Figma URL), it writes to an output
directory (default `./figma-extract`). By default it saves **images only**; pass
`--context` (alias `--full`) to also save the design-context files.

| File | Contents | When |
| --- | --- | --- |
| `assets/*` | Every referenced image — PNG, JPG, GIF, WEBP, SVG — original filenames preserved. | always |
| `assets/manifest.json` | Maps each design-context variable (`constName`) → downloaded filename, kind (`raster`/`svg`), source URL, and relative path. | always |
| `screenshot.png` | A render of the selection. | unless `--no-screenshot` |
| `code.tsx` | The Figma-generated reference code (trailing LLM-instruction text stripped). | `--context` |
| `variables.json` | Published Figma variables for the selection. | `--context` |
| `metadata.xml` | The node's structural metadata. | `--context` |

How it works: the bundled `scripts/extract-figma-assets.mjs` opens an MCP session
to `http://127.0.0.1:3845/mcp`, calls `get_design_context` / `get_variable_defs`
/ `get_metadata` / `get_screenshot`, parses the
`const imgFoo = "http://localhost:3845/assets/…"` declarations out of the
returned code, and downloads each asset (4 in parallel, with per-asset timeouts
and a cache check so re-runs are cheap).

## Requirements

- **Figma desktop** running with **Dev Mode MCP enabled**
  (Figma → Preferences → *Enable Dev Mode MCP server*).
- A frame/node **selected** in Figma (or pass a node id / URL).
- **Node.js 20+** on `PATH`.

No npm install — the script uses only Node built-ins.

## Usage

### Natural language (skill)

> Extract the assets from this Figma frame into `./design/home`

### Slash command

```
/figma-extract:extract                         # current selection → ./figma-extract
/figma-extract:extract 1:23 --out ./design     # a specific node
/figma-extract:extract https://figma.com/design/…?node-id=1-2
```

### Directly

```bash
node scripts/extract-figma-assets.mjs --help
node scripts/extract-figma-assets.mjs --out ./figma-extract --json   # images only
node scripts/extract-figma-assets.mjs --node 1:23 --context          # + design context
```

| Flag | Effect |
| --- | --- |
| `-n, --node <id\|url>` | Target a specific node instead of the current selection. |
| `-o, --out <dir>` | Output directory (default `./figma-extract`). |
| `--url <mcpUrl>` | Override the MCP URL (default `$FIGMA_MCP_URL` or `http://127.0.0.1:3845/mcp`). |
| `--no-screenshot` | Skip the screenshot. |
| `--context`, `--full` | Also write `code.tsx` / `variables.json` / `metadata.xml`. Off by default (images only). |
| `--json` | Print the manifest as JSON to stdout. |

The script exits non-zero only if one or more downloads fail. A selection that
references no placed images is a success — the screenshot and design context are
still saved.

## Credits

The MCP transport and asset-parsing logic are ported from Automattic Special
Projects' Neptune Figma-to-WordPress tool.
