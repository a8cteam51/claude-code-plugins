#!/usr/bin/env node
// Compare two front-end snapshots, page by page and viewport by viewport, and report what got worse.
//
//   node compare.mjs <dir>/frontend/source <dir>/frontend/target [--out <dir>/frontend/REPORT.md] [--visual 3]
//
// Only differences count: an error present on both sides is the site's, not the migration's. Each
// difference is an ISSUE (likely a migration problem) or a NOTE (expected on WordPress.com, or too small
// to matter). Exit 1 when there is at least one issue.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import pixelmatch from 'pixelmatch';
import pngjs from 'pngjs';

const { PNG } = pngjs;
const { values, positionals } = parseArgs({
	allowPositionals: true,
	options: { out: { type: 'string' }, visual: { type: 'string', default: '3' }, json: { type: 'string' } },
});
const [srcDir, dstDir] = positionals;
if (!srcDir || !dstDir) {
	console.error('usage: node compare.mjs <source snapshot dir> <target snapshot dir> [--out REPORT.md] [--visual 3]');
	process.exit(2);
}
const VISUAL_ISSUE = Number(values.visual); // percent of pixels that differ
const src = JSON.parse(readFileSync(join(srcDir, 'snapshot.json'), 'utf8'));
const dst = JSON.parse(readFileSync(join(dstDir, 'snapshot.json'), 'utf8'));

// Hosts that belong to the platforms. Differences involving them are expected when the host changes.
// gaug.es is Pressable's own visitor tracker, injected into every Pressable page; it is not part of the site.
const PLATFORM = /(^|\.)((wp|wordpress|wpcomstaging|gravatar|jetpack|videopress)\.com|wp\.me|pressable\.com|mystagingwebsite\.com|gaug\.es)$/;
// Body classes and robots values the quarantine or platform add on their own.
const EXPECTED_BODY = /^(wp-custom-logo|logged-in|admin-bar|no-customize-support|customize-support|wpcom|atomic|is-|theme-)/;

const findings = [];
const add = (level, page, what, detail = '') => findings.push({ level, page, what, detail });
const hostOf = (u) => (u.startsWith('{host}') ? '{host}' : u.split('/')[0]);
const diff = (a = [], b = []) => {
	const sa = new Set(a);
	const sb = new Set(b);
	return { gone: [...sa].filter((x) => !sb.has(x)), added: [...sb].filter((x) => !sa.has(x)) };
};
const key = (p) => `${p.path} [${p.viewport}]`;
const dstByKey = new Map(dst.pages.map((p) => [key(p), p]));
const srcHost = src.host;

function visual(s, d) {
	const a = join(srcDir, s.screenshot);
	const b = join(dstDir, d.screenshot);
	if (!existsSync(a) || !existsSync(b)) return null;
	const pa = PNG.sync.read(readFileSync(a));
	const pb = PNG.sync.read(readFileSync(b));
	const w = Math.min(pa.width, pb.width);
	const h = Math.min(pa.height, pb.height);
	const crop = (p) => {
		const out = new PNG({ width: w, height: h });
		PNG.bitblt(p, out, 0, 0, w, h, 0, 0);
		return out;
	};
	const ca = crop(pa);
	const cb = crop(pb);
	const out = new PNG({ width: w, height: h });
	const n = pixelmatch(ca.data, cb.data, out.data, w, h, { threshold: 0.1 });
	const file = d.screenshot.replace(/\.png$/, '.diff.png');
	writeFileSync(join(dstDir, file), PNG.sync.write(out));
	return { percent: Math.round((n / (w * h)) * 1000) / 10, heightSource: pa.height, heightTarget: pb.height, file };
}

