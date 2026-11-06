#!/usr/bin/env node
// Pick a small, stable sample of pages to snapshot on both sides of a migration.
//
//   node sample.mjs https://source.example --out <dir>/frontend-paths.txt [--per-sitemap 2] [--max 25]
//
// Takes the first few URLs from each sub-sitemap (one per post type and taxonomy), plus the home page,
// a search, a 404 and the WooCommerce pages when the source has them. The same file is then used for
// the source and the target, so both are compared page for page. Edit it by hand to add pages that matter.
import { writeFileSync } from 'node:fs';
import { parseArgs } from 'node:util';

const { values, positionals } = parseArgs({
	allowPositionals: true,
	options: { out: { type: 'string' }, 'per-sitemap': { type: 'string', default: '2' }, max: { type: 'string', default: '25' } },
});
const base = (positionals[0] || '').replace(/\/$/, '');
if (!base || !values.out) {
	console.error('usage: node sample.mjs <source base URL> --out <file> [--per-sitemap 2] [--max 25]');
	process.exit(2);
}
const perSitemap = Number(values['per-sitemap']);
const max = Number(values.max);
const UA = 'Mozilla/5.0 (compatible; t51-migration-check/1.0)';

async function get(url) {
	try {
		const res = await fetch(url, { headers: { 'User-Agent': UA }, redirect: 'follow', signal: AbortSignal.timeout(20000) });
		return { status: res.status, body: res.ok ? await res.text() : '' };
	} catch {
		return { status: 0, body: '' };
	}
}

const locs = (xml) => [...xml.matchAll(/<loc>\s*([^<\s]+)\s*<\/loc>/g)].map((m) => m[1].replace(/&amp;/g, '&'));
const pathOf = (url) => {
	const u = new URL(url);
	return u.pathname + u.search;
};

const paths = ['/'];
const add = (p) => {
	if (!paths.includes(p)) paths.push(p);
};

// Sitemaps: an index lists one sitemap per post type or taxonomy; take a few pages from each.
for (const index of ['/wp-sitemap.xml', '/sitemap_index.xml', '/sitemap.xml']) {
	const { status, body } = await get(base + index);
	if (status !== 200 || !body.includes('<loc>')) continue;
	const entries = locs(body);
	const children = entries.filter((l) => /\.xml(\?|$)/.test(l));
	if (!children.length) {
		entries.slice(0, perSitemap * 3).forEach((l) => add(pathOf(l)));
		break;
	}
	for (const child of children.slice(0, 15)) {
		if (/users|author/i.test(child)) continue; // Author archives add little and expose usernames.
		const sub = await get(child);
		locs(sub.body).filter((l) => !/\.xml(\?|$)/.test(l)).slice(0, perSitemap).forEach((l) => add(pathOf(l)));
	}
	break;
}

// WooCommerce pages, only where the source answers 200 for them.
for (const p of ['/shop/', '/cart/', '/checkout/', '/my-account/']) {
	if ((await get(base + p)).status === 200) add(p);
}
add('/?s=test');
add('/this-page-should-404-t51/');

const sample = paths.slice(0, max);
writeFileSync(values.out, sample.join('\n') + '\n');
console.log(`${sample.length} paths written to ${values.out}`);
