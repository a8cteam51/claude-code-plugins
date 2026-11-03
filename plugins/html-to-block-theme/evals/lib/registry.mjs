import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import YAML from 'yaml';
import { evalsDir, findItems, pluginDir, readItems } from './inventory.mjs';

export function loadConfig() {
  const config = JSON.parse(fs.readFileSync(path.join(evalsDir, 'eval.config.json'), 'utf8'));
  const site = process.env.H2BT_EVAL_SITE || config.site_path;
  return { ...config, site_path: site.startsWith('~') ? path.join(os.homedir(), site.slice(1)) : site };
}

// Every Markdown file the plugin loads into a model: the skill, its references, the agents.
export function pluginFiles() {
  const found = [];
  for (const directory of ['skills', 'agents']) {
    for (const entry of fs.readdirSync(path.join(pluginDir, directory), { withFileTypes: true, recursive: true })) {
      if (entry.isFile() && entry.name.endsWith('.md')) {
        found.push(path.relative(pluginDir, path.join(entry.parentPath || entry.path, entry.name)));
      }
    }
  }
  return found.sort();
}

// The registry joins three things: the plugin's text, cut into items; the kind of each
// section, which says what instrument can judge it; and the probes, each anchored to the
// items it speaks for. `problems` lists everything that does not line up.
export function loadRegistry() {
  const kinds = YAML.parse(fs.readFileSync(path.join(evalsDir, 'registry', 'kinds.yaml'), 'utf8'));
  const problems = [];
  const all = pluginFiles();
  const byBase = new Map(all.map((file) => [path.basename(file), file]));
  const itemsByFile = new Map();

  const itemsOf = (file) => {
    if (!itemsByFile.has(file)) {
      const scope = kinds.files[file];
      const items = readItems(file);
      for (const item of items) {
        item.inScope = Boolean(scope);
        item.kind = scope ? scope.sections?.[item.section] : undefined;
        if (scope && item.kind === undefined) {
          item.kind = 'unclassified';
        }
        for (const override of scope?.overrides || []) {
          if (findItems([item], override.match).length) {
            item.kind = override.kind;
          }
        }
      }
      if (scope) {
        const present = new Set(items.map((item) => item.section));
        for (const section of present) {
          if (scope.sections?.[section] === undefined) {
            problems.push(`${file}: section "${section}" has no kind in registry/kinds.yaml`);
          }
        }
        for (const section of Object.keys(scope.sections || {})) {
          if (!present.has(section)) {
            problems.push(`${file}: registry/kinds.yaml names a section that is gone: "${section}"`);
          }
        }
        for (const override of scope.overrides || []) {
          if (findItems(items, override.match).length !== 1) {
            problems.push(`${file}: override "${override.match}" matches ${findItems(items, override.match).length} items, not 1`);
          }
          if (!kinds.kinds[override.kind]) {
            problems.push(`${file}: override "${override.match}" names an unknown kind "${override.kind}"`);
          }
        }
        for (const kind of Object.values(scope.sections || {})) {
          if (!kinds.kinds[kind]) {
            problems.push(`${file}: unknown kind "${kind}"`);
          }
        }
      }
      itemsByFile.set(file, items);
    }
    return itemsByFile.get(file);
  };

  for (const file of Object.keys(kinds.files)) {
    if (!all.includes(file)) {
      problems.push(`registry/kinds.yaml names a file that is gone: ${file}`);
      continue;
    }
    itemsOf(file);
  }

  const probes = [];
  const probesDir = path.join(evalsDir, 'registry', 'probes');
  for (const name of fs.readdirSync(probesDir).filter((entry) => entry.endsWith('.yaml')).sort()) {
    for (const probe of YAML.parse(fs.readFileSync(path.join(probesDir, name), 'utf8')) || []) {
      probe.source = name;
      probe.items = [];
      for (const cover of probe.covers || []) {
        const file = byBase.get(cover.file) || cover.file;
        if (!all.includes(file)) {
          problems.push(`${probe.id}: covers a file that is not in the plugin: ${cover.file}`);
          continue;
        }
        const matches = findItems(itemsOf(file), cover.match);
        if (matches.length !== 1) {
          problems.push(`${probe.id}: "${cover.match}" matches ${matches.length} items in ${cover.file}, not 1`);
          continue;
        }
        probe.items.push(matches[0]);
        (matches[0].probes ||= []).push(probe.id);
      }
      for (const field of ['id', 'consumer', 'task', 'grade', 'pass_example', 'fail_example']) {
        if (probe[field] === undefined) {
          problems.push(`${probe.id || name}: missing ${field}`);
        }
      }
      if (probes.some((other) => other.id === probe.id)) {
        problems.push(`${probe.id}: used twice`);
      }
      probe.kind = probe.items.find((item) => item.kind)?.kind || 'unclassified';
      probes.push(probe);
    }
  }

  return { kinds, files: all, itemsOf, items: [...itemsByFile.values()].flat(), probes, problems };
}
