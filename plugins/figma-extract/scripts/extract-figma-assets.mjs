#!/usr/bin/env node
// Self-contained client for Figma's local Dev Mode MCP server (the HTTP
// server bundled with Figma desktop, default http://127.0.0.1:3845/mcp).
// Given the current Figma selection (or an explicit node id / URL) it:
//   1. opens an MCP session (initialize + notifications/initialized),
//   2. pulls the design context (code.tsx), variable defs, metadata, and a
//      screenshot,
//   3. parses the `const imgFoo = "http://localhost:3845/assets/<hash>.<ext>"`
//      declarations out of the design context and downloads each asset to
//      <out>/assets/, and
//   4. writes a manifest mapping each variable name -> downloaded file.
//
// Zero dependencies: Node 20+ built-ins only (global fetch / AbortController).
// This talks to the RAW MCP server over HTTP — it does not require the Figma
// MCP server to be registered inside Claude Code. It only requires Figma
// desktop to be running with Dev Mode MCP enabled.
//
// The MCP transport + asset-parsing logic is ported from the Neptune Ink app
// (source/integrations/figma/mcp.ts and assets-fetch.ts).

import {mkdir, writeFile, access} from 'node:fs/promises';
import {join, basename, resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {Buffer} from 'node:buffer';
import process from 'node:process';

const DEFAULT_MCP_URL = 'http://127.0.0.1:3845/mcp';
const PROTOCOL_VERSION = '2025-06-18';
const MCP_REQUEST_TIMEOUT_MS = 60_000;
const ASSET_TIMEOUT_MS = 30_000;
const PARALLEL_DOWNLOADS = 4;

// Anchored to start-of-line. Captures the const name AND the URL so each
// downloaded file can be mapped back to the variable that references it in
// the design context. Host/port are generalised (localhost or 127.0.0.1,
// any port) since the asset server shares the MCP server's port.
const ASSET_DECL_RE =
	/^const\s+(\w+)\s*=\s*["'](https?:\/\/(?:localhost|127\.0\.0\.1):\d+\/assets\/[^"']+)["']/gm;
const KEEP_EXT_RE = /\.(png|jpe?g|gif|webp|svg)$/i;
const SVG_EXT_RE = /\.svg$/i;

// Figma's MCP tools append guidance aimed at downstream LLMs (e.g. "SUPER
// CRITICAL: convert this React+Tailwind to your stack…"). Strip it so the
// saved files contain only the artifact. Markers are anchored to line start.
const LLM_INSTRUCTION_MARKERS = {
	'code.tsx': /^SUPER CRITICAL: The generated React/m,
	'metadata.xml': /^IMPORTANT: After you call this tool/m,
};

function parseArgs(argv) {
	const opts = {
		node: '',
		out: './figma-extract',
		url: process.env.FIGMA_MCP_URL ?? DEFAULT_MCP_URL,
		screenshot: true,
		// Images-only by default: download assets + screenshot, but don't write
		// the design-context files. Opt in with --context / --full.
		context: false,
		json: false,
	};
	for (let i = 0; i < argv.length; i++) {
		const arg = argv[i];
		switch (arg) {
			case '--node':
			case '-n':
				opts.node = argv[++i] ?? '';
				break;
			case '--out':
			case '-o':
				opts.out = argv[++i] ?? opts.out;
				break;
			case '--url':
				opts.url = argv[++i] ?? opts.url;
				break;
			case '--no-screenshot':
				opts.screenshot = false;
				break;
			case '--context':
			case '--full':
				// Also write code.tsx / variables.json / metadata.xml.
				opts.context = true;
				break;
			case '--json':
				opts.json = true;
				break;
			case '--help':
			case '-h':
				opts.help = true;
				break;
			default:
				// Bare positional is treated as the node ref for convenience.
				if (!arg.startsWith('-') && !opts.node) opts.node = arg;
		}
	}
	return opts;
}

const HELP = `Extract images and design context from the current Figma selection.

Usage: node extract-figma-assets.mjs [options]

Options:
  -n, --node <id|url>   Figma node id (e.g. 1:23 or 1-23) or a Figma URL.
                        Omit to use the current selection in Figma desktop.
  -o, --out <dir>       Output directory (default: ./figma-extract).
      --url <mcpUrl>    Override the MCP server URL
                        (default: $FIGMA_MCP_URL or ${DEFAULT_MCP_URL}).
      --no-screenshot   Skip the selection screenshot.
      --context, --full Also write the design context
                        (code.tsx / variables.json / metadata.xml). By default
                        only the images and screenshot are saved.
      --json            Print a machine-readable JSON summary to stdout.
  -h, --help            Show this help.

Requires Figma desktop running with Dev Mode MCP enabled.`;

function log(msg) {
	process.stderr.write(msg + '\n');
}

// ---------------------------------------------------------------------------
// MCP transport
// ---------------------------------------------------------------------------

async function fetchWithTimeout(url, init, timeoutMs) {
	const controller = new AbortController();
	const timer = setTimeout(
		() => controller.abort(new Error(`Request timed out after ${timeoutMs}ms`)),
		timeoutMs,
	);
	try {
		return await fetch(url, {...init, signal: controller.signal});
	} finally {
		clearTimeout(timer);
	}
}

async function initializeSession(url) {
	let initResp;
	try {
		initResp = await fetchWithTimeout(
			url,
			{
				method: 'POST',
				headers: {
					'Content-Type': 'application/json',
					Accept: 'application/json, text/event-stream',
					'MCP-Protocol-Version': PROTOCOL_VERSION,
				},
				body: JSON.stringify({
					jsonrpc: '2.0',
					id: 1,
					method: 'initialize',
					params: {
						protocolVersion: PROTOCOL_VERSION,
						capabilities: {},
						clientInfo: {name: 'figma-extract', version: '0.1'},
					},
				}),
			},
			MCP_REQUEST_TIMEOUT_MS,
		);
	} catch (err) {
		throw new Error(
			`Could not reach the Figma MCP server at ${url}. ` +
				'Is Figma desktop running with Dev Mode MCP enabled? ' +
				`(${err instanceof Error ? err.message : String(err)})`,
		);
	}

	if (initResp.status === 429) {
		throw new Error(`Figma rate limit (HTTP 429): ${await initResp.text()}`);
	}

	const sessionId = initResp.headers.get('mcp-session-id');
	const initText = await initResp.text();
	if (!sessionId) {
		throw new Error(
			'No Mcp-Session-Id returned. Is Figma desktop running with Dev Mode ' +
				`MCP enabled?\n${initText}`,
		);
	}

	await mcpCall(url, sessionId, {
		jsonrpc: '2.0',
		method: 'notifications/initialized',
	});

	return sessionId;
}

async function mcpCall(url, sessionId, payload) {
	const resp = await fetchWithTimeout(
		url,
		{
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				Accept: 'application/json, text/event-stream',
				'Mcp-Session-Id': sessionId,
				'MCP-Protocol-Version': PROTOCOL_VERSION,
			},
			body: JSON.stringify(payload),
		},
		MCP_REQUEST_TIMEOUT_MS,
	);

	if (resp.status === 429) {
		throw new Error(`Figma rate limit (HTTP 429): ${await resp.text()}`);
	}

	const text = await resp.text();
	if (payload.id === undefined) return undefined; // notification

	const ct = resp.headers.get('content-type') ?? '';
	if (ct.includes('text/event-stream') || /(^|\n)data: /.test(text)) {
		for (const line of text.split('\n')) {
			if (line.startsWith('data: ')) {
				return JSON.parse(line.slice('data: '.length));
			}
		}
	}
	return JSON.parse(text);
}

