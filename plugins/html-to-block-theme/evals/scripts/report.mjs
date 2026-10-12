import fs from 'node:fs';
import path from 'node:path';
import { evalsDir } from '../lib/inventory.mjs';
import { loadConfig, loadRegistry } from '../lib/registry.mjs';
import { loadSamples, resultsDir, saveGrades } from '../lib/samples.mjs';
import { markdown, printSummary, summarise } from '../lib/summary.mjs';

// Grades the stored answers and writes reports/<model>@<effort>.md and .json. No model is
// called. --compare <model>@<effort> adds what changed since that report.
//
//   node scripts/report.mjs [--model id] [--effort level] [--compare name]

const args = process.argv.slice(2);
const option = (name) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : undefined);

const config = loadConfig();
config.model = option('model') || config.model;
config.effort = option('effort') || config.effort;

const registry = loadRegistry();
if (registry.problems.length) {
  console.error(registry.problems.map((problem) => `  ${problem}`).join('\n'));
  process.exit(1);
}

const summary = summarise(registry, loadSamples(config), config);
saveGrades(config);

const reports = path.join(evalsDir, 'reports');
const compare = option('compare');
const previous = compare ? JSON.parse(fs.readFileSync(path.join(reports, `${compare}.json`), 'utf8')) : undefined;

fs.mkdirSync(reports, { recursive: true });
const slim = { ...summary, probes: summary.probes.map(({ items, ...probe }) => ({ ...probe, covers: items.map((item) => item.id) })) };
fs.writeFileSync(path.join(reports, `${summary.run.name}.json`), `${JSON.stringify(slim, null, 2)}\n`);
const routingFile = path.join(resultsDir(config), 'routing.json');
const environmentFile = path.join(evalsDir, 'results', 'environment.json');
const extras = {
  routing: fs.existsSync(routingFile) ? JSON.parse(fs.readFileSync(routingFile, 'utf8')) : undefined,
  environment: fs.existsSync(environmentFile) ? JSON.parse(fs.readFileSync(environmentFile, 'utf8')) : undefined,
};
fs.writeFileSync(path.join(reports, `${summary.run.name}.md`), markdown(summary, previous, extras));

printSummary(summary);
console.log(`\nWrote reports/${summary.run.name}.md`);
