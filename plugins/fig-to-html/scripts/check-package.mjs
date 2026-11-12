#!/usr/bin/env node
// Checks a handoff package without a browser: its files, its links, its fonts, its documents, and the
// standards that can be read from the source. Usage: node check-package.mjs <handoff folder>
// Prints one line per check and exits 1 when any fails. Needs Node 22 or later; no dependencies.

import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.argv[2] || '');
const src = path.join(root, 'source');
if (!process.argv[2] || !fs.existsSync(src)) {
	console.error('Usage: node check-package.mjs <handoff folder>   (the folder that holds source/)');
	process.exit(2);
}

const results = [];
const pass = (name, detail = '') => results.push({ ok: true, name, detail });
const fail = (name, detail) => results.push({ ok: false, name, detail });
const info = (name, detail) => results.push({ ok: null, name, detail });
const check = (name, problems, okDetail = '') => (problems.length ? fail(name, problems.slice(0, 8).join('; ') + (problems.length > 8 ? `; and ${problems.length - 8} more` : '')) : pass(name, okDetail));

const read = (file) => (fs.existsSync(file) ? fs.readFileSync(file, 'utf8') : null);
const walk = (dir, base = dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name), base) : [path.relative(base, path.join(dir, e.name))]));

const pages = fs.readdirSync(src).filter((f) => f.endsWith('.html')).sort();
const cssPath = path.join(src, 'assets', 'site.css');
const css = read(cssPath) || '';
const docs = Object.fromEntries(['DESIGN.md', 'decisions.md', 'views.md'].map((d) => [d, read(path.join(root, d))]));

// ---------------------------------------------------------------- files

check('The three documents exist beside source/', Object.entries(docs).filter(([, text]) => text === null).map(([name]) => `${name} is missing`));
// The log of annotations is written by `fig.mjs annotations` from the reader's output, which sits beside the package.
const annotations = read(path.join(root, 'annotations.md'));
const extractDir = path.join(root, '..', 'extract');
const extracted = fs.existsSync(extractDir) ? fs.readdirSync(extractDir).map((folder) => read(path.join(extractDir, folder, 'notes.json'))).filter(Boolean).map((text) => JSON.parse(text)) : [];
const sameText = (text) => text.replace(/[ \t]+$/gm, '');
check(
	'annotations.md logs every annotation the reader found',
	annotations === null
		? ['annotations.md is missing: run fig.mjs annotations <out>/extract --out <out>/handoff/annotations.md']
		: extracted.flatMap((frame) => [
			...(annotations.includes(`\`${frame.node.id}\``) ? [] : [`${frame.node.name} (${frame.node.id}) was extracted and is not listed`]),
			...frame.annotations.filter((a) => a.text && !sameText(annotations).includes(sameText(a.text))).map((a) => `a note on ${frame.node.name} is not in it: "${a.text.split('\n')[0].slice(0, 50)}"`),
		]).map((problem, i) => (i ? problem : `${problem}. Run fig.mjs annotations again`)),
	extracted.length ? `${extracted.length} extracted frame${extracted.length === 1 ? '' : 's'}, ${extracted.reduce((sum, frame) => sum + frame.annotations.length, 0)} notes on them` : 'no extract/ folder beside the package to compare it with',
);
check('source/ holds at least one page', pages.length ? [] : ['no .html file in source/'], `${pages.length} page${pages.length === 1 ? '' : 's'}`);
check('assets/site.css exists', css ? [] : ['source/assets/site.css is missing']);