function openMcpSession(url) {
	let nextId = 1000;
	let sessionId;
	return {
		async open() {
			sessionId = await initializeSession(url);
		},
		async call(name, args) {
			return mcpCall(url, sessionId, {
				jsonrpc: '2.0',
				id: nextId++,
				method: 'tools/call',
				params: {name, arguments: args},
			});
		},
	};
}

// ---------------------------------------------------------------------------
// MCP response helpers
// ---------------------------------------------------------------------------

function toolContent(resp) {
	const result = resp?.result;
	if (typeof result !== 'object' || result === null) return [];
	const content = result.content;
	return Array.isArray(content) ? content : [];
}

function isToolError(resp) {
	const result = resp?.result;
	return (
		typeof result === 'object' && result !== null && result.isError === true
	);
}

function joinTextContent(resp) {
	return toolContent(resp)
		.filter(c => c.type === 'text' && typeof c.text === 'string')
		.map(c => c.text)
		.join('\n');
}

function stripLlmInstructions(file, text) {
	const marker = LLM_INSTRUCTION_MARKERS[file];
	if (!marker) return text;
	const match = marker.exec(text);
	if (!match) return text;
	const head = text.slice(0, match.index).replace(/\s+$/, '');
	return head === '' ? '' : head + '\n';
}

