# Changelog

## [0.1.0] - 2026-06-15

### Added
- Initial release.
- `extract-figma-assets` skill (natural language) and `/figma-extract:extract`
  command for pulling images and design context out of the current Figma
  selection.
- Self-contained, zero-dependency `scripts/extract-figma-assets.mjs` MCP client
  (Node 20+). Opens a session to Figma desktop's local Dev Mode MCP server,
  pulls `get_design_context` / `get_variable_defs` / `get_metadata` /
  `get_screenshot`, parses the `const imgFoo = "http://localhost:3845/assets/…"`
  declarations out of the returned code, and downloads each referenced asset
  (PNG/JPG/GIF/WEBP/SVG) in parallel with per-asset timeouts and a cache check.
- Writes `assets/`, `assets/manifest.json` (constName → file mapping with
  raster/svg classification), and `screenshot.png` by default (images only).
  Pass `--context` / `--full` to additionally write the design context
  (`code.tsx` / `variables.json` / `metadata.xml`) with Figma's trailing
  LLM-instruction text stripped. Supports `--node`, `--out`, `--url`,
  `--no-screenshot`, `--context` / `--full`, and `--json`.
- MCP transport and asset-parsing logic ported from Automattic Special Projects'
  Neptune Figma-to-WordPress tool.
