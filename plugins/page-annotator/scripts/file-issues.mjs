#!/usr/bin/env node
/**
 * Turn an annotation payload into GitHub issues — one issue per annotation.
 *
 * Usage:
 *   node scripts/file-issues.mjs --payload <payload.json> --meta <meta.json>
 *                                [--only 1,3] [--dry-run]
 *
 *   --payload  The overlay's state node, verbatim (schema version 3).
 *   --meta     Per-annotation extras Claude supplies:
 *                {
 *                  "repo": "owner/name",
 *                  "annotations": {
 *                    "1": { "title": "…", "screenshot": "https://github.com/user-attachments/assets/…" }
 *                  }
 *                }
 *              Both keys inside an annotation are optional. `repo` overrides
 *              the one captured in the payload.
 *   --only     Comma-separated annotation ids; everything else is skipped.
 *   --dry-run  Render the bodies to stdout and stop. Nothing is created.
 *
 * Output:
 *   --dry-run  Human-readable rendered issues on stdout (drives the preview
 *              Claude shows the user before anything is published).
 *   otherwise  JSON on stdout: {"1": {"number": 42, "url": "https://…"}}
 *              covering only the issues created by this run.
 *   Progress and errors always go to stderr.
 *
 * Annotations that already carry an `issue` are skipped — that is what makes a
 * second batch, or a re-run after a partial failure, safe.
 *
 * Exits non-zero if any issue failed to create; successfully created ones are
 * still printed, so their numbers can be stamped back into the page.
 */

import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const REPO_RE = /^[\w.-]+\/[\w.-]+$/;
const PLUGIN_URL = 'https://github.com/a8cteam51/claude-code-plugins';

/* ------------------------------ arguments ------------------------------ */

const argv = process.argv.slice(2);
const flag = (name) => {
  const i = argv.indexOf(name);
  return i === -1 ? undefined : argv[i + 1];
};
const has = (name) => argv.includes(name);

const die = (msg) => {
  console.error(msg);
  process.exit(1);
};

const payloadPath = flag('--payload');
const metaPath = flag('--meta');
const dryRun = has('--dry-run');

if (!payloadPath) die('Missing --payload <file>. See the header of this script for usage.');

const readJson = (file, label) => {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch (err) {
    die(`Cannot read the ${label} file ${file}: ${err.message}`);
  }
  try {
    return JSON.parse(raw);
  } catch (err) {
    die(`The ${label} file ${file} is not valid JSON: ${err.message}`);
  }
};

const payload = readJson(payloadPath, 'payload');
const meta = metaPath ? readJson(metaPath, 'meta') : {};
const metaFor = (id) => (meta.annotations && meta.annotations[String(id)]) || {};

if (payload.version !== 3) {
  console.error(`Warning: payload schema version is ${payload.version}, expected 3. ` +
    'Fields may be missing; update the installed userscript.');
}

const repo = (meta.repo || payload.repo || '').trim();
if (!REPO_RE.test(repo)) {
  die(`No usable repository. Got ${JSON.stringify(repo)}; expected "owner/name". ` +
    'Set it in the overlay\'s repo field or pass it as "repo" in --meta.');
}

const all = Array.isArray(payload.annotations) ? payload.annotations : [];
if (!all.length) die('The payload contains no annotations.');

const only = flag('--only');
const wanted = only ? new Set(only.split(',').map((s) => s.trim()).filter(Boolean)) : null;

const skipped = [];
const queue = [];
for (const ann of all) {
  if (ann.issue) { skipped.push(`#${ann.id} (already filed as #${ann.issue.number})`); continue; }
  if (wanted && !wanted.has(String(ann.id))) { skipped.push(`#${ann.id} (not in --only)`); continue; }
  queue.push(ann);
}
for (const s of skipped) console.error(`Skipping annotation ${s}`);
if (!queue.length) die('Nothing left to file — every annotation was skipped.');

/* ------------------------------ rendering ------------------------------ */

// Table cells: newlines and pipes both break a markdown row.
const cell = (v) => {
  const s = String(v ?? '').replace(/\|/g, '\\|').replace(/\s*\n\s*/g, ' ').trim();
  return s || '—';
};
const code = (v) => {
  const s = cell(v);
  return s === '—' ? s : `\`${s.replace(/`/g, 'ˋ')}\``;
};