for (const s of src.pages) {
	const page = key(s);
	const d = dstByKey.get(page);
	if (!d) {
		add('NOTE', page, 'not in the target snapshot');
		continue;
	}
	if (s.status !== d.status) {
		add(s.status === 200 ? 'ISSUE' : 'NOTE', page, `status ${s.status} on source, ${d.status} on target`);
	}
	if (d.error && !s.error) add('ISSUE', page, 'page failed to load on target', d.error);
	if (!s.dom || !d.dom) continue;
	const sd = s.dom;
	const dd = d.dom;

	// Content and structure: same database, so these should match exactly.
	if (sd.title !== dd.title) add('ISSUE', page, 'title differs', `"${sd.title}" → "${dd.title}"`);
	const h = diff(sd.headings, dd.headings);
	if (h.gone.length || h.added.length) add('ISSUE', page, 'headings differ', [...h.gone.map((x) => `- ${x}`), ...h.added.map((x) => `+ ${x}`)].slice(0, 12).join('\n'));
	if (sd.canonical !== dd.canonical) add(dd.canonical && dd.canonical.includes(srcHost) ? 'ISSUE' : 'NOTE', page, 'canonical differs', `${sd.canonical} → ${dd.canonical}`);
	if (sd.robots !== dd.robots) add('NOTE', page, 'robots meta differs (the quarantine sets noindex until cutover)', `${sd.robots} → ${dd.robots}`);
	if (Math.abs(sd.textLength - dd.textLength) > Math.max(200, sd.textLength * 0.05)) add('ISSUE', page, 'amount of text differs', `about ${sd.textLength} → ${dd.textLength} characters`);
	for (const [sel, n] of Object.entries(sd.counts)) {
		// Script, style and stylesheet counts change with the platform; the asset lists below say which ones matter.
		if (['script', 'style', 'link[rel=stylesheet]', 'iframe'].includes(sel)) continue;
		const m = dd.counts[sel] ?? 0;
		if (n === m) continue;
		const big = Math.abs(n - m) > Math.max(2, n * 0.1);
		add(big ? 'ISSUE' : 'NOTE', page, `number of ${sel} elements differs`, `${n} → ${m}`);
	}
	const bc = diff(sd.bodyClasses, dd.bodyClasses);
	const bcReal = [...bc.gone, ...bc.added].filter((c) => !EXPECTED_BODY.test(c));
	if (bcReal.length) add('NOTE', page, 'body classes differ', [...bc.gone.map((x) => `- ${x}`), ...bc.added.map((x) => `+ ${x}`)].join(' '));

	// Assets: a stylesheet or script the source loads and the target does not is the classic migration break.
	for (const k of ['stylesheets', 'scripts']) {
		const a = diff(sd[k], dd[k]);
		const kind = k === 'scripts' ? 'script' : 'stylesheet';
		// WordPress.com runs the Gutenberg plugin, so a core block asset can be served from the plugin instead.
		const tail = (u) => u.split('/').slice(-2).join('/');
		const replaced = (x) => /\/wp-includes\//.test(x) && a.added.find((y) => y.includes('/plugins/gutenberg/') && tail(y) === tail(x));
		for (const x of a.gone) {
			const sub = replaced(x);
			if (sub) {
				add('NOTE', page, `${kind} served by the Gutenberg plugin on target instead of core`, `${x} → ${sub}`);
				continue;
			}
			const platform = PLATFORM.test(hostOf(x));
			add(platform ? 'NOTE' : 'ISSUE', page, `${kind} missing on target${platform ? ' (platform asset)' : ''}`, x);
		}
		for (const x of a.added) {
			if (a.gone.some((g) => replaced(g) === x)) continue;
			add('NOTE', page, `${kind} only on target${PLATFORM.test(hostOf(x)) ? ' (platform asset)' : ''}`, x);
		}
	}

	// Styling and layout.
	for (const [sel, props] of Object.entries(sd.styles)) {
		const t = dd.styles[sel];
		if (!t) {
			add('NOTE', page, `<${sel}> not found on target`);
			continue;
		}
		const changed = Object.entries(props).filter(([p, v]) => t[p] !== v).map(([p, v]) => `${p}: ${v} → ${t[p]}`);
		if (changed.length) add('ISSUE', page, `computed style of <${sel}> differs`, changed.join('\n'));
	}
	const f = diff(sd.fonts.loaded, dd.fonts.loaded);
	if (f.gone.length) add('ISSUE', page, 'fonts loaded on source but not on target', f.gone.join(', '));
	const ff = diff(sd.fonts.failed, dd.fonts.failed);
	if (ff.added.length) add('ISSUE', page, 'fonts failed on target', ff.added.join(', '));
	if (sd.height && Math.abs(sd.height - dd.height) / sd.height > 0.1) add('ISSUE', page, 'page height differs by more than 10%', `${sd.height}px → ${dd.height}px`);
	for (const [sel, b] of Object.entries(sd.boxes)) {
		const t = dd.boxes[sel];
		if (!b || !t) {
			if (b && !t) add('ISSUE', page, `<${sel}> missing on target`);
			continue;
		}
		if (Math.abs(b.h - t.h) > Math.max(40, b.h * 0.15) || Math.abs(b.w - t.w) > 20) add('NOTE', page, `<${sel}> size differs`, `${b.w}×${b.h} → ${t.w}×${t.h}`);
	}
	const bi = diff(sd.brokenImages, dd.brokenImages);
	if (bi.added.length) add('ISSUE', page, 'images broken on target', bi.added.slice(0, 10).join('\n'));

	// Errors: only new ones count.
	const ce = diff(s.console.map((c) => `${c.type}: ${c.text}`), d.console.map((c) => `${c.type}: ${c.text}`));
	for (const x of ce.added) add(/^(error|pageerror)/.test(x) ? 'ISSUE' : 'NOTE', page, 'new console message on target', x);
	const fr = diff(s.failedRequests.map((r) => `${r.status || r.error} ${r.url}`), d.failedRequests.map((r) => `${r.status || r.error} ${r.url}`));
	for (const x of fr.added) add(PLATFORM.test(hostOf(x.split(' ')[1] || '')) ? 'NOTE' : 'ISSUE', page, 'request failed on target', x);
	const mc = diff(s.mixedContent, d.mixedContent);
	if (mc.added.length) add('ISSUE', page, 'mixed content on target', mc.added.join('\n'));
	const refs = (d.otherHosts || []).filter((x) => x === srcHost || /mystagingwebsite\.com$|pressable\.com$/.test(x));
	if (refs.length) add('ISSUE', page, 'target still loads from the old host', refs.join(', '));

	// Pixels last: noisy, so a large difference is an issue and a small one a note.
	const v = visual(s, d);
	if (v && v.percent >= VISUAL_ISSUE) add('ISSUE', page, `${v.percent}% of pixels differ`, `see ${v.file}`);
	else if (v && v.percent >= 0.5) add('NOTE', page, `${v.percent}% of pixels differ`, `see ${v.file}`);
}

