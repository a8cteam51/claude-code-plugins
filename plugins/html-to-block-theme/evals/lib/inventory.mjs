import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const evalsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
export const pluginDir = path.resolve(evalsDir, '..');

export const squash = (text) => text.replace(/\s+/g, ' ').trim();

// Roughly four bytes to a token. Good enough to compare passages with each other.
export const tokens = (bytes) => Math.round(bytes / 4);

const LIST_ITEM = /^\s*(?:[-*]|\d+\.)\s+\S/;
const HEADING = /^(#{1,6})\s+(.*\S)\s*$/;
const TABLE_RULE = /^\|\s*:?-{3,}/;

// A guide is a run of sections, and a section is a run of items. An item is what one rule
// usually occupies: a list item at any depth with the lines that continue it, a table row,
// or a paragraph with the code block that follows it. A nested list item is its own item,
// because a step's sub-points are separate rules. Items are the unit the registry points
// at, the unit an ablation removes, and the unit the report counts.
export function readItems(file) {
  const absolute = path.join(pluginDir, file);
  const lines = fs.readFileSync(absolute, 'utf8').split('\n');
  const items = [];
  let section = '(top)';
  let open = null;
  let inFence = false;
  let blankBefore = false;

  const close = (end) => {
    if (!open) {
      return;
    }
    let last = end;
    while (last > open.start && lines[last - 1].trim() === '') {
      last--;
    }
    const text = lines.slice(open.start, last).join('\n');
    const key = squash(text);
    items.push({
      file,
      section: open.section,
      type: open.type,
      start: open.start,
      end: last,
      text,
      key,
      bytes: Buffer.byteLength(text),
      id: crypto.createHash('sha1').update(`${file}\n${key}`).digest('hex').slice(0, 10),
    });
    open = null;
  };
  const start = (index, type) => {
    close(index);
    open = { start: index, type, section };
  };

  let index = 0;
  if (lines[0] === '---') {
    const end = lines.indexOf('---', 1);
    if (end > 0) {
      section = '(frontmatter)';
      start(0, 'frontmatter');
      close(end + 1);
      section = '(top)';
      index = end + 1;
    }
  }

  for (; index < lines.length; index++) {
    const line = lines[index];

    if (/^\s*```/.test(line)) {
      if (!inFence && !open) {
        start(index, 'code');
      }
      inFence = !inFence;
      blankBefore = false;
      continue;
    }
    if (inFence) {
      continue;
    }
    if (line.trim() === '') {
      blankBefore = true;
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      close(index);
      section = heading[2];
    } else if (LIST_ITEM.test(line)) {
      start(index, 'list');
    } else if (line.startsWith('|')) {
      // A header row and its rule are furniture; each body row is an item.
      const isRule = TABLE_RULE.test(line);
      const isHeader = TABLE_RULE.test(lines[index + 1] || '');
      close(index);
      if (!isRule && !isHeader) {
        start(index, 'row');
        close(index + 1);
      }
    } else if (/^\s/.test(line)) {
      // Indented: nested under whatever is open.
      if (!open) {
        start(index, 'paragraph');
      }
    } else if (!open || blankBefore || open.type === 'row') {
      start(index, 'paragraph');
    }
    blankBefore = false;
  }
  close(lines.length);

  return items;
}

// Every item whose text holds the anchor. A probe's anchor must find exactly one.
export function findItems(items, match) {
  const needle = squash(match);
  return items.filter((item) => item.key.includes(needle));
}

// The file with some of its items cut out, for the arm that asks "and without this?".
export function withoutItems(file, items) {
  const lines = fs.readFileSync(path.join(pluginDir, file), 'utf8').split('\n');
  const cut = new Set();
  for (const item of items.filter((candidate) => candidate.file === file)) {
    for (let line = item.start; line < item.end; line++) {
      cut.add(line);
    }
  }
  return lines.filter((_, line) => !cut.has(line)).join('\n');
}

export function stripFrontmatter(text) {
  return text.startsWith('---\n') ? text.slice(text.indexOf('\n---', 3) + 4).replace(/^\n+/, '') : text;
}
