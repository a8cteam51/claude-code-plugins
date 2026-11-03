import path from 'node:path';
import { readItems, tokens } from './inventory.mjs';
import { runName, tally } from './samples.mjs';
import { verdict } from './verdict.mjs';

// The kinds a model eval can judge. The rest need another instrument: a script for a fact
// about a tool, a scenario run for process and steering, nothing for orientation.
export const JUDGEABLE = ['platform', 'decision'];

// When several probes speak for one passage, the one that argues hardest for keeping it wins.
const KEEP_ORDER = ['needed', 'counterweight', 'partly known', 'not followed', 'worse with plugin', 'known', 'no data'];
const strongest = (verdicts) => KEEP_ORDER.find((name) => verdicts.includes(name)) || 'no data';

const sum = (list, pick) => list.reduce((total, entry) => total + pick(entry), 0);
const lead = (item) => (/\*\*(.+?)\*\*/.exec(item.text)?.[1] || item.key).replace(/^[-*\d. ]+/, '').slice(0, 70);

export function summarise(registry, samples, config) {
  const probes = registry.probes.map((probe) => {
    const arms = tally(probe, samples, config);
    return { id: probe.id, kind: probe.kind, consumer: probe.consumer, items: probe.items, arms, verdict: verdict(arms, config, probe.items.length > 0) };
  });
  const verdictOf = new Map(probes.map((probe) => [probe.id, probe.verdict]));
  for (const item of registry.items) {
    item.verdict = item.probes ? strongest(item.probes.map((id) => verdictOf.get(id))) : undefined;
  }

  const files = registry.files.map((file) => {
    const scope = registry.kinds.files[file];
    const items = scope ? registry.itemsOf(file) : readItems(file);
    const bytes = (list) => sum(list, (item) => item.bytes);
    const entry = { file, inScope: Boolean(scope), tokens: tokens(bytes(items)), items: items.length };
    if (scope) {
      const judgeable = items.filter((item) => JUDGEABLE.includes(item.kind));
      const probed = judgeable.filter((item) => item.probes);
      entry.kinds = Object.fromEntries(Object.keys(registry.kinds.kinds).map((kind) => [kind, tokens(bytes(items.filter((item) => item.kind === kind)))]));
      entry.judgeable = tokens(bytes(judgeable));
      entry.probed = tokens(bytes(probed));
      entry.verdicts = Object.fromEntries(KEEP_ORDER.map((name) => [name, tokens(bytes(probed.filter((item) => item.verdict === name)))]));
    }
    return entry;
  });

  const latest = samples.map((sample) => sample.at).sort().pop();
  return {
    run: { name: runName(config), model: config.model, effort: config.effort, wordpress: config.wordpress, date: latest ? latest.slice(0, 10) : null },
    probes,
    files,
    counts: Object.fromEntries(KEEP_ORDER.map((name) => [name, probes.filter((probe) => probe.verdict === name).length])),
    cost: {
      calls: sum(probes, (probe) => sum(Object.values(probe.arms), (arm) => arm.total)),
      minutes: Math.round(sum(probes, (probe) => sum(Object.values(probe.arms), (arm) => arm.ms)) / 60000),
      usd: sum(probes, (probe) => sum(Object.values(probe.arms), (arm) => arm.cost)),
    },
  };
}

const score = (arm) => (arm.total ? `${arm.pass}/${arm.total}` : '—');
const probeTokens = (probe) => tokens(sum(probe.items, (item) => item.bytes));

export function printSummary(summary) {
  console.log(`\n${summary.run.name}, WordPress ${summary.run.wordpress}`);
  console.log(`${'probe'.padEnd(34)} ${'kind'.padEnd(9)} ${'unaided'.padEnd(8)} ${'plugin'.padEnd(7)} ${'cut'.padEnd(5)} verdict`);
  for (const probe of summary.probes) {
    console.log(
      `${probe.id.padEnd(34)} ${probe.kind.padEnd(9)} ${score(probe.arms.bare).padEnd(8)} ${score(probe.arms.guided).padEnd(7)} ${score(probe.arms.ablated).padEnd(5)} ${probe.verdict}`,
    );
  }
  console.log(`\n${Object.entries(summary.counts).filter(([, count]) => count).map(([name, count]) => `${count} ${name}`).join(' · ')}`);
}