// The same difference on many pages is one finding: group by what and detail, list the pages.
const grouped = new Map();
for (const x of findings) {
	const k = `${x.level}\u0000${x.what}\u0000${x.detail}`;
	if (!grouped.has(k)) grouped.set(k, { ...x, pages: [] });
	grouped.get(k).pages.push(x.page);
}
const total = src.pages.length;
const groups = [...grouped.values()].sort((a, b) => b.pages.length - a.pages.length);
const issues = groups.filter((x) => x.level === 'ISSUE');
const notes = groups.filter((x) => x.level === 'NOTE');
const where = (g) => (g.pages.length === total ? `all ${total} pages` : g.pages.length > 4 ? `${g.pages.length} of ${total} pages, e.g. ${g.pages.slice(0, 3).join(', ')}` : g.pages.join(', '));
const lines = [
	`# Front-end comparison`,
	'',
	`- Source: ${src.base} (snapshot ${src.taken})`,
	`- Target: ${dst.base} (snapshot ${dst.taken})`,
	`- Pages compared: ${total / 2} paths × 2 viewports`,
	`- **Result: ${issues.length ? 'DIFFERENCES' : 'MATCH'}** — ${issues.length} issues, ${notes.length} notes`,
	'',
	'Content differences (headings, text, links, page height) can be activity on the source since the last sync, not a',
	'migration fault. Check them against the data parity result before treating them as a problem.',
	'',
];
for (const [label, list] of [['Issues', issues], ['Notes', notes]]) {
	if (!list.length) continue;
	lines.push(`## ${label}`, '');
	for (const x of list) {
		lines.push(`- **${x.what}** — ${where(x)}`);
		if (x.detail) lines.push(...x.detail.split('\n').map((l) => `    ${l}`));
	}
	lines.push('');
}
const report = lines.join('\n');
if (values.out) writeFileSync(values.out, report);
if (values.json) writeFileSync(values.json, JSON.stringify(groups, null, 1));
console.log(report.split('\n').slice(0, 8).join('\n'));
console.log(`RESULT: ${issues.length ? 'DIFFERENCES' : 'MATCH'} (${issues.length} issues, ${notes.length} notes)`);
process.exit(issues.length ? 1 : 0);
