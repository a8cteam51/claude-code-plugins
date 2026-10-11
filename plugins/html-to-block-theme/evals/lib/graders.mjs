import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { evalsDir, pluginDir } from './inventory.mjs';

// A pattern is a JavaScript regular expression source. Dot matches a line break. A leading
// (?i) asks for case-insensitive matching: JavaScript has no inline flags, and a pattern
// that does not compile fails every answer without saying why.
export function toRegex(source) {
  const text = String(source);
  return text.startsWith('(?i)') ? new RegExp(text.slice(4), 'is') : new RegExp(text, 's');
}

const asList = (value) => (value === undefined ? [] : Array.isArray(value) ? value : [value]);

// The fenced blocks of an answer, by what they hold. An answer with no fence is all markup.
export function extract(answer) {
  const fences = [...answer.matchAll(/```([A-Za-z0-9_-]*)[^\n]*\n([\s\S]*?)```/g)].map((match) => ({
    lang: match[1].toLowerCase(),
    body: match[2],
  }));
  if (fences.length === 0) {
    return { markup: answer, css: '', json: '' };
  }
  const pick = (test) => fences.filter(test).map((fence) => fence.body).join('\n');
  return {
    markup: pick((fence) => fence.body.includes('<!-- wp:') || ['html', 'markup', 'wp'].includes(fence.lang)),
    // Without its comments: a model explains itself there, and names what it did not do.
    css: pick((fence) => ['css', 'scss'].includes(fence.lang)).replace(/\/\*[\s\S]*?\*\//g, ''),
    json: pick((fence) => ['json', 'jsonc'].includes(fence.lang)),
  };
}

// Block delimiters in order, with their attributes and nesting depth. A delimiter whose
// attributes are not JSON is kept with `invalid` set, so a grader can see it.
export function parseBlocks(markup) {
  const blocks = [];
  let depth = 0;
  for (const match of markup.matchAll(/<!--\s+(\/)?wp:([a-z0-9-]+(?:\/[a-z0-9-]+)?)\s+(?:(\{[\s\S]*?\})\s+)?(\/)?-->/g)) {
    const [, closing, rawName, rawAttrs, selfClosing] = match;
    if (closing) {
      depth = Math.max(0, depth - 1);
      continue;
    }
    const block = { name: rawName.includes('/') ? rawName : `core/${rawName}`, attrs: {}, depth, json: '{}' };
    if (rawAttrs) {
      try {
        block.attrs = JSON.parse(rawAttrs);
        block.json = JSON.stringify(block.attrs);
      } catch {
        block.invalid = true;
        block.json = rawAttrs;
      }
    }
    blocks.push(block);
    if (!selfClosing) {
      depth++;
    }
  }
  return blocks;
}

// name, name_matches, attrs_match, attrs_lack (patterns over the attributes as JSON) and
// top_level. Every condition given must hold.
function satisfies(block, predicate) {
  if (predicate.name !== undefined && block.name !== predicate.name) {
    return false;
  }
  if (predicate.name_matches !== undefined && !toRegex(predicate.name_matches).test(block.name)) {
    return false;
  }
  if (predicate.top_level !== undefined && (block.depth === 0) !== predicate.top_level) {
    return false;
  }
  return (
    asList(predicate.attrs_match).every((pattern) => toRegex(pattern).test(block.json)) &&
    asList(predicate.attrs_lack).every((pattern) => !toRegex(pattern).test(block.json))
  );
}

function fixtureTheme(target) {
  fs.cpSync(path.join(evalsDir, 'fixtures', 'theme'), target, { recursive: true });
}

// The plugin's own gate, run on the answer. `as: template` puts it in the theme's
// templates; anything else is page content.
function audit(markup, options) {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'h2bt-eval-audit-'));
  try {
    const theme = path.join(work, 'theme');
    const content = path.join(work, 'content');
    fixtureTheme(theme);
    fs.mkdirSync(content);
    const target = options.as === 'template' ? path.join(theme, 'templates', 'eval-answer.html') : path.join(content, 'answer.html');
    fs.writeFileSync(target, markup);
    let output;
    try {
      output = execFileSync(
        'bash',
        [path.join(pluginDir, 'scripts', 'standards-audit.sh'), '--theme-dir', theme, '--layout', 'standalone', '--content-dir', content],
        { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] },
      );
    } catch (error) {
      output = `${error.stdout || ''}`;
    }
    const line = output.split('\n').reverse().find((candidate) => candidate.startsWith('H2BT_AUDIT_'));
    if (!line) {
      throw new Error('standards-audit.sh printed no H2BT_AUDIT_ line');
    }
    return Object.fromEntries([...line.matchAll(/(\w+)=(\S+)/g)].map((pair) => [pair[1], pair[2]]));
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
}

