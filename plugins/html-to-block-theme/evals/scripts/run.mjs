import fs from 'node:fs';
import { ask, pool } from '../lib/agent.mjs';
import { ARMS, sampleHash, systemPrompt } from '../lib/context.mjs';
import { loadConfig, loadRegistry } from '../lib/registry.mjs';
import { appendSample, dropSamples, loadSamples, probeNeedsSite, runName, saveGrades, tally } from '../lib/samples.mjs';
import { wanted } from '../lib/verdict.mjs';
import { summarise, printSummary } from '../lib/summary.mjs';

// Runs the probes against the model: unaided, with the plugin, and with the covered
// passages cut from the plugin where the first two leave that open. It asks only for the
// samples it does not already hold, so a run that stops can be started again.
//
//   node scripts/run.mjs [--only id,id] [--arms bare,guided] [--model id] [--effort level]
//                        [--fresh] [--concurrency n] [--max-calls n] [--dry]

const args = process.argv.slice(2);
const flag = (name) => args.includes(`--${name}`);
const option = (name) => (args.includes(`--${name}`) ? args[args.indexOf(`--${name}`) + 1] : undefined);

const config = loadConfig();
config.model = option('model') || config.model;
config.effort = option('effort') || config.effort;
const concurrency = Number(option('concurrency') || config.concurrency);
const maxCalls = Number(option('max-calls') || config.max_calls);
const arms = option('arms') ? option('arms').split(',') : ARMS;

const registry = loadRegistry();
if (registry.problems.length) {
  console.error(registry.problems.map((problem) => `  ${problem}`).join('\n'));
  console.error('The registry does not line up with the plugin. Run `npm run check`.');
  process.exit(1);
}

const only = option('only')?.split(',');
const probes = registry.probes.filter((probe) => !only || only.includes(probe.id));
if (only && probes.length !== only.length) {
  console.error(`Unknown probe in --only: ${only.filter((id) => !probes.some((probe) => probe.id === id)).join(', ')}`);
  process.exit(1);
}
if (probes.some(probeNeedsSite) && !fs.existsSync(config.site_path)) {
  console.error(`Some probes are graded on the eval site, and there is none at ${config.site_path}. Run \`npm run site\`.`);
  process.exit(1);
}
if (flag('fresh')) {
  dropSamples(config, probes.map((probe) => probe.id));
}

console.log(`${runName(config)} · ${probes.length} probes · arms ${arms.join(', ')} · ${concurrency} at a time`);

let calls = 0;
let failures = 0;
const started = Date.now();

for (let round = 1; round <= 4; round++) {
  const samples = loadSamples(config);
  const jobs = [];
  for (const probe of probes) {
    const have = tally(probe, samples, config);
    const want = wanted(have, probe, config);
    for (const arm of arms) {
      for (let index = have[arm].total; index < want[arm]; index++) {
        jobs.push({ probe, arm, index });
      }
    }
  }
  saveGrades(config);
  if (jobs.length === 0) {
    break;
  }
  if (calls + jobs.length > maxCalls) {
    console.log(`Stopping at --max-calls ${maxCalls}: ${jobs.length} more samples are wanted.`);
    break;
  }
  console.log(`\nRound ${round}: ${jobs.length} samples`);
  if (flag('dry')) {
    for (const job of jobs) {
      console.log(`  ${job.arm.padEnd(8)} ${job.probe.id} #${job.index + 1}`);
    }
    break;
  }

  let done = 0;
  let roundFailures = 0;
  await pool(jobs, concurrency, async ({ probe, arm, index }) => {
    const reply = await ask({ system: systemPrompt(arm, probe, config), prompt: probe.task, model: config.model, effort: config.effort });
    appendSample(config, { probe: probe.id, arm, index, hash: sampleHash(arm, probe, config), at: new Date().toISOString(), ...reply });
    calls++;
    done++;
    if (reply.error) {
      roundFailures++;
      failures++;
    }
    const note = reply.error ? `ERROR ${reply.error.slice(0, 80)}` : `${Math.round((reply.ms || 0) / 1000)}s`;
    console.log(`  [${done}/${jobs.length}] ${arm.padEnd(8)} ${probe.id} #${index + 1} ${note}`);
  });
  if (roundFailures === jobs.length) {
    console.error('Every call in this round failed. Stopping; run again to resume.');
    break;
  }
}

const summary = summarise(registry, loadSamples(config), config);
saveGrades(config);
printSummary(summary);
console.log(`\n${calls} calls, ${failures} failed, ${Math.round((Date.now() - started) / 60000)} min. Write the report with \`npm run report\`.`);
