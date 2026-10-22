#!/usr/bin/env node
// Load each sampled page in a real browser and record what a visitor would get: status, console errors,
// failed requests, the page's structure, key computed styles, fonts, broken images and a screenshot.
//
//   node snapshot.mjs https://site.example --paths <dir>/frontend-paths.txt --out <dir>/frontend/source
//
// Logged out, GET only, no proxy, desktop and mobile viewports. Uses the installed Google Chrome (playwright-core
// downloads no browser); set CHROME_PATH to use another Chromium build. Writes snapshot.json and
// screenshots/ under --out.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright-core';

const { values, positionals } = parseArgs({
	allowPositionals: true,
	options: { paths: { type: 'string' }, out: { type: 'string' }, 'max-height': { type: 'string', default: '5000' } },
});
const base = (positionals[0] || '').replace(/\/$/, '');
if (!base || !values.paths || !values.out) {
	console.error('usage: node snapshot.mjs <base URL> --paths <file> --out <dir> [--max-height 5000]');
	process.exit(2);
}
const host = new URL(base).host;
const paths = readFileSync(values.paths, 'utf8').split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'));
const shots = join(values.out, 'screenshots');
mkdirSync(shots, { recursive: true });

const VIEWPORTS = {
	desktop: { viewport: { width: 1366, height: 900 } },
	mobile: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
const STYLE_SELECTORS = ['body', 'header', 'nav', 'main', 'footer', 'h1', 'h2', 'p', 'a', 'button'];
const STYLE_PROPS = ['font-family', 'font-size', 'font-weight', 'line-height', 'color', 'background-color'];

// Make URLs comparable across hosts: own host becomes {host}, cache-busting version args go.
const norm = (url) => {
	try {
		const u = new URL(url, base);
		for (const k of ['ver', 'v', 'm', 'minify', '_']) u.searchParams.delete(k);
		const own = u.host === host;
		return (own ? '{host}' : u.host) + u.pathname + (u.search || '');
	} catch {
		return url;
	}
};

const launch = process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' };
// Direct connections only. Chrome otherwise follows the system proxy, and a request through the Automattic
// proxy makes WordPress.com render its admin and debug bars, so the target would never match the source.
const browser = await chromium.launch({ headless: true, args: ['--no-proxy-server'], ...launch });
const pages = [];

for (const path of paths) {
	for (const [vpName, vp] of Object.entries(VIEWPORTS)) {
		const context = await browser.newContext({ ...vp, reducedMotion: 'reduce', userAgent: undefined, ignoreHTTPSErrors: false });
		const page = await context.newPage();
		const consoleMsgs = [];
		const failed = [];
		const requests = [];
		page.on('console', (m) => {
			if (['error', 'warning'].includes(m.type())) consoleMsgs.push({ type: m.type(), text: m.text().slice(0, 300).split(host).join('{host}') });
		});
		page.on('pageerror', (e) => consoleMsgs.push({ type: 'pageerror', text: String(e.message).slice(0, 300).split(host).join('{host}') }));
		page.on('requestfailed', (r) => failed.push({ url: norm(r.url()), status: 0, type: r.resourceType(), error: r.failure()?.errorText || '' }));
		page.on('response', (r) => {
			requests.push(r.url());
			if (r.status() >= 400 && r.url() !== page.url()) failed.push({ url: norm(r.url()), status: r.status(), type: r.request().resourceType() });
		});

		const entry = { path, viewport: vpName };
		try {
			const res = await page.goto(base + path, { waitUntil: 'load', timeout: 45000 });
			await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
			entry.status = res ? res.status() : 0;
			entry.final = norm(page.url());
			// Scroll through the page so lazy-loaded images and blocks load, then return to the top.
			await page.evaluate(async () => {
				for (let y = 0; y < document.documentElement.scrollHeight && y < 15000; y += 600) {
					window.scrollTo(0, y);
					await new Promise((r) => setTimeout(r, 80));
				}
				window.scrollTo(0, 0);
			});
			await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {});
			await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' }).catch(() => {});
			entry.dom = await page.evaluate(
				({ selectors, props }) => {
					const box = (el) => {
						if (!el) return null;
						const r = el.getBoundingClientRect();
						return { x: Math.round(r.x), y: Math.round(r.y + window.scrollY), w: Math.round(r.width), h: Math.round(r.height) };
					};
					const styles = {};
					for (const sel of selectors) {
						const el = document.querySelector(sel);
						if (!el) continue;
						const cs = getComputedStyle(el);
						styles[sel] = Object.fromEntries(props.map((p) => [p, cs.getPropertyValue(p)]));
					}
					const meta = (n) => document.querySelector(`meta[name="${n}"]`)?.content || null;
					const fonts = { loaded: [], failed: [] };
					document.fonts.forEach((f) => {
						const name = `${f.family.replace(/["']/g, '')} ${f.weight} ${f.style}`;
						if (f.status === 'loaded') fonts.loaded.push(name);
						if (f.status === 'error') fonts.failed.push(name);
					});
					return {
						title: document.title,
						lang: document.documentElement.lang,
						description: meta('description'),
						robots: meta('robots'),
						canonical: document.querySelector('link[rel=canonical]')?.href || null,
						bodyClasses: [...document.body.classList].sort(),
						headings: [...document.querySelectorAll('h1,h2,h3')].slice(0, 40).map((h) => `${h.tagName}: ${h.textContent.trim().replace(/\s+/g, ' ').slice(0, 120)}`),
						counts: Object.fromEntries(['a', 'img', 'form', 'input', 'iframe', 'video', 'script', 'link[rel=stylesheet]', 'style', 'section', 'article'].map((s) => [s, document.querySelectorAll(s).length])),
						stylesheets: [...document.querySelectorAll('link[rel=stylesheet]')].map((l) => l.href),
						scripts: [...document.querySelectorAll('script[src]')].map((s) => s.src),
						iframes: [...document.querySelectorAll('iframe[src]')].map((f) => f.src),
						brokenImages: [...document.querySelectorAll('img')].filter((i) => i.complete && i.naturalWidth === 0 && (i.currentSrc || i.src)).map((i) => i.currentSrc || i.src).slice(0, 30),
						textLength: Math.round((document.body.innerText || '').length / 50) * 50,
						height: document.documentElement.scrollHeight,
						boxes: Object.fromEntries(['header', 'nav', 'main', 'footer', 'h1'].map((s) => [s, box(document.querySelector(s))])),
						styles,
						fonts,
					};
				},
				{ selectors: STYLE_SELECTORS, props: STYLE_PROPS },
			);
			for (const k of ['stylesheets', 'scripts', 'iframes', 'brokenImages']) entry.dom[k] = entry.dom[k].map((u) => (/^https?:/.test(u) ? norm(u) : u));
			if (entry.dom.canonical) entry.dom.canonical = norm(entry.dom.canonical);
			entry.mixedContent = base.startsWith('https:') ? [...new Set(requests.filter((u) => u.startsWith('http:')).map(norm))] : [];
			entry.otherHosts = [...new Set(requests.map((u) => { try { return new URL(u).host; } catch { return ''; } }).filter((h) => h && h !== host))].sort();
			const file = `${path.replace(/[^a-z0-9]+/gi, '_').replace(/^_|_$/g, '') || 'home'}-${vpName}.png`;
			const height = Math.min(entry.dom.height, Number(values['max-height']));
			await page.screenshot({ path: join(shots, file), clip: { x: 0, y: 0, width: vp.viewport.width, height }, fullPage: true });
			entry.screenshot = `screenshots/${file}`;
		} catch (e) {
			entry.status = entry.status ?? 0;
			entry.error = String(e.message).split('\n')[0].slice(0, 200);
		}
		entry.console = consoleMsgs;
		entry.failedRequests = failed;
		pages.push(entry);
		process.stdout.write(`${entry.status} ${vpName.padEnd(7)} ${path}${entry.error ? '  ERROR ' + entry.error : ''}\n`);
		await context.close();
	}
}
await browser.close();
writeFileSync(join(values.out, 'snapshot.json'), JSON.stringify({ base, host, taken: new Date().toISOString(), pages }, null, 1));
console.log(`snapshot of ${paths.length} paths written to ${values.out}/snapshot.json`);