async function callText(session, tool, args) {
	const resp = await session.call(tool, args);
	if (resp?.error) {
		throw new Error(`MCP error ${resp.error.code}: ${resp.error.message}`);
	}
	if (isToolError(resp)) {
		throw new Error(`${tool} returned isError=true: ${joinTextContent(resp)}`);
	}
	return joinTextContent(resp);
}

// ---------------------------------------------------------------------------
// Asset parsing + download
// ---------------------------------------------------------------------------

function extractAssetRefs(code) {
	const seen = new Set();
	const out = [];
	for (const match of code.matchAll(ASSET_DECL_RE)) {
		const constName = match[1];
		const url = match[2];
		if (!constName || !url || seen.has(url)) continue;
		const pathname = new URL(url).pathname;
		if (!KEEP_EXT_RE.test(pathname)) continue;
		seen.add(url);
		out.push({
			constName,
			url,
			filename: basename(pathname),
			kind: SVG_EXT_RE.test(pathname) ? 'svg' : 'raster',
		});
	}
	return out;
}

async function fileExists(p) {
	try {
		await access(p);
		return true;
	} catch {
		return false;
	}
}

async function fetchAsset(url) {
	const resp = await fetchWithTimeout(url, {}, ASSET_TIMEOUT_MS);
	if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
	return Buffer.from(await resp.arrayBuffer());
}

