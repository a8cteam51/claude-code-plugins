#!/usr/bin/env node
// Read a Figma .fig export without Figma: list its pages and frames, and extract
// one node as a plain JSON tree with its images, vectors, tokens and designer notes.
//
// The .fig format is undocumented. Everything here was worked out against real
// files (fig-kiwi version 106); a newer Figma may change field meanings.
// Node 22.15+ (zstd in node:zlib). No npm dependencies. Needs `unzip` on PATH
// when given a .fig file rather than an unpacked folder.

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import zlib from 'node:zlib';
import crypto from 'node:crypto';
import { execFileSync } from 'node:child_process';

// ---------------------------------------------------------------- kiwi decoding

const utf8 = new TextDecoder();
const f32 = new Float32Array(1);
const i32 = new Int32Array(f32.buffer);

class Reader {
	constructor(bytes) {
		this.b = bytes;
		this.i = 0;
	}
	byte() {
		return this.b[this.i++];
	}
	varUint() {
		let value = 0;
		let shift = 0;
		let byte;
		do {
			byte = this.b[this.i++];
			value |= (byte & 127) << shift;
			shift += 7;
		} while (byte & 128 && shift < 35);
		return value >>> 0;
	}
	varInt() {
		const v = this.varUint();
		return v & 1 ? ~(v >>> 1) : v >>> 1;
	}
	varFloat() {
		const b = this.b;
		const i = this.i;
		if (b[i] === 0) {
			this.i++;
			return 0;
		}
		let bits = b[i] | (b[i + 1] << 8) | (b[i + 2] << 16) | (b[i + 3] << 24);
		this.i += 4;
		bits = (bits << 23) | (bits >>> 9);
		i32[0] = bits;
		return f32[0];
	}
	string() {
		let end = this.i;
		while (this.b[end] !== 0) end++;
		const s = utf8.decode(this.b.subarray(this.i, end));
		this.i = end + 1;
		return s;
	}
	varUint64() {
		let value = 0n;
		let shift = 0n;
		let byte;
		while ((byte = this.b[this.i++]) & 128 && shift < 56n) {
			value |= BigInt(byte & 127) << shift;
			shift += 7n;
		}
		return value | (BigInt(byte) << shift);
	}
	varInt64() {
		const v = this.varUint64();
		return v & 1n ? ~(v >> 1n) : v >> 1n;
	}
	bytes() {
		const n = this.varUint();
		const out = this.b.slice(this.i, this.i + n);
		this.i += n;
		return out;
	}
}

const BUILTIN = ['bool', 'byte', 'int', 'uint', 'float', 'string', 'int64', 'uint64'];
const KINDS = ['ENUM', 'STRUCT', 'MESSAGE'];

function decodeSchema(bytes) {
	const r = new Reader(bytes);
	const defs = [];
	const count = r.varUint();
	for (let d = 0; d < count; d++) {
		const name = r.string();
		const kind = KINDS[r.byte()];
		const fields = [];
		const fieldCount = r.varUint();
		for (let f = 0; f < fieldCount; f++) {
			fields.push({ name: r.string(), type: r.varInt(), isArray: !!(r.byte() & 1), value: r.varUint() });
		}
		defs.push({ name, kind, fields });
	}
	return defs;
}

// One decoder closure per definition, built lazily because definitions refer to each other.
function compile(defs) {
	const decoders = new Array(defs.length);
	const scalar = (type) => {
		if (type >= 0) return (r) => decoders[type](r);
		switch (BUILTIN[~type]) {
			case 'bool':
				return (r) => !!r.byte();
			case 'byte':
				return (r) => r.byte();
			case 'int':
				return (r) => r.varInt();
			case 'uint':
				return (r) => r.varUint();
			case 'float':
				return (r) => r.varFloat();
			case 'string':
				return (r) => r.string();
			case 'int64':
				return (r) => r.varInt64();
			case 'uint64':
				return (r) => r.varUint64();
			default:
				throw new Error(`Unknown kiwi type ${type}`);
		}
	};
	const reader = (field) => {
		if (field.isArray && field.type < 0 && BUILTIN[~field.type] === 'byte') return (r) => r.bytes();
		const one = scalar(field.type);
		if (!field.isArray) return one;
		return (r) => {
			const n = r.varUint();
			const out = new Array(n);
			for (let i = 0; i < n; i++) out[i] = one(r);
			return out;
		};
	};
	defs.forEach((def, index) => {
		if (def.kind === 'ENUM') {
			const names = new Map(def.fields.map((f) => [f.value, f.name]));
			decoders[index] = (r) => names.get(r.varUint());
		} else if (def.kind === 'STRUCT') {
			let fields;
			decoders[index] = (r) => {
				fields ??= def.fields.map((f) => [f.name, reader(f)]);
				const out = {};
				for (const [name, read] of fields) out[name] = read(r);
				return out;
			};
		} else {
			let fields;
			decoders[index] = (r) => {
				fields ??= new Map(def.fields.map((f) => [f.value, [f.name, reader(f)]]));
				const out = {};
				for (;;) {
					const id = r.varUint();
					if (id === 0) return out;
					const field = fields.get(id);
					if (!field) throw new Error(`Unknown field ${id} in ${def.name}`);
					out[field[0]] = field[1](r);
				}
			};
		}
	});
	const message = defs.findIndex((d) => d.name === 'Message');
	if (message < 0) throw new Error('The file has no Message definition.');
	return (bytes) => decoders[message](new Reader(bytes));
}

export function decodeCanvas(buf) {
	const magic = buf.subarray(0, 8).toString('latin1');
	if (!magic.startsWith('fig-')) throw new Error(`Not a Figma canvas: starts with "${magic}".`);
	const version = buf.readUInt32LE(8);
	const chunks = [];
	for (let o = 12; o + 4 <= buf.length; ) {
		const n = buf.readUInt32LE(o);
		o += 4;
		chunks.push(buf.subarray(o, o + n));
		o += n;
	}
	if (chunks.length < 2) throw new Error('Expected a schema chunk and a data chunk.');
	const unpack = (b) =>
		b[0] === 0x28 && b[1] === 0xb5 && b[2] === 0x2f && b[3] === 0xfd ? zlib.zstdDecompressSync(b) : zlib.inflateRawSync(b);
	if (typeof zlib.zstdDecompressSync !== 'function') throw new Error('Node 22.15 or later is required (zstd).');
	const schema = decodeSchema(new Uint8Array(unpack(chunks[0])));
	const message = compile(schema)(new Uint8Array(unpack(chunks[1])));
	return { magic, version, schema, message };
}

// ---------------------------------------------------------------- loading

function load(input) {
	const stat = fs.statSync(input);
	let dir = null;
	let zip = null;
	let canvasPath;
	if (stat.isDirectory()) {
		dir = input;
		canvasPath = path.join(dir, 'canvas.fig');
	} else {
		const head = Buffer.alloc(8);
		const fd = fs.openSync(input, 'r');
		fs.readSync(fd, head, 0, 8, 0);
		fs.closeSync(fd);
		if (head.toString('latin1').startsWith('fig-')) {
			canvasPath = input; // an old-style .fig that is the bare canvas, with no images inside
		} else {
			zip = input;
			const tag = crypto.createHash('sha1').update(`${path.resolve(input)}:${stat.size}:${stat.mtimeMs}`).digest('hex').slice(0, 16);
			dir = path.join(os.tmpdir(), `fig-to-html-${tag}`);
			canvasPath = path.join(dir, 'canvas.fig');
			if (!fs.existsSync(canvasPath)) {
				fs.mkdirSync(dir, { recursive: true });
				execFileSync('unzip', ['-o', '-q', zip, 'canvas.fig', 'meta.json', '-d', dir]);
			}
		}
	}
	const { version, message } = decodeCanvas(fs.readFileSync(canvasPath));
	let meta = {};
	try {
		meta = JSON.parse(fs.readFileSync(path.join(dir ?? '', 'meta.json'), 'utf8'));
	} catch {}
	return new Fig({ version, message, dir, zip, meta });
}

const gid = (g) => (g && g.sessionID !== 0xffffffff ? `${g.sessionID}:${g.localID}` : null);