// What WordPress prints for the answer on the eval site: the HTML and the block-supports
// CSS. One call at a time, and each result is kept for the life of the process.
const rendered = new Map();
export function render(markup, sitePath) {
  if (rendered.has(markup)) {
    return rendered.get(markup);
  }
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'h2bt-eval-render-'));
  try {
    const file = path.join(work, 'answer.html');
    fs.writeFileSync(file, markup.trim() === '' ? '<!-- wp:paragraph --><p></p><!-- /wp:paragraph -->' : markup);
    const output = execFileSync('bash', [path.join(pluginDir, 'scripts', 'render-probe.sh'), '--site-path', sitePath, '--markup', file], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    const [, html = '', css = ''] = /--- html ---\n([\s\S]*?)--- block-supports css ---\n([\s\S]*?)H2BT_PROBE_OK/.exec(output) || [];
    const result = { html, css, version: (/wp=(\S+)/.exec(output) || [])[1] };
    rendered.set(markup, result);
    return result;
  } finally {
    fs.rmSync(work, { recursive: true, force: true });
  }
}

export const needsSite = (checks) => checks.some((check) => check.render !== undefined || (check.any_of || []).some(needsSite));

// Every check must hold. Returns { pass, failed: [what did not hold] }. Checks that need
// the eval site are skipped, and reported as skipped, when there is no site path.
export function grade(answer, checks, { sitePath } = {}) {
  const parts = extract(answer);
  const blocks = parseBlocks(parts.markup);
  const failed = [];
  const skipped = [];
  const texts = { answer, markup: parts.markup, css: parts.css, json: parts.json };

  for (const check of checks) {
    const [kind] = Object.keys(check);
    const value = check[kind];
    const label = `${kind}: ${typeof value === 'string' ? value : JSON.stringify(value)}`;
    let ok;

    const textCheck = /^(answer|markup|css|json)_(matches|lacks)$/.exec(kind);
    if (textCheck) {
      const found = asList(value).map((pattern) => toRegex(pattern).test(texts[textCheck[1]]));
      ok = textCheck[2] === 'matches' ? found.every(Boolean) : !found.some(Boolean);
    } else if (kind === 'some_block') {
      ok = blocks.some((block) => satisfies(block, value));
    } else if (kind === 'no_block') {
      ok = !blocks.some((block) => satisfies(block, value));
    } else if (kind === 'every_block') {
      const subjects = blocks.filter((block) => satisfies(block, value.of));
      ok = subjects.length > 0 && subjects.every((block) => satisfies(block, value.is));
    } else if (kind === 'any_of') {
      // Several right answers: each entry is a list of checks, and one list holding is enough.
      const outcomes = value.map((checks) => grade(answer, checks, { sitePath }));
      if (outcomes.every((outcome) => outcome.skipped.length)) {
        skipped.push(label);
        continue;
      }
      ok = outcomes.some((outcome) => outcome.pass && outcome.skipped.length === 0);
    } else if (kind === 'valid_blocks') {
      ok = blocks.length > 0 && !blocks.some((block) => block.invalid);
    } else if (kind === 'audit') {
      const counters = audit(parts.markup, value);
      ok = asList(value.clean).every((counter) => counters[counter] === '0');
    } else if (kind === 'render') {
      if (!sitePath) {
        skipped.push(label);
        continue;
      }
      const output = render(parts.markup, sitePath);
      ok =
        asList(value.html_matches).every((pattern) => toRegex(pattern).test(output.html)) &&
        asList(value.html_lacks).every((pattern) => !toRegex(pattern).test(output.html)) &&
        asList(value.css_matches).every((pattern) => toRegex(pattern).test(output.css)) &&
        asList(value.css_lacks).every((pattern) => !toRegex(pattern).test(output.css));
    } else {
      throw new Error(`Unknown check: ${kind}`);
    }

    if (!ok) {
      failed.push(label);
    }
  }

  return { pass: failed.length === 0, failed, skipped };
}