// A fence long enough to survive backticks inside the content.
const fence = (content, lang = '') => {
  const longest = (String(content).match(/`+/g) || [])
    .reduce((m, s) => Math.max(m, s.length), 0);
  const bar = '`'.repeat(Math.max(3, longest + 1));
  return `${bar}${lang}\n${content}\n${bar}`;
};

const table = (rows) => [
  '| | |',
  '|---|---|',
  ...rows.filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `| ${k} | ${v} |`),
].join('\n');

function browserFrom(ua = '') {
  const pick = (re, label) => {
    const m = ua.match(re);
    return m && `${label} ${m[1]}`;
  };
  return pick(/\bEdg\/([\d.]+)/, 'Edge')
    || pick(/\bOPR\/([\d.]+)/, 'Opera')
    || pick(/\bChrome\/([\d.]+)/, 'Chrome')
    || pick(/\bFirefox\/([\d.]+)/, 'Firefox')
    || pick(/\bVersion\/([\d.]+).*Safari/, 'Safari')
    || 'Unknown';
}

function titleFor(ann) {
  const explicit = (metaFor(ann.id).title || ann.title || '').trim();
  if (explicit) return explicit.slice(0, 200);
  // Fall back to the note's first sentence — Claude normally supplies a title,
  // but the script must not produce an untitled issue if it doesn't.
  const first = String(ann.note || '').split(/(?<=[.!?])\s+|\n/)[0].trim();
  const base = first || String(ann.note || '').trim() || `Annotation #${ann.id}`;
  return base.length > 70 ? `${base.slice(0, 69).trimEnd()}…` : base;
}

function bodyFor(ann) {
  const page = payload.page || {};
  const env = payload.env || {};
  const vp = page.viewport || {};
  const rect = ann.rect || {};
  const shot = metaFor(ann.id).screenshot;
  const parts = [];

  parts.push(String(ann.note || '').trim());

  if (shot) parts.push(`![Annotated screenshot](${shot})`);

  parts.push('### Where\n\n' + table([
    ['Page', page.url ? `[${cell(page.title || page.url)}](${page.url})` : cell(page.title)],
    ['Element', code(ann.selector)],
    ['Tag', code(ann.tag && `<${ann.tag}>`)],
    ['Text', code(ann.text)],
    ['Position', rect.width !== undefined
      ? `${rect.x}, ${rect.y} — ${rect.width} × ${rect.height}` : undefined],
  ]));

  parts.push('### Environment\n\n' + table([
    ['Browser', cell(browserFrom(env.userAgent))],
    ['Platform', cell(env.platform)],
    ['Viewport', vp.width ? `${vp.width} × ${vp.height}${vp.dpr ? ` @${vp.dpr}x` : ''}` : undefined],
    ['Screen', env.screen && env.screen.width ? `${env.screen.width} × ${env.screen.height}` : undefined],
    ['Language', cell(env.language)],
    ['Time zone', cell(env.timezone)],
    ['Colour scheme', cell(env.colorScheme)],
    ['Reduced motion', env.reducedMotion === undefined ? undefined : (env.reducedMotion ? 'yes' : 'no')],
    ['Captured', cell(ann.createdAt || page.capturedAt)],
  ]));

  const details = [];
  if (ann.outerHTML) details.push(fence(ann.outerHTML, 'html'));
  const styles = Object.entries(ann.styles || {}).filter(([, v]) => v);
  if (styles.length) {
    details.push([
      '| Property | Computed value |',
      '|---|---|',
      ...styles.map(([k, v]) => `| \`${k}\` | ${code(v)} |`),
    ].join('\n'));
  }
  if (env.userAgent) details.push(`User agent: ${code(env.userAgent)}`);
  if (details.length) {
    parts.push([
      '<details>',
      '<summary>Element markup and computed styles</summary>',
      '',
      details.join('\n\n'),
      '',
      '</details>',
    ].join('\n'));
  }

  parts.push('---\n\n' +
    `<sub>Filed from [page-annotator](${PLUGIN_URL}) · annotation #${ann.id}` +
    `${payload.script ? ` · overlay ${payload.script}` : ''}</sub>`);

  return parts.filter(Boolean).join('\n\n') + '\n';
}

/* -------------------------------- output -------------------------------- */

if (dryRun) {
  for (const ann of queue) {
    process.stdout.write(`\n${'='.repeat(72)}\n`);
    process.stdout.write(`ANNOTATION #${ann.id} → ${repo}\n`);
    process.stdout.write(`TITLE: ${titleFor(ann)}\n`);
    if (!metaFor(ann.id).screenshot) process.stdout.write('NOTE: no screenshot attached\n');
    process.stdout.write(`${'='.repeat(72)}\n\n`);
    process.stdout.write(bodyFor(ann));
  }
  console.error(`\nDry run: ${queue.length} issue(s) would be created in ${repo}. Nothing was published.`);
  process.exit(0);
}

/* ------------------------------- creating ------------------------------- */

const gh = (args) => execFileSync('gh', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });

// Fail before publishing anything if the repo isn't reachable.
let visibility = '';
try {
  const info = JSON.parse(gh(['repo', 'view', repo, '--json', 'isPrivate,viewerPermission']));
  visibility = info.isPrivate ? 'private' : 'public';
  console.error(`Target: ${repo} (${visibility}, your permission: ${info.viewerPermission || 'unknown'})`);
} catch (err) {
  die(`Cannot reach ${repo} via gh: ${(err.stderr || err.message || '').toString().trim()}\n` +
    'Check the repository name, and that gh is installed and authenticated (`gh auth status`).');
}

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'page-annotator-'));
const results = {};
let failures = 0;

for (const ann of queue) {
  const title = titleFor(ann);
  const bodyFile = path.join(tmp, `issue-${ann.id}.md`);
  fs.writeFileSync(bodyFile, bodyFor(ann), 'utf8');
  try {
    const out = gh(['issue', 'create', '--repo', repo, '--title', title, '--body-file', bodyFile]).trim();
    const url = (out.match(/https:\/\/\S+\/issues\/\d+/) || [])[0];
    if (!url) throw new Error(`gh reported success but printed no issue URL:\n${out}`);
    const number = Number(url.split('/').pop());
    results[ann.id] = { number, url };
    console.error(`Filed annotation #${ann.id} → #${number} ${url}`);
  } catch (err) {
    failures++;
    console.error(`FAILED annotation #${ann.id} (${title}): ` +
      `${(err.stderr || err.message || '').toString().trim()}`);
  }
}

fs.rmSync(tmp, { recursive: true, force: true });

process.stdout.write(JSON.stringify(results, null, 2) + '\n');

if (failures) {
  console.error(`\n${failures} of ${queue.length} issue(s) failed. ` +
    'The successful ones are in the JSON above — stamp those back before retrying.');
  process.exit(1);
}
console.error(`\nCreated ${queue.length} issue(s) in ${repo}.`);
