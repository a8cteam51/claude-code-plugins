import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { workspacesDir, workspacesEnvVar } from './workspaces-dir.mjs';

const evalsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const executable = process.platform === 'win32' ? 'promptfoo.cmd' : 'promptfoo';
const binDir = path.join(evalsDir, 'node_modules', '.bin');
const requestedRepeats = Number.parseInt(process.argv[2] || '3', 10);
const repeats = Number.isFinite(requestedRepeats) && requestedRepeats > 0 ? requestedRepeats : 3;
const outputFile = path.join(evalsDir, 'results', 'latest.json');

function runNode(script) {
  return spawnSync(process.execPath, [path.join(evalsDir, 'scripts', script)], {
    cwd: evalsDir,
    env: process.env,
    stdio: 'inherit',
  });
}

fs.mkdirSync(path.join(evalsDir, 'results'), { recursive: true });
fs.rmSync(outputFile, { force: true });

const reset = runNode('reset-workspaces.mjs');
if (reset.status !== 0) {
  process.exit(reset.status ?? 1);
}

const result = spawnSync(executable, [
  'eval',
  '--config',
  'promptfooconfig.yaml',
  '--no-cache',
  '--repeat',
  String(repeats),
  '--output',
  outputFile,
], {
  cwd: evalsDir,
  env: {
    ...process.env,
    PATH: `${binDir}:${process.env.PATH}`,
    // promptfoo interpolates {{ env.* }} inside provider configs, which is how the config
    // reaches workspaces that live outside this repo. Running promptfoo directly without
    // this set leaves the template unrendered.
    [workspacesEnvVar]: workspacesDir,
  },
  stdio: 'inherit',
});

runNode('clean-workspaces.mjs');

if (!fs.existsSync(outputFile)) {
  process.exit(result.status ?? 1);
}

const output = JSON.parse(fs.readFileSync(outputFile, 'utf8'));
const errors = output.results?.stats?.errors || 0;
if (errors > 0) {
  console.error(`The eval completed with ${errors} provider error${errors === 1 ? '' : 's'}.`);
  process.exit(1);
}

// A recall case only earns its slot when the unaided arm fails it. Summarise the split per
// case so dead-weight cases are obvious rather than buried in a green table.
const RETRIEVAL_METRIC = 'Opened the guide';

const emptyArm = () => ({ pass: 0, total: 0, opened: 0, content: 0 });
const byCase = new Map();

for (const item of output.results?.results || []) {
  const caseName = item.testCase?.description || 'Unnamed case';
  const arm = /no skill/.test(item.provider?.label || '') ? 'off' : 'on';
  const entry = byCase.get(caseName) || { off: emptyArm(), on: emptyArm(), disclosure: false };
  const parts = item.gradingResult?.componentResults || [];
  const retrieval = parts.filter((part) => part.assertion?.metric === RETRIEVAL_METRIC);
  const content = parts.filter((part) => part.assertion?.metric !== RETRIEVAL_METRIC);

  if (retrieval.length > 0) {
    entry.disclosure = true;
  }
  entry[arm].total += 1;
  if (item.success) {
    entry[arm].pass += 1;
  }
  if (retrieval.some((part) => part.pass)) {
    entry[arm].opened += 1;
  }
  if (content.length > 0 && content.every((part) => part.pass)) {
    entry[arm].content += 1;
  }
  byCase.set(caseName, entry);
}

console.log('\nSeparation per case (skill-off should fail, skill-on should pass):');
for (const [caseName, entry] of byCase) {
  console.log(`  ${caseName}`);

  // A disclosure case is a pointer check on the skill arm, not an A/B. The baseline has no
  // reference file to open, so it can never pass the retrieval assertion — reporting that
  // as "separates" would be a tautology. Report the quadrant instead.
  if (entry.disclosure) {
    const on = entry.on;
    let verdict = 'mixed, run more repeats';
    if (on.opened === 0) {
      verdict = 'POINTER FAILED: SKILL.md never sent it to the guide';
    } else if (on.opened === on.total && on.content === on.total) {
      verdict = 'pointer works and the guide is clear';
    } else if (on.opened === on.total) {
      verdict = 'pointer works, but the guide did not yield the answer';
    }
    console.log('    disclosure case — measures SKILL.md\'s pointer, not skill-vs-no-skill');
    console.log(`    skill-on:  opened ${on.opened}/${on.total} · content ${on.content}/${on.total} · ${verdict}`);
    const baseline = entry.off.content === entry.off.total
      ? 'content is base knowledge — only the retrieval assertion separates'
      : `content ${entry.off.content}/${entry.off.total} unaided`;
    console.log(`    skill-off: ${baseline}`);
    continue;
  }

  let note = 'mixed, run more repeats';
  if (entry.off.pass === 0 && entry.on.pass === entry.on.total) {
    note = 'separates';
  } else if (entry.off.pass === entry.off.total && entry.on.pass === entry.on.total) {
    note = 'DEAD WEIGHT: the base model already knows this';
  } else if (entry.on.pass === 0) {
    note = 'REGRESSION: the skill fails its own rule';
  }
  console.log(`    skill-off ${entry.off.pass}/${entry.off.total} · skill-on ${entry.on.pass}/${entry.on.total} · ${note}`);
}

console.log('\nThe eval completed. Assertion failures are part of the comparison.');
process.exit(0);