class Fig {
	constructor({ version, message, dir, zip, meta }) {
		Object.assign(this, { version, dir, zip, meta });
		this.blobs = message.blobs || [];
		this.nodes = (message.nodeChanges || []).filter((n) => n.phase !== 'REMOVED');
		this.byId = new Map(this.nodes.map((n) => [gid(n.guid), n]));
		this.byKey = new Map(this.nodes.filter((n) => n.key).map((n) => [n.key, n]));
		this.kids = new Map();
		for (const n of this.nodes) {
			const p = gid(n.parentIndex?.guid);
			if (!p) continue;
			if (!this.kids.has(p)) this.kids.set(p, []);
			this.kids.get(p).push(n);
		}
		for (const list of this.kids.values())
			list.sort((a, b) => (a.parentIndex.position < b.parentIndex.position ? -1 : a.parentIndex.position > b.parentIndex.position ? 1 : 0));
		this.document = this.nodes.find((n) => n.type === 'DOCUMENT');
		this.categories = new Map(
			(this.document?.annotationCategories?.items || []).map((c) => [gid(c.id), c.custom?.label || titleCase(c.preset)])
		);
	}
	children(n) {
		return this.kids.get(gid(n.guid)) || [];
	}
	parent(n) {
		return this.byId.get(gid(n.parentIndex?.guid));
	}
	page(n) {
		let p = n;
		while (p && p.type !== 'CANVAS') p = this.parent(p);
		return p;
	}
	// Figma keeps copies of library components on a hidden page; they are not the designer's frames.
	isInternal(page) {
		return !page || page.internalOnly === true || page.name === 'Internal Only Canvas';
	}
	pages() {
		return this.nodes.filter((n) => n.type === 'CANVAS' && !this.isInternal(n));
	}
	symbolOf(n) {
		return this.byId.get(gid(n.overriddenSymbolID) || gid(n.symbolData?.symbolID));
	}
	// A variant is named "Property=Value" and lives in a state group that carries the component's name.
	componentName(sym) {
		const parent = sym && this.parent(sym);
		return parent?.isStateGroup ? `${parent.name} (${sym.name})` : sym?.name;
	}
	style(ref) {
		if (!ref) return null;
		return this.byId.get(gid(ref.guid)) || (ref.assetRef && this.byKey.get(ref.assetRef.key)) || null;
	}
	variable(alias) {
		if (!alias) return null;
		return this.byId.get(gid(alias.guid)) || (alias.assetRef && this.byKey.get(alias.assetRef.key)) || null;
	}
}

// ---------------------------------------------------------------- small helpers

const titleCase = (s) => (s ? s.charAt(0) + s.slice(1).toLowerCase().replace(/_/g, ' ') : '');
const round = (n, p = 2) => (typeof n === 'number' ? Math.round(n * 10 ** p) / 10 ** p : n);
const slug = (s, max = 40) =>
	(s || 'node')
		.normalize('NFKD')
		.replace(/[^\w\s-]/g, '')
		.trim()
		.replace(/[\s_-]+/g, '-')
		.toLowerCase()
		.slice(0, max)
		.replace(/-+$/, '') || 'node';
const hex2 = (v) =>
	Math.round(Math.min(1, Math.max(0, v)) * 255)
		.toString(16)
		.padStart(2, '0');
const hexColor = (c) => `#${hex2(c.r)}${hex2(c.g)}${hex2(c.b)}`;
const cssColor = (c, opacity = 1) => {
	const a = round((c.a ?? 1) * opacity, 3);
	return a >= 1 ? hexColor(c) : `rgba(${Math.round(c.r * 255)}, ${Math.round(c.g * 255)}, ${Math.round(c.b * 255)}, ${a})`;
};
const isRotated = (t) => t && (Math.abs(t.m01) > 1e-4 || Math.abs(t.m10) > 1e-4);
const IDENTITY = { m00: 1, m01: 0, m02: 0, m10: 0, m11: 1, m12: 0 };
const multiply = (a, b) => ({
	m00: a.m00 * b.m00 + a.m01 * b.m10,
	m01: a.m00 * b.m01 + a.m01 * b.m11,
	m02: a.m00 * b.m02 + a.m01 * b.m12 + a.m02,
	m10: a.m10 * b.m00 + a.m11 * b.m10,
	m11: a.m10 * b.m01 + a.m11 * b.m11,
	m12: a.m10 * b.m02 + a.m11 * b.m12 + a.m12,
});
const htmlToText = (html) =>
	(html || '')
		.replace(/<a [^>]*href="([^"]*)"[^>]*>(.*?)<\/a>/g, (m, url, text) => (text === url ? url : `${text} (${url})`))
		.replace(/<\/(p|li|h\d)>/g, '\n')
		.replace(/<br\s*\/?>/g, '\n')
		.replace(/<[^>]+>/g, '')
		.replace(/&amp;/g, '&')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&nbsp;/g, ' ')
		.replace(/\n{2,}/g, '\n')
		.trim();

