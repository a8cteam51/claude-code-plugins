import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import YAML from 'yaml';
import { grade } from '../lib/graders.mjs';
import { evalsDir, findItems, pluginDir, tokens } from '../lib/inventory.mjs';
import { loadConfig, loadRegistry } from '../lib/registry.mjs';
import { JUDGEABLE } from '../lib/summary.mjs';

// Everything that can be checked without calling a model.
//
//   1. The plugin's model and effort pins agree with each other and with the eval config.
//   2. The registry lines up with the plugin: every section in scope has a kind, and every
//      probe's anchor finds exactly one passage. A guide that grew fails here until the new
//      section is classified.
//   3. Every probe's graders accept its known-good answer and reject its known-bad one.
//
// With --site, the checks that need the eval site run too: the graders that read what
// WordPress prints, and the environment facts, each tried against the installed tools.
//
//   node scripts/check.mjs [--site]

const withSite = process.argv.includes('--site');
const config = loadConfig();
let failed = 0;
const fail = (message) => {
  failed++;
  console.log(`  FAIL ${message}`);
};

console.log('Pins');
try {
  const line = execFileSync('bash', [path.join(pluginDir, 'scripts', 'model-pin.sh'), '--check'], { encoding: 'utf8' }).trim();
  console.log(`  ${line}`);
} catch (error) {
  fail(`model-pin.sh --check\n${error.stdout || error.message}`);
}

console.log('Registry');
const registry = loadRegistry();
registry.problems.forEach(fail);
const scoped = registry.items.filter((item) => item.inScope);
const judgeable = scoped.filter((item) => JUDGEABLE.includes(item.kind));
const size = (items) => tokens(items.reduce((total, item) => total + item.bytes, 0));
console.log(`  ${Object.keys(registry.kinds.files).length} files in scope, ${scoped.length} passages, ${size(scoped)} tokens`);
console.log(`  a model eval can judge ${judgeable.length} passages (${size(judgeable)} tokens); probes speak for ${judgeable.filter((item) => item.probes).length} (${size(judgeable.filter((item) => item.probes))} tokens)`);

// The facts about the tools are anchored to passages too, so that an edit cannot orphan one.
const environmentFile = path.join(evalsDir, 'registry', 'environment.yaml');
const environment = fs.existsSync(environmentFile) ? YAML.parse(fs.readFileSync(environmentFile, 'utf8')) || [] : [];
for (const entry of environment) {
  for (const cover of entry.covers || []) {
    const file = registry.files.find((candidate) => path.basename(candidate) === cover.file) || cover.file;
    const matches = registry.files.includes(file) ? findItems(registry.itemsOf(file), cover.match).length : 0;
    if (matches !== 1) {
      fail(`environment ${entry.id}: "${cover.match}" matches ${matches} passages in ${cover.file}, not 1`);
    }
  }
}
console.log(`  ${environment.length} facts about the tools have a script`);

console.log(`Graders (${registry.probes.length} probes)`);
const options = withSite ? { sitePath: config.site_path } : {};
let needSite = 0;
for (const probe of registry.probes) {
  if (!probe.grade || probe.pass_example === undefined || probe.fail_example === undefined) {
    continue;
  }
  let good;
  let bad;
  try {
    good = grade(probe.pass_example, probe.grade, options);
    bad = grade(probe.fail_example, probe.grade, options);
  } catch (error) {
    fail(`${probe.id}: ${error.message}`);
    continue;
  }
  if (!good.pass) {
    fail(`${probe.id}: the known-good answer is rejected by ${good.failed.join(' | ')}`);
  }
  if (bad.pass && bad.skipped.length === 0) {
    fail(`${probe.id}: the known-bad answer is accepted`);
  }
  if (good.skipped.length) {
    needSite++;
  }
}
if (needSite) {
  console.log(`  ${needSite} probes have checks that need the eval site: run with --site`);
}

if (withSite) {
  console.log('Environment (facts about the tools, tried on the eval site)');
  const results = [];
  for (const entry of environment) {
    const run = spawnSync('bash', ['-c', entry.run], { cwd: config.site_path, env: { ...process.env, SITE: config.site_path }, encoding: 'utf8' });
    const output = `${run.stdout}${run.stderr}`;
    const holds = entry.holds_when_output_lacks ? !output.includes(entry.holds_when_output_lacks) : output.includes(entry.holds_when_output_has);
    results.push({ id: entry.id, claim: entry.claim, holds });
    console.log(`  ${holds ? 'holds           ' : 'not reproduced  '} ${entry.id}: ${entry.claim}`);
  }
  fs.mkdirSync(path.join(evalsDir, 'results'), { recursive: true });
  fs.writeFileSync(path.join(evalsDir, 'results', 'environment.json'), `${JSON.stringify(results, null, 2)}\n`);
}

console.log(failed ? `\n${failed} problem${failed === 1 ? '' : 's'}.` : '\nH2BT_EVAL_CHECK_OK');
process.exit(failed ? 1 : 0);