async function downloadAssets(refs, assetsDir) {
	await mkdir(assetsDir, {recursive: true});
	let downloaded = 0;
	let skipped = 0;
	let failed = 0;
	const onDisk = new Map();

	let cursor = 0;
	const next = () => (cursor < refs.length ? refs[cursor++] : null);

	const worker = async () => {
		let ref;
		while ((ref = next())) {
			const outPath = join(assetsDir, ref.filename);
			if (await fileExists(outPath)) {
				skipped++;
				onDisk.set(ref.url, {...ref, path: outPath});
				continue;
			}
			try {
				await writeFile(outPath, await fetchAsset(ref.url));
				downloaded++;
				onDisk.set(ref.url, {...ref, path: outPath});
			} catch (err) {
				failed++;
				log(`  ! ${ref.filename}: ${err instanceof Error ? err.message : err}`);
			}
		}
	};

	await Promise.all(
		Array.from({length: Math.min(PARALLEL_DOWNLOADS, refs.length)}, worker),
	);

	const assets = refs.map(r => onDisk.get(r.url)).filter(Boolean);
	return {downloaded, skipped, failed, assets};
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
	const opts = parseArgs(process.argv.slice(2));
	if (opts.help) {
		process.stdout.write(HELP + '\n');
		return;
	}

	const outDir = resolve(opts.out);
	await mkdir(outDir, {recursive: true});

	// Mirror the Neptune app: pass nodeUrl for full URLs, nodeId for bare ids,
	// nothing for the current selection.
	const callArgs = !opts.node
		? {}
		: opts.node.startsWith('http')
			? {nodeUrl: opts.node}
			: {nodeId: opts.node};

	log(`Connecting to Figma MCP at ${opts.url}…`);
	const session = openMcpSession(opts.url);
	await session.open();

	log(
		opts.node
			? `Pulling design context for node ${opts.node}…`
			: 'Pulling design context for the current selection…',
	);
	const code = await callText(session, 'get_design_context', callArgs);

	if (opts.context) {
		const cleaned = stripLlmInstructions('code.tsx', code);
		await writeFile(join(outDir, 'code.tsx'), cleaned || code);

		for (const [tool, file] of [
			['get_variable_defs', 'variables.json'],
			['get_metadata', 'metadata.xml'],
		]) {
			try {
				const text = await callText(session, tool, callArgs);
				await writeFile(join(outDir, file), stripLlmInstructions(file, text));
			} catch (err) {
				log(`  ! ${file}: ${err instanceof Error ? err.message : err}`);
			}
		}
	}

	// Screenshot (base64 image content block).
	let screenshotPath;
	if (opts.screenshot) {
		try {
			const shotResp = await session.call('get_screenshot', callArgs);
			const imageBlock = toolContent(shotResp).find(c => c.type === 'image');
			if (imageBlock?.data) {
				screenshotPath = join(outDir, 'screenshot.png');
				await writeFile(screenshotPath, Buffer.from(imageBlock.data, 'base64'));
			} else {
				log('  ! No image content in screenshot response.');
			}
		} catch (err) {
			log(`  ! screenshot: ${err instanceof Error ? err.message : err}`);
		}
	}

	// Assets referenced by the design context.
	const refs = extractAssetRefs(code);
	let result = {downloaded: 0, skipped: 0, failed: 0, assets: []};
	if (refs.length > 0) {
		log(`Downloading ${refs.length} asset${refs.length === 1 ? '' : 's'}…`);
		result = await downloadAssets(refs, join(outDir, 'assets'));
	} else {
		log('No image assets referenced in the design context.');
	}

	const manifest = {
		node: opts.node || 'current-selection',
		out: outDir,
		generatedFrom: opts.url,
		screenshot: screenshotPath ? basename(screenshotPath) : null,
		counts: {
			referenced: refs.length,
			downloaded: result.downloaded,
			skipped: result.skipped,
			failed: result.failed,
			raster: result.assets.filter(a => a.kind === 'raster').length,
			svg: result.assets.filter(a => a.kind === 'svg').length,
		},
		assets: result.assets.map(a => ({
			constName: a.constName,
			filename: a.filename,
			kind: a.kind,
			url: a.url,
			path: join('assets', a.filename),
		})),
	};

	if (refs.length > 0) {
		await writeFile(
			join(outDir, 'assets', 'manifest.json'),
			JSON.stringify(manifest, null, 2) + '\n',
		);
	}

	const summary =
		`Done. ${result.downloaded} downloaded` +
		`${result.skipped ? `, ${result.skipped} cached` : ''}` +
		`${result.failed ? `, ${result.failed} failed` : ''}` +
		` (${manifest.counts.raster} raster, ${manifest.counts.svg} svg). ` +
		`Output: ${outDir}`;
	log(summary);

	if (opts.json) {
		process.stdout.write(JSON.stringify(manifest, null, 2) + '\n');
	}

	if (result.failed > 0) process.exitCode = 1;
}

// Exported for unit tests; the CLI body below only runs when executed directly.
export {extractAssetRefs, stripLlmInstructions};

const invokedDirectly =
	process.argv[1] &&
	import.meta.url === pathToFileURL(process.argv[1]).href;

if (invokedDirectly) {
	main().catch(err => {
		log(`Error: ${err instanceof Error ? err.message : String(err)}`);
		process.exitCode = 1;
	});
}