const html = Object.fromEntries(pages.map((p) => [p, fs.readFileSync(path.join(src, p), 'utf8')]));
const attrs = (text, tags, names) => {
	const found = [];
	const tagPattern = new RegExp(`<(${tags.join('|')})\\b[^>]*>`, 'gi');
	for (const tag of text.match(tagPattern) || []) for (const name of names) for (const m of tag.matchAll(new RegExp(`\\s${name}="([^"]*)"`, 'gi'))) found.push({ tag, value: m[1] });
	return found;
};
const cssUrls = [...css.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map((m) => m[1]).concat([...css.matchAll(/@import\s+["']([^"']+)["']/g)].map((m) => m[1]));
const isRemote = (v) => /^(https?:)?\/\//i.test(v);
const isData = (v) => /^data:/i.test(v);

// Files a page loads, as opposed to places its links go.
const loaded = {};
for (const [page, text] of Object.entries(html)) {
	loaded[page] = [
		...attrs(text, ['link'], ['href']),
		...attrs(text, ['script', 'img', 'source', 'video', 'audio', 'iframe', 'embed', 'track'], ['src', 'poster']),
		...attrs(text, ['img', 'source'], ['srcset']).flatMap((a) => a.value.split(',').map((part) => ({ tag: a.tag, value: part.trim().split(/\s+/)[0] }))),
	].map((a) => a.value).filter((v) => v && !isData(v));
}

check(
	'Nothing is loaded from another host',
	[...Object.entries(loaded).flatMap(([page, list]) => list.filter(isRemote).map((v) => `${page} loads ${v}`)), ...cssUrls.filter(isRemote).map((v) => `site.css loads ${v}`)],
);

const escapes = (v) => /^(file:|\/|[A-Za-z]:\\)/.test(v) || path.relative(src, path.resolve(src, v)).startsWith('..');
const links = Object.fromEntries(Object.entries(html).map(([page, text]) => [page, attrs(text, ['a', 'area', 'form'], ['href', 'action']).map((a) => a.value)]));
check(
	'No path reaches outside source/',
	[
		...Object.entries(loaded).flatMap(([page, list]) => list.filter((v) => !isRemote(v) && escapes(v)).map((v) => `${page}: ${v}`)),
		...Object.entries(links).flatMap(([page, list]) => list.filter((v) => !isRemote(v) && !/^(#|mailto:|tel:)/.test(v) && escapes(v.split(/[?#]/)[0] || '.')).map((v) => `${page}: ${v}`)),
		...cssUrls.filter((v) => !isRemote(v) && !isData(v) && path.relative(src, path.resolve(path.dirname(cssPath), v)).startsWith('..')).map((v) => `site.css: ${v}`),
	],
);

const used = new Set();
const missing = [];
for (const [page, list] of Object.entries(loaded)) for (const v of list.filter((x) => !isRemote(x))) {
	const file = path.relative(src, path.resolve(src, v.split(/[?#]/)[0]));
	used.add(file);
	if (!fs.existsSync(path.join(src, file))) missing.push(`${page} → ${v}`);
}
for (const v of cssUrls.filter((x) => !isRemote(x) && !isData(x))) {
	const file = path.relative(src, path.resolve(path.dirname(cssPath), v.split(/[?#]/)[0]));
	used.add(file);
	if (!fs.existsSync(path.join(src, file))) missing.push(`site.css → ${v}`);
}
check('Every file a page or the stylesheet refers to exists', missing, `${used.size} files`);

const assets = fs.existsSync(path.join(src, 'assets')) ? walk(path.join(src, 'assets')).map((f) => path.join('assets', f)) : [];
const isLicence = (f) => /(^|\/)(OFL|LICEN[CS]E|COPYING)[^/]*$/i.test(f);
check('Nothing in assets/ is unused', assets.filter((f) => !used.has(f) && !isLicence(f)).map((f) => f));

check(
	'One stylesheet and one script, both in assets/',
	Object.entries(html).flatMap(([page, text]) => [
		...attrs(text, ['link'], ['href']).filter((a) => /rel="stylesheet"/i.test(a.tag) && a.value !== 'assets/site.css').map((a) => `${page} links ${a.value}`),
		...attrs(text, ['script'], ['src']).filter((a) => a.value !== 'assets/site.js').map((a) => `${page} runs ${a.value}`),
		.../<style\b/i.test(text) ? [`${page} has a <style> block`] : [],
		.../<script\b(?![^>]*\bsrc=)[^>]*>\s*\S/i.test(text) ? [`${page} has an inline script`] : [],
	]),
);

// ---------------------------------------------------------------- fonts

const faces = [...css.matchAll(/@font-face\s*\{([^}]*)\}/g)].map((m) => m[1]);
const fontFiles = faces.flatMap((body) => [...body.matchAll(/url\(\s*["']?([^"')]+)["']?\s*\)/g)].map((m) => m[1]));
const fontDir = path.join(src, 'assets', 'fonts');
const licences = fs.existsSync(fontDir) ? fs.readdirSync(fontDir).filter(isLicence) : [];
check(
	'Fonts are local files with a licence beside them',
	[
		...fontFiles.filter((v) => isRemote(v) || !path.relative(src, path.resolve(path.dirname(cssPath), v)).startsWith(path.join('assets', 'fonts'))).map((v) => `${v} is not in assets/fonts/`),
		...(fontFiles.length && !licences.length ? ['no licence file in assets/fonts/'] : []),
	],
	fontFiles.length ? `${fontFiles.length} font file${fontFiles.length === 1 ? '' : 's'}, ${licences.length} licence${licences.length === 1 ? '' : 's'}` : 'no @font-face rules: system fonts only',
);

// ---------------------------------------------------------------- shared chrome

const region = (text, tag) => {
	const open = text.search(new RegExp(`<${tag}\\b`, 'i'));
	const close = text.toLowerCase().lastIndexOf(`</${tag}>`);
	return open < 0 || close < 0 ? null : text.slice(open, close + tag.length + 3);
};
for (const tag of ['header', 'footer']) {
	const groups = new Map();
	for (const [page, text] of Object.entries(html)) {
		const part = region(text, tag);
		if (part === null) continue;
		groups.set(part, [...(groups.get(part) || []), page]);
	}
	const variants = [...groups.values()];
	if (variants.length <= 1) pass(`The ${tag} is identical in every page that has one`, `${variants[0]?.length || 0} page${variants[0]?.length === 1 ? '' : 's'}`);
	else if (variants.length === 2 && tag === 'header') info('Two headers in the set', `${variants.map((v) => v.join(', ')).join(' | ')}. Allowed when the design draws two: views.md must name both`);
	else fail(`The ${tag} is identical in every page that has one`, `${variants.length} versions: ${variants.map((v) => v.join(', ')).join(' | ')}`);
}

// ---------------------------------------------------------------- links and the documents

const pageSet = new Set(pages);
check(
	'Every internal link goes to a file in the set, or is # and recorded',
	Object.entries(links).flatMap(([page, list]) => list.filter((v) => !isRemote(v) && !/^(#|mailto:|tel:)/.test(v) && !fs.existsSync(path.join(src, v.split(/[?#]/)[0]))).map((v) => `${page} → ${v}`)),
);
const hashCount = Object.fromEntries(Object.entries(links).map(([page, list]) => [page, list.filter((v) => v === '#').length]));
info('Links to # per page, to match against the content status in views.md', Object.entries(hashCount).map(([page, n]) => `${page}: ${n}`).join(', '));

const views = docs['views.md'] || '';
check('views.md names every page in source/', pages.filter((p) => !views.includes(`\`${p}\``)).map((p) => `${p} is not in views.md`));
check(
	'Every page views.md lists as a file exists',
	[...new Set([...views.matchAll(/`([a-z0-9-]+(?:--[a-z0-9-]+)?\.html)`/g)].map((m) => m[1]))].filter((p) => !pageSet.has(p)).map((p) => `${p} is named in views.md and is not in source/`),
);
const section = (text, heading) => {
	const start = text.search(new RegExp(`^#{2,4} ${heading}`, 'mi'));
	if (start < 0) return null;
	const level = /^#+/.exec(text.slice(start))[0].length;
	const rest = text.slice(start + level + 1);
	const end = rest.search(new RegExp(`^#{1,${level}} `, 'm'));
	return end < 0 ? rest : rest.slice(0, end);
};
check('views.md has a content status with an entry per page', views ? pages.filter((p) => !(section(views, 'Content status') || '').includes(`\`${p}\``)).map((p) => `no entry for ${p}`) : ['views.md is missing']);
check(
	'decisions.md carries the content status, the designer\'s notes and the standards check',
	docs['decisions.md'] ? ['Content status', 'The designer.s notes', 'Standards'].filter((h) => section(docs['decisions.md'], h) === null).map((h) => `no "${h.replace('.', '’')}" section`) : ['decisions.md is missing'],
);

const visible = (text) => text.replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, '').replace(/<[^>]+>/g, ' ');
check('Nothing visible on a page says "placeholder"', Object.entries(html).filter(([, text]) => /placeholder|lorem ipsum/i.test(visible(text))).map(([page]) => page));

// ---------------------------------------------------------------- DESIGN.md against the stylesheet

const design = docs['DESIGN.md'] || '';
const front = /^---\n([\s\S]*?)\n---/.exec(design)?.[1] || '';
const block = (key) => {
	const lines = front.split('\n');
	const at = lines.findIndex((l) => l.startsWith(`${key}:`));
	if (at < 0) return [];
	const out = [];
	for (const line of lines.slice(at + 1)) {
		if (/^\S/.test(line)) break;
		out.push(line);
	}
	return out;
};
const rootBlock = /:root\s*\{([^}]*)\}/.exec(css)?.[1] || '';
const cssVar = (name) => new RegExp(`--${name}\\s*:\\s*([^;]+);`).exec(rootBlock)?.[1].trim();
const colours = new Map();
for (const line of block('colors')) {
	const m = /^\s+([a-z0-9-]+):\s*(?:\{\s*value:\s*)?"([^"]+)"/.exec(line);
	if (m) colours.set(m[1], m[2]);
}
check(
	'DESIGN.md\'s colours equal --color-<slug> in site.css',
	colours.size ? [...colours].filter(([slug, value]) => (cssVar(`color-${slug}`) || '').toLowerCase() !== value.toLowerCase()).map(([slug, value]) => `${slug}: DESIGN.md ${value}, site.css ${cssVar(`color-${slug}`) || 'has no --color-' + slug}`) : ['DESIGN.md has no colours in its frontmatter'],
	`${colours.size} colours`,
);
check('No palette slug collides with a class WordPress core uses', [...colours.keys()].filter((slug) => ['border', 'text', 'link'].includes(slug)).map((slug) => `${slug}: core puts has-${slug}-color on blocks, so name this colour by its role`));

// Contrast of the pairings DESIGN.md lists: `- [ink, canvas]`, with `large` or `ui` as a third item for the 3:1 cases.
const parse = (value) => {
	const hex = /^#([0-9a-f]{3,8})$/i.exec(value.trim())?.[1];
	if (hex) {
		const full = hex.length <= 4 ? [...hex].map((c) => c + c).join('') : hex;
		return { r: parseInt(full.slice(0, 2), 16), g: parseInt(full.slice(2, 4), 16), b: parseInt(full.slice(4, 6), 16), a: full.length === 8 ? parseInt(full.slice(6, 8), 16) / 255 : 1 };
	}
	const rgb = /^rgba?\(([^)]+)\)$/i.exec(value.trim())?.[1].split(/[,\s/]+/).filter(Boolean).map(Number);
	return rgb ? { r: rgb[0], g: rgb[1], b: rgb[2], a: rgb[3] ?? 1 } : null;
};
const over = (top, under) => ({ r: top.r * top.a + under.r * (1 - top.a), g: top.g * top.a + under.g * (1 - top.a), b: top.b * top.a + under.b * (1 - top.a), a: 1 });
const luminance = ({ r, g, b }) => [r, g, b].map((c) => c / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)).reduce((sum, c, i) => sum + c * [0.2126, 0.7152, 0.0722][i], 0);
const ratio = (a, b) => {
	const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
	return (hi + 0.05) / (lo + 0.05);
};
const pairs = block('pairs').map((l) => /^\s+-\s*\[\s*([a-z0-9-]+)\s*,\s*([a-z0-9-]+)\s*(?:,\s*(large|ui)\s*)?\]/.exec(l)).filter(Boolean);
if (!pairs.length) fail('DESIGN.md lists the colour pairings the pages use, under pairs', 'no pairs in the frontmatter, so contrast was not checked');
else {
	const low = [];
	const unknown = [];
	const seen = [];
	for (const [, fg, bg, kind] of pairs) {
		const front = parse(colours.get(fg) || '');
		const back = parse(colours.get(bg) || '');
		if (!front || !back) {
			unknown.push(`${fg} on ${bg}`);
			continue;
		}
		const value = ratio(over(front, back), back);
		const need = kind ? 3 : 4.5;
		seen.push({ fg, bg, value });
		if (value < need) low.push(`${fg} on ${bg} is ${value.toFixed(2)}:1, needs ${need}:1`);
	}
	check('Every colour pairing reaches its contrast', [...low, ...unknown.map((u) => `${u}: a colour is not in DESIGN.md`)], `${pairs.length} pairings; lowest: ${seen.sort((a, b) => a.value - b.value).slice(0, 1).map((p) => `${p.fg} on ${p.bg} at ${p.value.toFixed(2)}:1`)}`);
}

// ---------------------------------------------------------------- standards readable from the source

check(
	'The type-rendering baseline is in site.css',
	['font-synthesis: none', 'text-rendering: geometricPrecision', '-webkit-font-smoothing: antialiased', '-moz-osx-font-smoothing: grayscale', 'text-wrap-style: pretty', 'scroll-behavior: smooth'].filter((rule) => !css.replace(/\s+/g, ' ').includes(rule)).map((rule) => `missing ${rule}`),
);
check('site.css writes text-wrap-style, never the text-wrap shorthand', /(^|[\s;{])text-wrap\s*:/.test(css) ? ['the text-wrap shorthand also sets text-wrap-mode and undoes an inherited nowrap: write text-wrap-style'] : []);
check('Motion stops for prefers-reduced-motion', /animation|transition/.test(css) && !/prefers-reduced-motion:\s*reduce/.test(css) ? ['site.css animates and has no prefers-reduced-motion rule'] : []);
check('A focus indicator is styled', /:focus-visible/.test(css) ? [] : ['site.css has no :focus-visible rule']);

for (const [page, text] of Object.entries(html)) {
	const problems = [];
	if (!/<html[^>]*\slang="[a-z-]+"/i.test(text)) problems.push('no lang on <html>');
	if (!/<meta[^>]*name="viewport"/i.test(text)) problems.push('no viewport meta');
	if (/user-scalable\s*=\s*no|maximum-scale\s*=\s*1(\.0)?\b/i.test(text)) problems.push('the viewport meta blocks zoom');
	const levels = [...text.matchAll(/<h([1-6])\b/gi)].map((m) => Number(m[1]));
	if (levels.filter((l) => l === 1).length !== 1) problems.push(`${levels.filter((l) => l === 1).length} h1 elements`);
	levels.forEach((l, i) => { if (i && l > levels[i - 1] + 1) problems.push(`h${levels[i - 1]} is followed by h${l}`); });
	for (const tag of ['header', 'main', 'footer']) if (!new RegExp(`<${tag}\\b`, 'i').test(text)) problems.push(`no <${tag}>`);
	const navs = text.match(/<nav\b[^>]*>/gi) || [];
	if (navs.length > 1 && navs.some((n) => !/aria-label(ledby)?=/.test(n))) problems.push('more than one <nav> and one has no label');
	if (!/<a[^>]*href="#[a-z][^"]*"[^>]*>\s*skip/i.test(text)) problems.push('no skip link');
	for (const img of text.match(/<img\b[^>]*>/gi) || []) if (!/\salt="/i.test(img)) problems.push(`an image has no alt: ${/src="([^"]*)"/.exec(img)?.[1]}`);
	for (const a of text.match(/<a\b[^>]*target="_blank"[^>]*>/gi) || []) if (!/new (tab|window)/i.test(a)) problems.push('a link opens a new tab without saying so in its label');
	const labelled = new Set([...text.matchAll(/<label\b[^>]*\sfor="([^"]+)"/gi)].map((m) => m[1]));
	for (const field of text.match(/<(input|select|textarea)\b[^>]*>/gi) || []) {
		if (/type="(hidden|submit|button|image|reset)"/i.test(field)) continue;
		const id = /\sid="([^"]+)"/.exec(field)?.[1];
		if (!(id && labelled.has(id)) && !/aria-label(ledby)?=/.test(field)) problems.push(`a field has no label: ${field.slice(0, 60)}`);
	}
	check(`${page}: structure, landmarks, alt text and labels`, problems);
}

// ---------------------------------------------------------------- report

for (const r of results) console.log(`${r.ok === null ? 'NOTE' : r.ok ? 'PASS' : 'FAIL'}  ${r.name}${r.detail ? ` — ${r.detail}` : ''}`);
const failed = results.filter((r) => r.ok === false).length;
console.log(`\n${failed ? `${failed} check${failed === 1 ? '' : 's'} failed` : 'Every check passed'}: ${results.filter((r) => r.ok).length} passed, ${results.filter((r) => r.ok === null).length} to read.`);
console.log('Not checked here, because it needs a browser: sideways scroll at each width, target sizes, keyboard order, and the comparison with the exports. See page-audit.js.');
process.exit(failed ? 1 : 0);