const SHAPES = new Set(['VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'LINE', 'ELLIPSE', 'REGULAR_POLYGON', 'RECTANGLE', 'ROUNDED_RECTANGLE']);
const DRAWN = new Set(['VECTOR', 'BOOLEAN_OPERATION', 'STAR', 'REGULAR_POLYGON']);
const CONTAINERS = new Set(['FRAME', 'GROUP', 'SYMBOL', 'INSTANCE', 'SECTION']);

// ---------------------------------------------------------------- instance expansion

// A node as it is drawn: instances are replaced by their component's children with
// every override applied. `v` is the merged node, `kids` its resolved children.
function resolveTree(fig, root) {
	const stats = { instances: 0, unresolvedInstances: 0, hidden: 0 };
	const strip = ({ guidPath, guidPathTag, ...rest }) => rest;

	const scopeFor = (inst) => {
		const index = (list) => {
			const map = new Map();
			for (const o of list || []) if (o.guidPath?.guids?.length) map.set(o.guidPath.guids.map(gid).join('/'), o);
			return map;
		};
		// A property's value is written in an older form (value) and a newer one (varValue); a file can hold either or both.
		const assign = new Map();
		for (const a of inst.componentPropAssignments || []) {
			const now = a.varValue?.value || {};
			assign.set(gid(a.defID), {
				text: a.value?.textValue ?? now.textDataValue,
				bool: a.value?.boolValue ?? now.boolValue,
				symbol: a.value?.guidValue ?? now.symbolIdValue?.guid,
				slot: now.slotContentIdValue?.guid,
			});
		}
		return { overrides: index(inst.symbolData?.symbolOverrides), derived: index(inst.derivedSymbolData), assign, prefix: [] };
	};

	// Overrides address a node by its overrideKey when it has one and by its guid otherwise; some files mix both.
	const lookup = (map, prefix, node) => {
		const base = prefix.length ? `${prefix.join('/')}/` : '';
		return map.get(base + (gid(node.overrideKey) || gid(node.guid))) || map.get(base + gid(node.guid));
	};

	// Which component property drives which field of a node, again in an older and a newer form.
	const propRefs = (node) => {
		const refs = new Map();
		for (const r of node.componentPropRefs || []) if (!r.isDeleted) refs.set(r.componentPropNodeField, gid(r.defID));
		for (const e of node.parameterConsumptionMap?.entries || []) {
			const def = e.variableData?.value?.propRefValue?.defId;
			if (def) refs.set(e.variableField, gid(def));
		}
		return refs;
	};

	const visit = (node, scopes, idPath, depth) => {
		let v = node;
		let slot = null;
		if (scopes.length) {
			v = { ...node };
			const own = scopes[scopes.length - 1]; // the instance whose component this node belongs to
			for (const [field, def] of propRefs(node)) {
				const value = own.assign.get(def);
				if (!value) continue;
				if (field === 'VISIBLE' && value.bool !== undefined) v.visible = !!value.bool;
				else if (field === 'TEXT_DATA' && value.text) v.textData = { ...v.textData, ...value.text };
				else if (field === 'OVERRIDDEN_SYMBOL_ID' && value.symbol) v.overriddenSymbolID = value.symbol;
				else if (field === 'SLOT_CONTENT_ID' && value.slot) {
					slot = fig.byId.get(gid(value.slot)) || null;
					if (!slot) stats.unresolvedInstances++; // the placeholder's content is what gets shown, which is not what was drawn
				}
			}
			// A filled slot: the instance's own frame stands in for the component's placeholder, in the placeholder's place.
			if (slot) v = { ...v, ...slot, guid: node.guid, overrideKey: node.overrideKey, parentIndex: node.parentIndex, name: node.name, size: node.size, transform: node.transform };
			// Inner instances first, so an outer instance's override wins; computed layout goes on last.
			let assigned = v.componentPropAssignments || [];
			for (let s = scopes.length - 1; s >= 0; s--) {
				const o = lookup(scopes[s].overrides, scopes[s].prefix, node);
				if (!o) continue;
				if (o.componentPropAssignments) assigned = assigned.concat(o.componentPropAssignments);
				Object.assign(v, strip(o));
			}
			if (assigned.length) v.componentPropAssignments = assigned;
			for (let s = scopes.length - 1; s >= 0; s--) {
				const d = lookup(scopes[s].derived, scopes[s].prefix, node);
				if (d) Object.assign(v, strip(d));
			}
		}
		const id = idPath.length ? `I${[...idPath, gid(node.guid)].join(';')}` : gid(node.guid);
		const out = { v, id, kids: [] };
		if (v.visible === false) {
			stats.hidden++;
			return null;
		}
		let source = slot || node;
		let childScopes = scopes;
		let childPath = idPath;
		if (v.type === 'INSTANCE') {
			const sym = fig.symbolOf(v);
			if (!sym || depth > 40) {
				stats.unresolvedInstances++;
				return out;
			}
			stats.instances++;
			out.component = fig.componentName(sym);
			out.symbol = sym;
			// The instance's own fields win; what it does not carry comes from its component.
			out.v = v = { ...sym, ...v, type: 'INSTANCE', name: v.name };
			const key = gid(node.overrideKey) || gid(node.guid);
			childScopes = scopes.map((s) => ({ ...s, prefix: [...s.prefix, key] })).concat(scopeFor(v));
			childPath = [...idPath, gid(node.guid)];
			source = sym;
		}
		for (const child of fig.children(source)) {
			const resolved = visit(child, childScopes, childPath, depth + 1);
			if (resolved) out.kids.push(resolved);
		}
		return out;
	};

	const tree = visit(root, [], [], 0);
	return { tree, stats };
}

// ---------------------------------------------------------------- the tree as text

// Every layer on one line, with the values a page is built from. The same facts as node.json at about a quarter of the size.
function layersText(tree) {
	const paint = (p) => (p.color ? p.color + (p.opacity !== undefined ? `@${p.opacity}` : '') : p.image ? `image(${p.image}${p.fit ? ` ${p.fit}` : ''})` : p.video ? `video(${p.video})` : p.gradient ? `${p.gradient}(${(p.stops || []).join(', ')}${p.angle !== undefined ? ` ${p.angle}deg` : ''})` : JSON.stringify(p));
	const face = (t) => [t.font, t.size !== undefined || t.lineHeight !== undefined ? `${t.size ?? ''}/${t.lineHeight ?? ''}` : '', t.letterSpacing ? `spacing=${t.letterSpacing}` : '', t.case, t.decoration].filter(Boolean).join(' ');
	const lines = [
		'One line per layer: TYPE "name" x,y WxH, then only what applies.',
		'size=<width>/<height> (fixed, hug, fill) | [direction gap pad=top,right,bottom,left justify align wrap] | absolute clip mask flip rotation opacity blend | fill stroke radius shadow | svg | <component> | text{font size/lineHeight …} lines "characters" (⏎ is a line the designer broke by hand)',
		'',
	];
	const walk = (n, depth) => {
		const bits = [`${'  '.repeat(depth)}${n.type === 'SYMBOL' ? 'COMPONENT' : n.type} "${n.name}" ${n.x},${n.y} ${n.w}x${n.h}`];
		if (n.sizing) bits.push(`size=${n.sizing.w}/${n.sizing.h}`);
		if (n.layout) {
			const l = n.layout;
			bits.push(`[${[l.direction, l.gap !== undefined ? `gap=${l.gap}` : '', l.counterGap !== undefined ? `rowGap=${l.counterGap}` : '', l.padding ? `pad=${l.padding.join(',')}` : '', l.justify ? `justify=${l.justify}` : '', l.align ? `align=${l.align}` : '', l.wrap ? 'wrap' : ''].filter(Boolean).join(' ')}]`);
		}
		for (const key of ['absolute', 'clip', 'mask']) if (n[key]) bits.push(key);
		for (const key of ['flip', 'rotation', 'opacity', 'blend', 'alignSelf', 'minW', 'maxW', 'minH', 'maxH']) if (n[key] !== undefined && n[key] !== null) bits.push(`${key}=${n[key]}`);
		if (n.fills?.length) bits.push(`fill=${n.fills.map(paint).join(' + ')}`);
		if (n.stroke) bits.push(`stroke=${(n.stroke.paints || []).map(paint).join(' + ')} ${n.stroke.weight}px ${n.stroke.align || ''}${n.stroke.dash ? ` dash=${n.stroke.dash.join(',')}` : ''}`.trim());
		if (n.radius !== undefined) bits.push(`radius=${Array.isArray(n.radius) ? n.radius.join(',') : n.radius}`);
		for (const e of n.effects || []) bits.push(e.type.includes('shadow') ? `${e.type}=${e.x} ${e.y} ${e.blur} ${e.spread} ${e.color}` : `${e.type}=${e.blur ?? e.radius ?? ''}`);
		if (n.svg) bits.push(`svg=${n.svg}${n.svgBox ? ` drawn=${n.svgBox.x},${n.svgBox.y} ${n.svgBox.w}x${n.svgBox.h}` : ''}`);
		if (n.component) bits.push(`<${n.component}>`);
		if (n.designerNote) bits.push('[designer note]');
		if (n.text) {
			const t = n.text;
			const extra = [t.align, t.valign ? `valign=${t.valign}` : '', t.style ? `style="${t.style}"` : '', t.link ? `link=${t.link}` : '', t.list ? `list=${t.list}` : ''].filter(Boolean).join(' ');
			bits.push(`text{${face(t)}${extra ? ` ${extra}` : ''}}${t.lines ? ` ${t.lines} line${t.lines > 1 ? 's' : ''}` : ''} ${JSON.stringify(t.characters.replace(/\n/g, '⏎'))}`);
			for (const r of t.runs || []) {
				const how = [face(r), r.fills ? `fill=${r.fills.map(paint).join(' + ')}` : '', r.link ? `link=${r.link}` : '', r.style ? `style="${r.style}"` : ''].filter(Boolean).join(' ');
				if (how && r.text.trim()) bits.push(`run ${JSON.stringify(r.text)}={${how}}`);
			}
		}
		lines.push(bits.join(' '));
		for (const child of n.children || []) walk(child, depth + 1);
	};
	walk(tree, 0);
	return `${lines.join('\n')}\n`;
}

// ---------------------------------------------------------------- vectors to SVG

// A geometry blob is a run of commands: 0 close, 1 move, 2 line, 3 quadratic, 4 cubic, each followed by its float32 coordinates.
function pathData(fig, blobIndex, onPoint) {
	const bytes = fig.blobs[blobIndex]?.bytes;
	if (!bytes) return '';
	const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
	const out = [];
	const LETTER = { 1: 'M', 2: 'L', 3: 'Q', 4: 'C' };
	const PAIRS = { 1: 1, 2: 1, 3: 2, 4: 3 };
	for (let o = 0; o < bytes.length; ) {
		const cmd = bytes[o++];
		if (cmd === 0) {
			out.push('Z');
			continue;
		}
		if (!PAIRS[cmd]) throw new Error(`Unknown path command ${cmd}`);
		const numbers = [];
		for (let i = 0; i < PAIRS[cmd]; i++, o += 8) {
			const x = view.getFloat32(o, true);
			const y = view.getFloat32(o + 4, true);
			onPoint?.(x, y);
			numbers.push(round(x, 3), round(y, 3));
		}
		out.push(LETTER[cmd] + numbers.join(' '));
	}
	return out.join('');
}

const hasPaintType = (v, test) => [...(v.fillPaints || []), ...(v.strokePaints || [])].some((p) => p.visible !== false && test(p.type));

// A subtree is exported as one SVG when it is only shapes and at least one of them is a drawn path.
function isArtwork(t) {
	let drawn = false;
	const walk = (n) => {
		const v = n.v;
		if (v.mask || hasPaintType(v, (type) => type === 'IMAGE' || type === 'VIDEO')) return false;
		if (DRAWN.has(v.type)) drawn = true;
		else if (!SHAPES.has(v.type) && !CONTAINERS.has(v.type)) return false;
		if (v.type === 'BOOLEAN_OPERATION') return true;
		return n.kids.every(walk);
	};
	return walk(t) && drawn;
}

// Where a linear gradient starts and ends, in the node's own pixel space.
function gradientLine(paint, size) {
	const t = paint.transform || IDENTITY;
	const det = t.m00 * t.m11 - t.m01 * t.m10 || 1;
	const inv = (x, y) => ({
		x: ((t.m11 * (x - t.m02) - t.m01 * (y - t.m12)) / det) * size.x,
		y: ((-t.m10 * (x - t.m02) + t.m00 * (y - t.m12)) / det) * size.y,
	});
	return { from: inv(0, 0.5), to: inv(1, 0.5) };
}

function toSvg(fig, t) {
	const defs = [];
	const body = [];
	const bounds = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
	const paintAttr = (paint, v) => {
		if (paint.type === 'SOLID') {
			const a = round((paint.color.a ?? 1) * (paint.opacity ?? 1), 3);
			return `fill="${hexColor(paint.color)}"${a < 1 ? ` fill-opacity="${a}"` : ''}`;
		}
		if (paint.type === 'GRADIENT_LINEAR' && paint.stops?.length) {
			const { from, to } = gradientLine(paint, v.size);
			const id = `g${defs.length}`;
			const stops = paint.stops
				.map((s) => `<stop offset="${round(s.position, 4)}" stop-color="${hexColor(s.color)}"${s.color.a < 1 ? ` stop-opacity="${round(s.color.a, 3)}"` : ''}/>`)
				.join('');
			defs.push(
				`<linearGradient id="${id}" gradientUnits="userSpaceOnUse" x1="${round(from.x)}" y1="${round(from.y)}" x2="${round(to.x)}" y2="${round(to.y)}">${stops}</linearGradient>`
			);
			return `fill="url(#${id})"${(paint.opacity ?? 1) < 1 ? ` fill-opacity="${round(paint.opacity, 3)}"` : ''}`;
		}
		const stop = paint.stops?.[0]?.color; // other gradient kinds fall back to their first colour
		return stop ? `fill="${hexColor(stop)}"` : null;
	};
	const draw = (geometry, paints, v, matrix) => {
		for (const paint of paints || []) {
			if (paint.visible === false) continue;
			const attr = paintAttr(paint, v);
			if (!attr) continue;
			for (const g of geometry || []) {
				const m = matrix;
				const d = pathData(fig, g.commandsBlob, (x, y) => {
					const px = m.m00 * x + m.m01 * y + m.m02;
					const py = m.m10 * x + m.m11 * y + m.m12;
					bounds.x0 = Math.min(bounds.x0, px);
					bounds.y0 = Math.min(bounds.y0, py);
					bounds.x1 = Math.max(bounds.x1, px);
					bounds.y1 = Math.max(bounds.y1, py);
				});
				if (!d) continue;
				const tf = `matrix(${round(m.m00, 5)} ${round(m.m10, 5)} ${round(m.m01, 5)} ${round(m.m11, 5)} ${round(m.m02, 3)} ${round(m.m12, 3)})`;
				body.push(`<path d="${d}" ${attr}${g.windingRule === 'ODD' ? ' fill-rule="evenodd"' : ''} transform="${tf}"/>`);
			}
		}
	};
	const walk = (n, matrix, isRoot) => {
		const v = n.v;
		const m = isRoot ? IDENTITY : multiply(matrix, v.transform || IDENTITY);
		const opacity = v.opacity ?? 1;
		if (opacity < 1 && !isRoot) body.push(`<g opacity="${round(opacity, 3)}">`);
		draw(v.fillGeometry, v.fillPaints, v, m);
		draw(v.strokeGeometry, v.strokePaints, v, m);
		if (v.type !== 'BOOLEAN_OPERATION') for (const k of n.kids) walk(k, m, false);
		if (opacity < 1 && !isRoot) body.push('</g>');
	};
	walk(t, IDENTITY, true);
	// Strokes and effects can draw outside the node's box; the SVG covers whichever is larger.
	let box = { x: 0, y: 0, w: round(t.v.size?.x ?? 0), h: round(t.v.size?.y ?? 0) };
	let outside = null;
	if (bounds.x0 < -0.5 || bounds.y0 < -0.5 || bounds.x1 > box.w + 0.5 || bounds.y1 > box.h + 0.5) {
		const x = Math.floor(Math.min(0, bounds.x0));
		const y = Math.floor(Math.min(0, bounds.y0));
		box = { x, y, w: Math.ceil(Math.max(box.w, bounds.x1)) - x, h: Math.ceil(Math.max(box.h, bounds.y1)) - y };
		outside = box;
	}
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${box.w}" height="${box.h}" viewBox="${box.x} ${box.y} ${box.w} ${box.h}" fill="none">${
		defs.length ? `<defs>${defs.join('')}</defs>` : ''
	}${body.join('')}</svg>\n`;
	return { svg, outside, empty: !body.length };
}

// ---------------------------------------------------------------- normalising

const JUSTIFY = { MIN: 'start', CENTER: 'center', MAX: 'end', SPACE_EVENLY: 'space-between', SPACE_BETWEEN: 'space-between', SPACE_AROUND: 'space-around', SPACE_EVENLY_CSS: 'space-evenly' };
const ALIGN = { MIN: 'start', CENTER: 'center', MAX: 'end', BASELINE: 'baseline', STRETCH: 'stretch' };
const FIELD_NAMES = {
	STACK_SPACING: 'gap', STACK_COUNTER_SPACING: 'counterGap', STACK_PADDING_LEFT: 'paddingLeft', STACK_PADDING_TOP: 'paddingTop',
	STACK_PADDING_RIGHT: 'paddingRight', STACK_PADDING_BOTTOM: 'paddingBottom', CORNER_RADIUS: 'radius', WIDTH: 'width', HEIGHT: 'height',
	MIN_WIDTH: 'minWidth', MAX_WIDTH: 'maxWidth', MIN_HEIGHT: 'minHeight', MAX_HEIGHT: 'maxHeight', STROKE_WEIGHT: 'strokeWeight',
	FONT_SIZE: 'fontSize', LINE_HEIGHT: 'lineHeight', LETTER_SPACING: 'letterSpacing', FONT_FAMILY: 'fontFamily', FONT_STYLE: 'fontStyle',
	OPACITY: 'opacity', PARAGRAPH_SPACING: 'paragraphSpacing',
	RECTANGLE_TOP_LEFT_CORNER_RADIUS: 'radiusTopLeft', RECTANGLE_TOP_RIGHT_CORNER_RADIUS: 'radiusTopRight',
	RECTANGLE_BOTTOM_LEFT_CORNER_RADIUS: 'radiusBottomLeft', RECTANGLE_BOTTOM_RIGHT_CORNER_RADIUS: 'radiusBottomRight',
};

// The node field each bound variable sets, for the ones that hold a plain number.
const FIELD_SOURCE = {
	STACK_SPACING: 'stackSpacing', STACK_COUNTER_SPACING: 'stackCounterSpacing', STACK_PADDING_LEFT: 'stackHorizontalPadding', STACK_PADDING_TOP: 'stackVerticalPadding',
	STACK_PADDING_RIGHT: 'stackPaddingRight', STACK_PADDING_BOTTOM: 'stackPaddingBottom', CORNER_RADIUS: 'cornerRadius', STROKE_WEIGHT: 'strokeWeight', FONT_SIZE: 'fontSize',
	RECTANGLE_TOP_LEFT_CORNER_RADIUS: 'rectangleTopLeftCornerRadius', RECTANGLE_TOP_RIGHT_CORNER_RADIUS: 'rectangleTopRightCornerRadius',
	RECTANGLE_BOTTOM_LEFT_CORNER_RADIUS: 'rectangleBottomLeftCornerRadius', RECTANGLE_BOTTOM_RIGHT_CORNER_RADIUS: 'rectangleBottomRightCornerRadius',
};

function createExtractor(fig, outDir) {
	const assetsDir = path.join(outDir, 'assets');
	const wantedImages = new Map(); // hash -> { name, folder, figmaName, natural, uses }
	const svgFiles = new Map(); // digest -> { file, uses }
	let drawing = null; // the node whose paints are being read
	const tokens = { colors: new Map(), numbers: new Map(), strings: new Map(), textStyles: new Map(), fillStyles: new Map(), effectStyles: new Map() };
	const notes = { annotations: new Map(), descriptions: new Map(), flagged: [] };
	const counts = { nodes: 0, text: 0 };

	const setName = (variable) => fig.byId.get(gid(variable.variableSetID?.guid))?.name || (variable.variableSetID?.assetRef && fig.byKey.get(variable.variableSetID.assetRef.key)?.name) || null;

	// A variable's value in its first mode, following aliases to the end.
	const rawValue = (data, depth = 0) => {
		if (!data || depth > 10) return undefined;
		const value = data.value || {};
		if (value.alias) return rawValue(fig.variable(value.alias)?.variableDataValues?.entries?.[0]?.variableData, depth + 1);
		if (value.expressionValue?.expressionFunction === 'COMPOSE_COLOR') {
			// A colour with an opacity applied; the opacity is read as a percentage.
			const [colorArg, alphaArg] = value.expressionValue.expressionArguments || [];
			const color = rawValue(colorArg, depth + 1);
			const alpha = rawValue(alphaArg, depth + 1);
			return color && typeof color === 'object' ? { ...color, a: (color.a ?? 1) * (typeof alpha === 'number' ? alpha / 100 : 1) } : undefined;
		}
		return value.colorValue ?? value.floatValue ?? value.textValue ?? value.boolValue;
	};
	const shown = (raw) => (raw && typeof raw === 'object' ? cssColor(raw) : typeof raw === 'number' ? round(raw, 3) : raw);
	// A variable's value in each of its modes, by mode name, when the modes differ.
	const modesOf = (variable) => {
		const entries = variable?.variableDataValues?.entries || [];
		const values = entries.map((e) => shown(rawValue(e.variableData)));
		if (new Set(values.map(String)).size < 2) return null;
		const set = fig.byId.get(gid(variable.variableSetID?.guid)) || (variable.variableSetID?.assetRef && fig.byKey.get(variable.variableSetID.assetRef.key));
		const names = new Map((set?.variableSetModes || []).map((m) => [gid(m.id), m.name]));
		return Object.fromEntries(entries.map((e, i) => [names.get(gid(e.modeID)) || `mode ${i + 1}`, values[i]]));
	};
	// `drawn` is the value the node actually has. A number bound to a variable whose value in every
	// mode differs from it is a stale binding (an instance override replaced the value), so it is not reported.
	const useVariable = (data, drawn) => {
		const variable = fig.variable(data?.value?.alias);
		if (!variable || variable.type !== 'VARIABLE') return null;
		const entries = variable.variableDataValues?.entries || [];
		const values = entries.map((e) => shown(rawValue(e.variableData)));
		if (typeof drawn === 'number' && values.length && !values.some((v) => typeof v === 'number' && Math.abs(v - drawn) < 0.01)) return null;
		const value = values[0] ?? drawn;
		const bucket = variable.variableResolvedType === 'COLOR' ? tokens.colors : typeof value === 'number' ? tokens.numbers : tokens.strings;
		const key = gid(variable.guid);
		if (!bucket.has(key)) {
			const token = { name: variable.name, collection: setName(variable), value, uses: 0 };
			const modes = modesOf(variable);
			if (modes) token.modes = modes;
			bucket.set(key, token);
		}
		bucket.get(key).uses++;
		return variable.name;
	};

	const image = (img, paint, folder = 'images') => {
		if (!img?.hash?.length) return null;
		const hash = Buffer.from(img.hash).toString('hex');
		if (!wantedImages.has(hash))
			wantedImages.set(hash, { name: `${slug(img.name || 'image', 32)}-${hash.slice(0, 8)}`, folder, figmaName: img.name || null, natural: paint.originalImageWidth ? [paint.originalImageWidth, paint.originalImageHeight] : null, uses: [] });
		if (drawing) wantedImages.get(hash).uses.push({ ...drawing, fit: (paint.imageScaleMode || '').toLowerCase() });
		return `assets/${wantedImages.get(hash).name}`; // the extension is added once the file has been read
	};

	const paints = (list, size) => {
		const out = [];
		for (const p of list || []) {
			if (p.visible === false) continue;
			const opacity = round(p.opacity ?? 1, 3);
			if (p.type === 'SOLID') {
				const item = { color: cssColor(p.color, p.opacity ?? 1) };
				const token = useVariable(p.colorVar, cssColor(p.color, p.opacity ?? 1));
				if (token) item.token = token;
				out.push(item);
			} else if (p.type?.startsWith('GRADIENT')) {
				const item = { gradient: p.type.slice(9).toLowerCase(), stops: (p.stops || []).map((s) => `${cssColor(s.color)} ${round(s.position * 100, 1)}%`) };
				if (p.type === 'GRADIENT_LINEAR' && size) {
					const { from, to } = gradientLine(p, size);
					item.angle = round((Math.atan2(to.x - from.x, -(to.y - from.y)) * 180) / Math.PI, 1);
					item.from = [round(from.x, 1), round(from.y, 1)];
					item.to = [round(to.x, 1), round(to.y, 1)];
				}
				if (opacity < 1) item.opacity = opacity;
				out.push(item);
			} else if (p.type === 'IMAGE' || p.type === 'VIDEO') {
				const item = {};
				if (p.type === 'VIDEO') item.video = image(p.video, p, 'videos');
				item[p.type === 'VIDEO' ? 'poster' : 'image'] = image(p.image, p);
				item.fit = { FILL: 'cover', FIT: 'contain', TILE: 'tile', STRETCH: 'crop' }[p.imageScaleMode] || p.imageScaleMode;
				if (p.originalImageWidth) item.natural = [p.originalImageWidth, p.originalImageHeight];
				if (p.imageScaleMode === 'TILE' && p.scale) item.scale = round(p.scale, 3);
				if (p.altText) item.alt = p.altText;
				if (opacity < 1) item.opacity = opacity;
				out.push(item);
			}
		}
		return out;
	};

	const styleName = (ref, bucket, describe) => {
		const style = fig.style(ref);
		if (!style) return null;
		if (!bucket.has(style.name)) {
			bucket.set(style.name, { name: style.name, ...describe(style) });
			if (style.description) notes.descriptions.set(`style:${style.name}`, { kind: 'Style', name: style.name, text: style.description });
		}
		return style.name;
	};

	const typography = (v) => {
		const out = {};
		if (v.fontName) out.font = `${v.fontName.family} ${v.fontName.style}`.trim();
		if (v.fontSize !== undefined) out.size = round(v.fontSize);
		if (v.lineHeight) out.lineHeight = v.lineHeight.units === 'PIXELS' ? `${round(v.lineHeight.value)}px` : v.lineHeight.units === 'PERCENT' ? (Math.abs(v.lineHeight.value - 100) < 0.01 ? 'auto' : `${round(v.lineHeight.value)}% of auto`) : round(v.lineHeight.value, 3);
		if (v.letterSpacing?.value) out.letterSpacing = v.letterSpacing.units === 'PERCENT' ? `${round(v.letterSpacing.value / 100, 4)}em` : `${round(v.letterSpacing.value)}px`;
		if (v.textCase && v.textCase !== 'ORIGINAL') out.case = v.textCase.toLowerCase();
		if (v.textDecoration && v.textDecoration !== 'NONE') out.decoration = v.textDecoration.toLowerCase();
		return out;
	};

	// A text style's size, line height or letter spacing can be a variable with a value per mode (desktop, mobile).
	const STYLE_FIELDS = { FONT_SIZE: 'size', LINE_HEIGHT: 'lineHeight', LETTER_SPACING: 'letterSpacing' };
	const textStyle = (s) => {
		const out = typography(s);
		for (const e of s.variableConsumptionMap?.entries || []) {
			const field = STYLE_FIELDS[e.variableField];
			const variable = field && fig.variable(e.variableData?.value?.alias);
			const modes = variable && modesOf(variable);
			if (modes) (out.modes ||= {})[field] = { variable: variable.name, ...modes };
		}
		return out;
	};

	// The size the file's own layout drew each glyph at. A node keeps the first mode's size when its text
	// style takes the size from a variable, so a frame set to another mode is only right here.
	const drawnSize = (glyphs, from, to) => {
		const tally = new Map();
		for (const g of glyphs) {
			const at = g.firstCharacter ?? 0;
			if (g.fontSize && at >= from && at < to) tally.set(g.fontSize, (tally.get(g.fontSize) || 0) + 1);
		}
		const top = [...tally].sort((a, b) => b[1] - a[1])[0];
		return top ? round(top[0]) : undefined;
	};

	const text = (v) => {
		const data = v.textData || {};
		// A line the designer broke by hand is stored as U+2028, which prints as nothing; it is written as a newline so it can be seen.
		const out = { characters: (data.characters ?? '').replace(/\u2028/g, '\n'), ...typography(v) };
		const glyphs = v.derivedTextData?.glyphs || [];
		const drawn = drawnSize(glyphs, 0, Infinity);
		if (drawn !== undefined) out.size = drawn;
		if (v.derivedTextData?.baselines?.length) out.lines = v.derivedTextData.baselines.length;
		if (v.textAlignHorizontal && v.textAlignHorizontal !== 'LEFT') out.align = v.textAlignHorizontal.toLowerCase();
		if (v.textAlignVertical && v.textAlignVertical !== 'TOP') out.valign = v.textAlignVertical.toLowerCase();
		if (v.paragraphSpacing) out.paragraphSpacing = round(v.paragraphSpacing);
		if (v.maxLines) out.maxLines = v.maxLines;
		if (v.hyperlink?.url) out.link = v.hyperlink.url;
		const style = styleName(v.styleIdForText, tokens.textStyles, textStyle);
		if (style) out.style = style;
		const lists = (data.lines || []).filter((l) => l.lineType && l.lineType !== 'PLAIN');
		if (lists.length) out.list = [...new Set(lists.map((l) => l.lineType.toLowerCase()))].join(', ');
		// Ranges styled differently from the rest of the text.
		const ids = data.characterStyleIDs || [];
		const table = new Map((data.styleOverrideTable || []).map((o) => [o.styleID, o]));
		const runs = [];
		for (let i = 0; i < ids.length; ) {
			let j = i;
			while (j < ids.length && ids[j] === ids[i]) j++;
			const o = table.get(ids[i]);
			if (o) {
				const run = { text: out.characters.slice(i, j), ...typography(o) };
				const runSize = drawnSize(glyphs, i, j);
				if (runSize !== undefined && runSize !== out.size) run.size = runSize;
				else delete run.size;
				const fill = paints(o.fillPaints);
				if (fill.length) run.fills = fill;
				if (o.hyperlink?.url) run.link = o.hyperlink.url;
				const runStyle = styleName(o.styleIdForText, tokens.textStyles, textStyle);
				if (runStyle && runStyle !== style) run.style = runStyle;
				if (Object.keys(run).length > 1) runs.push(run);
			}
			i = j;
		}
		if (runs.length) out.runs = runs;
		return out;
	};

	const annotate = (v, trail) => {
		for (const a of v.annotations || []) {
			const label = htmlToText(a.labelV2 || a.label);
			const props = (a.properties || []).map((p) => titleCase(p.type)).join(', ');
			if (!label && !props) continue;
			const key = `${gid(a.categoryId) || ''}|${label}|${props}`;
			if (!notes.annotations.has(key)) notes.annotations.set(key, { category: fig.categories.get(gid(a.categoryId)) || null, label, props, on: [] });
			notes.annotations.get(key).on.push(trail);
		}
	};

	const normalize = (t, parentDir, trail, isRoot) => {
		const v = t.v;
		counts.nodes++;
		const here = [...trail, v.name];
		annotate(v, here.slice(-4).join(' > '));
		const node = { id: t.id, name: v.name, type: v.type };
		if (t.component) {
			node.component = t.component;
			const description = t.symbol.symbolDescription || t.symbol.description || fig.parent(t.symbol)?.description;
			if (description) notes.descriptions.set(`component:${t.component}`, { kind: 'Component', name: t.component, text: htmlToText(description) });
			if (/\b(dev|design)[\s-]*note|annotation/i.test(t.component)) node.designerNote = true;
		}
		const tf = v.transform || IDENTITY;
		const size = v.size || { x: 0, y: 0 };
		Object.assign(node, { x: isRoot ? 0 : round(tf.m02), y: isRoot ? 0 : round(tf.m12), w: round(size.x), h: round(size.y) });
		if (isRotated(tf)) {
			node.rotation = round((-Math.atan2(tf.m10, tf.m00) * 180) / Math.PI, 2);
			if (tf.m00 * tf.m11 - tf.m01 * tf.m10 < 0) node.flip = 'mirrored';
		} else if (tf.m00 < 0 || tf.m11 < 0) {
			// Mirrored or turned half way round: the transform's origin is then a far corner, so the box is moved back to its top left.
			if (tf.m00 < 0 && !isRoot) node.x = round(tf.m02 - size.x);
			if (tf.m11 < 0 && !isRoot) node.y = round(tf.m12 - size.y);
			if (tf.m00 < 0 && tf.m11 < 0) node.rotation = 180;
			else node.flip = tf.m00 < 0 ? 'horizontal' : 'vertical';
		}
		if ((v.opacity ?? 1) < 1) node.opacity = round(v.opacity, 3);
		if (v.blendMode && !['NORMAL', 'PASS_THROUGH'].includes(v.blendMode)) node.blend = v.blendMode.toLowerCase();
		if (v.mask) node.mask = true;

		// How this node sizes itself, in CSS terms.
		const auto = v.stackMode && v.stackMode !== 'NONE' ? v.stackMode : null;
		const sizing = { w: 'fixed', h: 'fixed' };
		if (auto === 'HORIZONTAL' || auto === 'VERTICAL') {
			const main = v.stackPrimarySizing === 'FIXED' ? 'fixed' : 'hug';
			const cross = String(v.stackCounterSizing || '').startsWith('RESIZE') ? 'hug' : 'fixed';
			Object.assign(sizing, auto === 'HORIZONTAL' ? { w: main, h: cross } : { w: cross, h: main });
		}
		if (v.type === 'TEXT') {
			if (v.textAutoResize === 'WIDTH_AND_HEIGHT') Object.assign(sizing, { w: 'hug', h: 'hug' });
			else if (v.textAutoResize === 'HEIGHT') sizing.h = 'hug';
		}
		if (parentDir && v.stackPositioning !== 'ABSOLUTE') {
			if (v.stackChildPrimaryGrow) sizing[parentDir === 'HORIZONTAL' ? 'w' : 'h'] = 'fill';
			if (v.stackChildAlignSelf === 'STRETCH') sizing[parentDir === 'HORIZONTAL' ? 'h' : 'w'] = 'fill';
			else if (v.stackChildAlignSelf && v.stackChildAlignSelf !== 'AUTO') node.alignSelf = ALIGN[v.stackChildAlignSelf];
		}
		if (sizing.w !== 'fixed' || sizing.h !== 'fixed') node.sizing = sizing;
		if (parentDir && v.stackPositioning === 'ABSOLUTE') node.absolute = true;
		if (!parentDir && !isRoot && (v.horizontalConstraint || v.verticalConstraint))
			node.constraints = `${(v.horizontalConstraint || 'MIN').toLowerCase()} ${(v.verticalConstraint || 'MIN').toLowerCase()}`;
		for (const [key, field] of [['minW', v.minSize?.value?.x], ['minH', v.minSize?.value?.y], ['maxW', v.maxSize?.value?.x], ['maxH', v.maxSize?.value?.y]])
			if (field) node[key] = round(field);

		if (auto) {
			const layout = { direction: auto === 'HORIZONTAL' ? 'row' : auto === 'VERTICAL' ? 'column' : 'grid' };
			if (v.stackSpacing) layout.gap = round(v.stackSpacing);
			if (v.stackWrap === 'WRAP') {
				layout.wrap = true;
				if (v.stackCounterSpacing) layout.counterGap = round(v.stackCounterSpacing);
			}
			const padding = [v.stackVerticalPadding, v.stackPaddingRight, v.stackPaddingBottom, v.stackHorizontalPadding].map((p) => round(p || 0));
			if (padding.some(Boolean)) layout.padding = padding;
			if (v.stackPrimaryAlignItems && v.stackPrimaryAlignItems !== 'MIN') layout.justify = JUSTIFY[v.stackPrimaryAlignItems];
			if (v.stackCounterAlignItems && v.stackCounterAlignItems !== 'MIN') layout.align = ALIGN[v.stackCounterAlignItems];
			if (auto === 'GRID') Object.assign(layout, { columns: v.gridColumns?.length, rows: v.gridRows?.length, columnGap: round(v.gridColumnGap), rowGap: round(v.gridRowGap) });
			node.layout = layout;
		}
		if (CONTAINERS.has(v.type) && v.type !== 'GROUP' && !v.frameMaskDisabled && t.kids.length) node.clip = true;

		const bound = {};
		for (const entry of v.variableConsumptionMap?.entries || []) {
			const drawn = v[FIELD_SOURCE[entry.variableField]];
			const name = useVariable(entry.variableData, typeof drawn === 'number' ? drawn : undefined);
			if (name) bound[FIELD_NAMES[entry.variableField] || entry.variableField.toLowerCase()] = name;
		}
		if (Object.keys(bound).length) node.tokens = bound;

		drawing = { on: here.slice(-4).join(' > '), drawn: [node.w, node.h] };
		if (isArtwork(t)) {
			const { svg, outside, empty } = toSvg(fig, t);
			if (!empty) {
				const digest = crypto.createHash('sha1').update(svg).digest('hex').slice(0, 8);
				if (!svgFiles.has(digest)) {
					svgFiles.set(digest, { file: `${slug(t.component || v.name, 32)}-${digest}.svg`, bytes: Buffer.byteLength(svg), uses: [] });
					fs.mkdirSync(assetsDir, { recursive: true });
					fs.writeFileSync(path.join(assetsDir, svgFiles.get(digest).file), svg);
				}
				svgFiles.get(digest).uses.push(drawing);
				node.svg = `assets/${svgFiles.get(digest).file}`;
				if (outside) node.svgBox = outside; // the drawing overflows the node: its box relative to the node's top-left
				return node;
			}
		}

		const fills = paints(v.fillPaints, size);
		if (fills.length) node.fills = fills;
		const fillStyle = styleName(v.styleIdForFill, tokens.fillStyles, (s) => ({ fills: paints(s.fillPaints) }));
		if (fillStyle) node.fillStyle = fillStyle;
		const strokes = paints(v.strokePaints, size);
		if (strokes.length && (v.strokeWeight || v.borderStrokeWeightsIndependent)) {
			node.stroke = { paints: strokes, weight: round(v.strokeWeight), align: (v.strokeAlign || 'CENTER').toLowerCase() };
			if (v.borderStrokeWeightsIndependent)
				node.stroke.sides = [v.borderTopWeight, v.borderRightWeight, v.borderBottomWeight, v.borderLeftWeight].map((n) => round(n || 0));
			if (v.dashPattern?.length) node.stroke.dash = v.dashPattern.map((n) => round(n));
		}
		const corners = [v.rectangleTopLeftCornerRadius, v.rectangleTopRightCornerRadius, v.rectangleBottomRightCornerRadius, v.rectangleBottomLeftCornerRadius].map((n) => round(n || 0));
		if (corners.some(Boolean)) node.radius = corners.every((c) => c === corners[0]) ? corners[0] : corners;
		else if (v.cornerRadius) node.radius = round(v.cornerRadius);
		if (v.type === 'ELLIPSE') node.radius = '50%';
		const effects = (v.effects || [])
			.filter((e) => e.visible !== false)
			.map((e) =>
				e.type.endsWith('SHADOW')
					? { type: e.type === 'INNER_SHADOW' ? 'inner-shadow' : 'drop-shadow', x: round(e.offset?.x || 0), y: round(e.offset?.y || 0), blur: round(e.radius || 0), spread: round(e.spread || 0), color: cssColor(e.color || { r: 0, g: 0, b: 0, a: 1 }) }
					: { type: e.type === 'BACKGROUND_BLUR' ? 'backdrop-blur' : e.type === 'FOREGROUND_BLUR' ? 'blur' : e.type.toLowerCase(), radius: round(e.radius || 0) }
			);
		if (effects.length) node.effects = effects;
		const effectStyle = styleName(v.styleIdForEffect, tokens.effectStyles, () => ({ effects }));
		if (effectStyle) node.effectStyle = effectStyle;

		if (v.type === 'TEXT') {
			node.text = text(v);
			counts.text++;
		}
		if (node.designerNote) notes.flagged.push({ on: here.slice(-3).join(' > '), text: collectText(t) });
		const dir = auto === 'HORIZONTAL' || auto === 'VERTICAL' ? auto : null;
		const kids = t.kids.map((k) => normalize(k, dir, here, false));
		if (kids.length) node.children = kids;
		return node;
	};

	const collectText = (t) => {
		const out = [];
		const walk = (n) => {
			if (n.v.type === 'TEXT' && n.v.textData?.characters?.trim()) out.push(n.v.textData.characters.trim());
			n.kids.forEach(walk);
		};
		walk(t);
		return out.join(' / ');
	};

	// Copy the images the tree refers to, adding the extension their bytes call for.
	const writeAssets = () => {
		const renamed = new Map();
		const missing = [];
		const manifest = [];
		const uses = (list) => ({ useCount: list.length, uses: list.slice(0, 6) });
		for (const s of svgFiles.values()) manifest.push({ file: `assets/${s.file}`, kind: 'vector', bytes: s.bytes, ...uses(s.uses) });
		Object.assign(renamed, { missing, manifest });
		if (!wantedImages.size) return renamed;
		fs.mkdirSync(assetsDir, { recursive: true });
		const entries = [...wantedImages].map(([hash, info]) => ({ hash, ...info, source: fig.dir && path.join(fig.dir, info.folder, hash) }));
		const absent = entries.filter((e) => !e.source || !fs.existsSync(e.source));
		if (fig.zip && absent.length) {
			for (let i = 0; i < absent.length; i += 200) {
				try {
					execFileSync('unzip', ['-o', '-q', fig.zip, ...absent.slice(i, i + 200).map((e) => `${e.folder}/${e.hash}`), '-d', fig.dir], { stdio: 'ignore' });
				} catch {} // unzip exits non-zero when one name is absent; the copy below reports which
			}
		}
		for (const e of entries) {
			if (!e.source || !fs.existsSync(e.source)) {
				missing.push(e.name);
				continue;
			}
			const head = Buffer.alloc(16);
			const fd = fs.openSync(e.source, 'r');
			fs.readSync(fd, head, 0, 16, 0);
			fs.closeSync(fd);
			const file = `${e.name}.${sniff(head)}`;
			fs.copyFileSync(e.source, path.join(assetsDir, file));
			renamed.set(`assets/${e.name}`, `assets/${file}`);
			manifest.push({ file: `assets/${file}`, kind: e.folder === 'videos' ? 'video' : 'image', figmaName: e.figmaName, bytes: fs.statSync(e.source).size, natural: e.natural, ...uses(e.uses) });
		}
		return renamed;
	};

	return { normalize, writeAssets, tokens, notes, counts };
}

function sniff(head) {
	const hexHead = head.toString('hex');
	const ascii = head.toString('latin1');
	if (hexHead.startsWith('89504e47')) return 'png';
	if (hexHead.startsWith('ffd8ff')) return 'jpg';
	if (ascii.startsWith('GIF8')) return 'gif';
	if (ascii.startsWith('RIFF') && ascii.slice(8, 12) === 'WEBP') return 'webp';
	if (hexHead.startsWith('1a45dfa3')) return 'webm';
	if (ascii.slice(4, 8) === 'ftyp') return /avif|avis/.test(ascii.slice(8, 12)) ? 'avif' : /heic|heix|mif1/.test(ascii.slice(8, 12)) ? 'heic' : ascii.slice(8, 10) === 'qt' ? 'mov' : 'mp4';
	if (ascii.trimStart().startsWith('<')) return 'svg';
	return 'bin';
}

// ---------------------------------------------------------------- designer notes

// Text the designer left around the design rather than in it.
function contextNotes(fig, root) {
	const out = { presented: [], loose: [] };
	const textsUnder = (n, skip) => {
		const found = [];
		const walk = (x) => {
			if (x === skip || x.visible === false) return;
			if (x.type === 'TEXT' && x.textData?.characters?.trim()) found.push(x.textData.characters.trim());
			fig.children(x).forEach(walk);
		};
		walk(n);
		return found;
	};
	// Frames elsewhere in the file that show this component, such as a presentation slide.
	const rootId = gid(root.guid);
	for (const n of fig.nodes) {
		if (n.type !== 'INSTANCE' || gid(n.symbolData?.symbolID) !== rootId) continue;
		let top = n;
		while (fig.parent(top) && !['CANVAS', 'SECTION'].includes(fig.parent(top).type)) top = fig.parent(top);
		if (top === n) continue;
		const texts = textsUnder(top, n);
		if (texts.length) out.presented.push({ frame: top.name, page: fig.page(top)?.name, texts });
	}
	// Text typed straight onto the page, or into a section, beside the frames.
	const page = fig.page(root);
	if (page) {
		const walk = (container) => {
			for (const n of fig.children(container)) {
				if (n.visible === false) continue;
				if (n.type === 'TEXT' && n.textData?.characters?.trim()) out.loose.push(n.textData.characters.trim());
				else if (n.type === 'SECTION') walk(n);
			}
		};
		walk(page);
	}
	return out;
}

function notesMarkdown(fig, root, notes, context) {
	const lines = [`# Designer notes: ${root.name}`, ''];
	lines.push(`Read from \`${fig.meta.file_name || 'the Figma file'}\`${fig.meta.exported_at ? `, exported ${fig.meta.exported_at.slice(0, 10)}` : ''}; node \`${gid(root.guid)}\` on page "${fig.page(root)?.name ?? '?'}".`);
	lines.push('These are the designer\'s words, copied as written. They describe intent the frames cannot show, such as motion and behaviour.', '');
	const bullet = (text) => text.split('\n').map((l, i) => (i ? `  ${l}` : `- ${l}`)).join('\n');

	lines.push('## Annotations', '');
	if (notes.annotations.size) {
		for (const a of notes.annotations.values()) {
			const where = [...new Set(a.on)];
			const shown = where.slice(0, 3).map((w) => `\`${w}\``).join('; ');
			const head = `${a.category ? `**${a.category}.** ` : ''}${a.label}${a.props ? `${a.label ? ' ' : ''}[pins: ${a.props}]` : ''}`;
			lines.push(bullet(`${head}\nOn ${shown}${where.length > 3 ? ` and ${where.length - 3} more` : ''}${a.on.length > where.length ? ` (${a.on.length} places)` : ''}.`));
		}
	} else lines.push('None on this node or inside it.');
	lines.push('');

	if (notes.flagged.length) {
		lines.push('## Note layers inside the design', '', 'These layers are notes, not content: do not build them.', '');
		for (const f of notes.flagged) lines.push(bullet(`\`${f.on}\`: ${f.text || '(no text)'}`));
		lines.push('');
	}
	if (context.presented.length) {
		lines.push('## Where the design is presented', '');
		for (const p of context.presented) lines.push(bullet(`Frame "${p.frame}" on page "${p.page}": ${p.texts.map((t) => `"${t.replace(/\n/g, ' / ')}"`).join(', ')}`));
		lines.push('');
	}
	if (notes.descriptions.size) {
		lines.push('## Component and style descriptions', '');
		for (const d of notes.descriptions.values()) lines.push(bullet(`${d.kind} \`${d.name}\`: ${d.text}`));
		lines.push('');
	}
	if (context.loose.length) {
		const max = 80;
		lines.push('## Text placed on the page beside the frames', '');
		for (const t of context.loose.slice(0, max)) lines.push(bullet(t.length > 600 ? `${t.slice(0, 600)}…` : t));
		if (context.loose.length > max) lines.push('', `${context.loose.length - max} more are not listed.`);
		lines.push('');
	}
	lines.push('## Not in the file', '', 'Figma comment threads are kept on Figma\'s servers and are not part of a `.fig` export, so none appear here. Ask the designer for any that matter.', '');
	return lines.join('\n');
}

// ---------------------------------------------------------------- commands

function findNode(fig, ref) {
	const direct = fig.byId.get(ref.replace('-', ':'));
	if (direct) return direct;
	const wanted = ref.toLowerCase();
	const candidates = fig.nodes.filter((n) => ['FRAME', 'SYMBOL', 'SECTION', 'INSTANCE'].includes(n.type) && n.name?.toLowerCase() === wanted);
	if (candidates.length === 1) return candidates[0];
	if (!candidates.length) throw new Error(`No node with the id or exact name "${ref}". Run "find" to search by part of a name.`);
	throw new Error(`"${ref}" names ${candidates.length} nodes; pass one id:\n${candidates.map((n) => `  ${describe(fig, n)}`).join('\n')}`);
}

const dims = (n) => (n.size ? `${Math.round(n.size.x)}x${Math.round(n.size.y)}` : '');
const describe = (fig, n) => `${gid(n.guid)}\t${n.type === 'SYMBOL' ? 'COMPONENT' : n.type}\t${dims(n)}\t${n.name}\t(page "${fig.page(n)?.name ?? '?'}")`;

function cmdPages(fig) {
	for (const p of fig.pages()) console.log(`${gid(p.guid)}\t${fig.children(p).length} top-level\t${p.name}`);
}

// Top-level frames of a page, and under each the page-sized components it shows.
function cmdFrames(fig, opts) {
	const pages = fig.pages().filter((p) => !opts.page || p.name.toLowerCase().includes(opts.page.toLowerCase()));
	if (!pages.length) throw new Error(`No page matches "${opts.page}".`);
	for (const page of pages) {
		console.log(`\n# ${page.name}`);
		const list = (container, indent) => {
			for (const n of fig.children(container)) {
				if (n.type === 'SECTION') {
					console.log(`${indent}[section] ${n.name}`);
					list(n, `${indent}  `);
					continue;
				}
				if (!['FRAME', 'SYMBOL', 'INSTANCE'].includes(n.type)) continue;
				console.log(`${indent}${gid(n.guid)}\t${n.type === 'SYMBOL' ? 'COMPONENT' : n.type}\t${dims(n)}\t${n.name}`);
				const shown = new Set();
				const walk = (x, depth) => {
					if (x.type === 'INSTANCE') {
						const sym = fig.symbolOf(x);
						if (sym && x.size && x.size.x >= 300 && x.size.y >= 400 && !shown.has(sym)) {
							shown.add(sym);
							console.log(`${indent}  shows component ${gid(sym.guid)}\t${dims(sym)}\t${fig.componentName(sym)}`);
						}
						return;
					}
					if (depth < 6) fig.children(x).forEach((c) => walk(c, depth + 1));
				};
				if (n.type !== 'SYMBOL') walk(n, 0);
			}
		};
		list(page, '');
	}
}

function cmdFind(fig, term) {
	const wanted = term.toLowerCase();
	const hits = fig.nodes.filter((n) => ['FRAME', 'SYMBOL', 'SECTION'].includes(n.type) && n.name?.toLowerCase().includes(wanted) && !fig.isInternal(fig.page(n)));
	hits.sort((a, b) => (b.size ? b.size.x * b.size.y : 0) - (a.size ? a.size.x * a.size.y : 0));
	for (const n of hits.slice(0, 60)) console.log(describe(fig, n));
	if (hits.length > 60) console.log(`… ${hits.length - 60} more`);
	if (!hits.length) console.log('No frame, component or section matches.');
}

function cmdExtract(fig, opts) {
	if (!opts.node || !opts.out) throw new Error('extract needs --node <id or exact name> and --out <folder>.');
	const root = findNode(fig, opts.node);
	const outDir = path.resolve(opts.out);
	fs.mkdirSync(outDir, { recursive: true });
	const { tree, stats } = resolveTree(fig, root);
	if (!tree) throw new Error('That node is hidden.');
	const extractor = createExtractor(fig, outDir);
	const node = extractor.normalize(tree, null, [], true);
	const renamed = extractor.writeAssets();

	const fixPaths = (value) => {
		if (Array.isArray(value)) return value.forEach(fixPaths);
		if (!value || typeof value !== 'object') return;
		for (const key of ['image', 'poster', 'video']) if (typeof value[key] === 'string' && renamed.has(value[key])) value[key] = renamed.get(value[key]);
		Object.values(value).forEach(fixPaths);
	};
	fixPaths(node);

	const header = {
		source: { file: fig.meta.file_name || path.basename(fig.zip || fig.dir || ''), exported: fig.meta.exported_at || null, formatVersion: fig.version },
		node: { id: gid(root.guid), name: root.name, page: fig.page(root)?.name ?? null, width: node.w, height: node.h },
	};
	const written = [];
	const write = (name, data) => {
		fs.mkdirSync(path.dirname(path.join(outDir, name)), { recursive: true });
		fs.writeFileSync(path.join(outDir, name), typeof data === 'string' ? data : `${JSON.stringify(data, null, 1)}\n`);
		written.push(name);
	};

	// A large tree is written one file per top-level child, so a section can be read on its own.
	const whole = JSON.stringify(node);
	const split = opts.split === 'always' || (opts.split !== 'never' && whole.length > 120_000 && node.children?.length > 1);
	if (split) {
		fs.rmSync(path.join(outDir, 'sections'), { recursive: true, force: true });
		const sections = node.children.map((child, i) => {
			const file = `sections/${String(i + 1).padStart(2, '0')}-${slug(child.name, 30)}.json`;
			write(file, child);
			return { file, id: child.id, name: child.name, x: child.x, y: child.y, w: child.w, h: child.h };
		});
		write('node.json', { ...header, tree: { ...node, children: undefined, sections } });
	} else write('node.json', { ...header, tree: node });

	const outline = [];
	const draw = (n, depth) => {
		const bits = [n.type === 'SYMBOL' ? 'COMPONENT' : n.type, `"${n.name}"`, `${n.w}x${n.h}`];
		if (n.layout) bits.push(n.layout.direction);
		if (n.component && n.component !== n.name) bits.push(`<${n.component}>`);
		if (n.svg) bits.push(`→ ${n.svg}`);
		if (n.text) bits.push(`“${n.text.characters.slice(0, 60).replace(/\n/g, ' ⏎ ')}”`);
		if (n.designerNote) bits.push('[designer note]');
		outline.push(`${'  '.repeat(depth)}${bits.join(' ')}`);
		(n.children || []).forEach((c) => draw(c, depth + 1));
	};
	draw(node, 0);
	write('outline.txt', `${outline.join('\n')}\n`);
	write('layers.txt', layersText(node));

	const list = (map) => [...map.values()].sort((a, b) => a.name.localeCompare(b.name));
	const { tokens } = extractor;
	write('tokens.json', {
		note: 'Only the variables and styles this node uses. A variable\'s value is its first mode, with aliases followed to the end.',
		colors: list(tokens.colors), numbers: list(tokens.numbers), strings: list(tokens.strings),
		textStyles: list(tokens.textStyles), fillStyles: list(tokens.fillStyles), effectStyles: list(tokens.effectStyles),
	});
	write('notes.md', notesMarkdown(fig, root, extractor.notes, contextNotes(fig, root)));
	write('assets.json', {
		note: 'Every file in assets/, with where it is drawn. Only what this node draws was copied; the rest of the Figma file\'s images were left behind.',
		assets: renamed.manifest.sort((a, b) => a.file.localeCompare(b.file)),
	});

	const assets = fs.existsSync(path.join(outDir, 'assets')) ? fs.readdirSync(path.join(outDir, 'assets')) : [];
	const summary = {
		out: outDir,
		node: header.node,
		files: written.filter((f) => !f.startsWith('sections/')),
		sections: split ? written.filter((f) => f.startsWith('sections/')).length : 0,
		nodes: extractor.counts.nodes,
		textNodes: extractor.counts.text,
		instancesExpanded: stats.instances,
		instancesUnresolved: stats.unresolvedInstances,
		hiddenNodesSkipped: stats.hidden,
		images: assets.filter((f) => !f.endsWith('.svg')).length,
		svgs: assets.filter((f) => f.endsWith('.svg')).length,
		missingImages: renamed.missing || [],
		annotations: extractor.notes.annotations.size,
		tokens: { colors: tokens.colors.size, numbers: tokens.numbers.size, textStyles: tokens.textStyles.size },
	};
	console.log(JSON.stringify(summary, null, 1));
}

const HELP = `Read a Figma .fig export (or a folder it was unzipped into).

  fig.mjs pages   <fig>
  fig.mjs frames  <fig> [--page <part of a page name>]
  fig.mjs find    <fig> <part of a frame or component name>
  fig.mjs extract <fig> --node <id | exact name> --out <folder> [--split always|never]

extract writes node.json (the tree as drawn, instances expanded), outline.txt,
layers.txt (the tree as text, a line per layer with its values), tokens.json,
notes.md and assets/ (images, and vector artwork as SVG).`;

function main(argv) {
	const [command, input, ...rest] = argv;
	if (!command || command === '--help' || command === '-h' || !input) {
		console.log(HELP);
		process.exit(command === '--help' || command === '-h' ? 0 : 1);
	}
	const opts = { _: [] };
	for (let i = 0; i < rest.length; i++) {
		if (rest[i].startsWith('--')) opts[rest[i].slice(2)] = rest[++i];
		else opts._.push(rest[i]);
	}
	const fig = load(input);
	if (command === 'pages') cmdPages(fig);
	else if (command === 'frames') cmdFrames(fig, opts);
	else if (command === 'find') cmdFind(fig, opts._.join(' '));
	else if (command === 'extract') cmdExtract(fig, opts);
	else throw new Error(`Unknown command "${command}".\n\n${HELP}`);
}

if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(new URL(import.meta.url).pathname)) {
	try {
		main(process.argv.slice(2));
	} catch (error) {
		console.error(`fig.mjs: ${error.message}`);
		process.exit(1);
	}
}