// The report, one per model and effort, so that the next model's report can be read against
// this one. It stays on the machine that ran it: reports/ is ignored by git.
export function markdown(summary, previous, extras = {}) {
  const lines = [];
  const say = (...text) => lines.push(...text);
  const where = (probe) => probe.items.map((item) => `${path.basename(item.file)} § ${item.section}`).filter((value, index, all) => all.indexOf(value) === index).join('; ');
  const row = (probe) => `| \`${probe.id}\` | ${probe.kind} | ${score(probe.arms.bare)} | ${score(probe.arms.guided)} | ${score(probe.arms.ablated)} | **${probe.verdict}** | ${probeTokens(probe)} | ${where(probe)} |`;
  const table = (probes) => ['| Probe | Kind | Unaided | With plugin | Passage cut | Verdict | Tokens | Speaks for |', '|---|---|---|---|---|---|---|---|', ...probes.map(row)];
  const scoped = summary.files.filter((file) => file.inScope);
  const total = (pick) => sum(scoped, pick);

  say(`# ${summary.run.model} at ${summary.run.effort} effort`, '');
  say(`Measured ${summary.run.date || 'never'} on WordPress ${summary.run.wordpress}: ${summary.probes.length} probes, ${summary.cost.calls} graded answers, ${summary.cost.minutes} minutes of model time${summary.cost.usd ? `, $${summary.cost.usd.toFixed(2)} at list price` : ''}.`, '');
  say('Written by `npm run report`. Do not edit: change a probe or the plugin and run again. How to read it: `../README.md`.', '');

  say('## What this run says', '');
  const known = summary.probes.filter((probe) => probe.verdict === 'known');
  const attention = summary.probes.filter((probe) => ['not followed', 'worse with plugin'].includes(probe.verdict));
  say(`- **${summary.counts.needed} needed.** The model does not do these unaided and does with the plugin.`);
  say(`- **${summary.counts.known} known**, ${sum(known, probeTokens)} tokens of plugin text. The model does these unaided every time, and still does with the passage cut. Candidates to delete.`);
  say(`- **${summary.counts['partly known']} partly known** and **${summary.counts.counterweight} counterweight.** Keep.`);
  say(`- **${attention.length} need attention:** the plugin does not get them followed, or makes them worse.`);
  say(`- **${summary.counts['no data']} without enough samples.**`, '');
  say(`These probes speak for ${total((file) => file.probed)} of the ${total((file) => file.judgeable)} tokens a model eval can judge in the files in scope. A passage with no probe is untested, not unneeded.`, '');

  if (known.length) {
    say('## Candidates to delete', '', 'Delete the passage and keep its probe: a later model that fails the probe unaided is the signal to restore the text.', '', ...table(known), '');
  }
  if (attention.length) {
    say('## Needs attention', '', ...table(attention), '');
    for (const probe of attention) {
      const reasons = [...new Set(probe.arms.guided.failures)].slice(0, 3);
      say(`- \`${probe.id}\` with the plugin failed on: ${reasons.map((reason) => `\`${reason.replace(/`/g, "'").slice(0, 140)}\``).join(', ') || 'nothing recorded'}`);
    }
    say('');
  }
  say('## Every probe', '', ...table(summary.probes), '');

  if (previous) {
    const before = new Map(previous.probes.map((probe) => [probe.id, probe.verdict]));
    const changed = summary.probes.filter((probe) => before.has(probe.id) && before.get(probe.id) !== probe.verdict);
    say(`## Against ${previous.run.name}`, '');
    say(changed.length ? ['| Probe | Then | Now |', '|---|---|---|', ...changed.map((probe) => `| \`${probe.id}\` | ${before.get(probe.id)} | ${probe.verdict} |`)].join('\n') : 'No verdict changed.', '');
  }

  if (extras.routing) {
    say('## Does the skill send its reader to the right guide?', '', `Measured ${extras.routing.at.slice(0, 10)} on the skill as installed, by \`npm run routing\`.`, '');
    say('| Case | Guide | Opened it | Answered from it |', '|---|---|---|---|');
    for (const entry of extras.routing.summary) {
      say(`| \`${entry.id}\` | ${entry.opens} | ${entry.opened}/${entry.total} | ${entry.content}/${entry.total} |`);
    }
    say('');
  }
  if (extras.environment) {
    say('## Facts about the tools', '', 'Tried on the eval site by `npm run check -- --site`. One that is not reproduced is a passage to re-examine: the tool may have changed, or the fact may hold only on another kind of site.', '');
    say('| Fact | On the eval site |', '|---|---|');
    for (const entry of extras.environment) {
      say(`| ${entry.claim} | ${entry.holds ? 'holds' : '**not reproduced**'} |`);
    }
    say('');
  }
  say('## Coverage', '', 'Tokens of plugin text, by what can judge them. Only platform facts and house decisions are a question for a model eval.', '');
  say('| File | Tokens | Judgeable here | Probed | Environment | Process | Steering | Reference |', '|---|---|---|---|---|---|---|---|');
  for (const file of scoped) {
    say(`| ${file.file} | ${file.tokens} | ${file.judgeable} | ${file.probed} | ${file.kinds.environment} | ${file.kinds.process} | ${file.kinds.steering} | ${file.kinds.reference} |`);
  }
  say('', 'Not in scope yet:', '');
  for (const file of summary.files.filter((entry) => !entry.inScope)) {
    say(`- ${file.file}, ${file.tokens} tokens`);
  }
  say('');
  return lines.join('\n');
}
