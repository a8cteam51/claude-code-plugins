#!/usr/bin/env node
/**
 * Serve the canonical userscript so Tampermonkey can install it.
 *
 * Tampermonkey intercepts top-level navigations to a URL ending in `.user.js`
 * and shows its own install/update page. It will not do that for a `file://`
 * URL unless the user has enabled file access for the extension, so the
 * install flow goes through a short-lived loopback server instead.
 *
 * Usage:  node scripts/serve-userscript.js [--port N] [--timeout SEC]
 * Prints: VERSION=<x.y.z> and INSTALL_URL=<url>, then serves until --timeout
 *         (default 5 min) or until killed. Tampermonkey fetches the file
 *         twice — once to render its install page, once when the user clicks
 *         Install — so the server must outlive the human, not the first hit.
 *
 * Exits non-zero if the @version metadata and the VERSION constant disagree —
 * the plugin is the source of truth for which version should be installed, so
 * the two must never drift.
 */
'use strict';

const http = require('http');
const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, '..', 'skills', 'annotate', 'assets', 'page-annotator.user.js');
const NAME = path.basename(FILE);

const arg = (flag, fallback) => {
  const i = process.argv.indexOf(flag);
  return i === -1 ? fallback : Number(process.argv[i + 1]);
};
const port = arg('--port', 0);
const timeoutMs = arg('--timeout', 300) * 1000;

let source;
try {
  source = fs.readFileSync(FILE, 'utf8');
} catch (err) {
  console.error(`Cannot read ${FILE}: ${err.message}`);
  process.exit(1);
}

const metaVersion = (source.match(/^\/\/ @version\s+(\S+)/m) || [])[1];
const constVersion = (source.match(/^\s*const VERSION = '([^']+)'/m) || [])[1];
if (!metaVersion || !constVersion) {
  console.error('Could not read both the @version metadata and the VERSION constant.');
  process.exit(1);
}
if (metaVersion !== constVersion) {
  console.error(`Version mismatch in ${NAME}: @version is ${metaVersion} but VERSION is ${constVersion}.`);
  console.error('Update both before serving — Tampermonkey upgrades on @version, the plugin probes VERSION.');
  process.exit(1);
}

let hits = 0;

const stop = (why) => {
  console.log(why);
  process.exit(0);
};

const server = http.createServer((req, res) => {
  const wanted = req.url.split('?')[0] === '/' + NAME;
  if (!wanted) {
    res.writeHead(404, { 'Content-Type': 'text/plain' });
    return res.end('not found');
  }
  res.writeHead(200, {
    // Tampermonkey keys off the .user.js suffix, but a JS content type keeps
    // Chrome from offering to download it if the extension is missing.
    'Content-Type': 'text/javascript; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  res.end(source);
  // Hit 1 is Tampermonkey rendering its install page; hit 2 is the user
  // clicking Install. Keep serving either way — the caller kills this.
  console.log(`SERVED=${++hits}`);
});

server.listen(port, '127.0.0.1', () => {
  const { port: actual } = server.address();
  console.log(`VERSION=${metaVersion}`);
  console.log(`INSTALL_URL=http://127.0.0.1:${actual}/${NAME}`);
});

setTimeout(() => stop('DONE=timeout'), timeoutMs).unref?.();
