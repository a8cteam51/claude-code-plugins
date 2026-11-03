import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { ARMS, sampleHash } from './context.mjs';
import { grade, needsSite } from './graders.mjs';
import { evalsDir } from './inventory.mjs';

// One directory per model and effort: that pair is the thing being measured.
export const runName = (config) => `${config.model}@${config.effort}`;
export const resultsDir = (config) => path.join(evalsDir, 'results', runName(config));

const samplesFile = (config) => path.join(resultsDir(config), 'samples.jsonl');
const gradesFile = (config) => path.join(resultsDir(config), 'grades.json');

// Answers are kept as they came back, one JSON object per line, and graded when read. A
// grader that turns out wrong is fixed and the answers are graded again; no model is called.
export function loadSamples(config) {
  if (!fs.existsSync(samplesFile(config))) {
    return [];
  }
  return fs
    .readFileSync(samplesFile(config), 'utf8')
    .split('\n')
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

export function appendSample(config, sample) {
  fs.mkdirSync(resultsDir(config), { recursive: true });
  fs.appendFileSync(samplesFile(config), `${JSON.stringify(sample)}\n`);
}

export function dropSamples(config, probeIds) {
  const kept = loadSamples(config).filter((sample) => !probeIds.includes(sample.probe));
  fs.mkdirSync(resultsDir(config), { recursive: true });
  fs.writeFileSync(samplesFile(config), kept.map((sample) => `${JSON.stringify(sample)}\n`).join(''));
}

// Grades are remembered on disk because a check against the eval site takes seconds. The
// graders' own source is part of the key, so a grader that is fixed grades everything again.
const gradersVersion = crypto.createHash('sha1').update(fs.readFileSync(path.join(evalsDir, 'lib', 'graders.mjs'))).digest('hex');
let gradeCache;
function gradeOnce(config, probe, answer) {
  if (!gradeCache) {
    gradeCache = fs.existsSync(gradesFile(config)) ? JSON.parse(fs.readFileSync(gradesFile(config), 'utf8')) : {};
  }
  const key = crypto.createHash('sha1').update(`${gradersVersion}\n${JSON.stringify(probe.grade)}\n${answer}`).digest('hex');
  if (!gradeCache[key]) {
    const result = grade(answer, probe.grade, { sitePath: config.site_path });
    if (result.skipped.length) {
      return result;
    }
    gradeCache[key] = { pass: result.pass, failed: result.failed };
  }
  return gradeCache[key];
}

export function saveGrades(config) {
  if (gradeCache) {
    fs.mkdirSync(resultsDir(config), { recursive: true });
    fs.writeFileSync(gradesFile(config), JSON.stringify(gradeCache));
  }
}

// The samples that still describe this probe, per arm, graded. A sample goes stale when the
// model, the effort, the task or the covered passages change.
export function tally(probe, samples, config) {
  const arms = {};
  for (const arm of ARMS) {
    const hash = sampleHash(arm, probe, config);
    const valid = samples.filter((sample) => sample.probe === probe.id && sample.arm === arm && sample.hash === hash && !sample.error);
    const graded = valid.map((sample) => ({ ...sample, ...gradeOnce(config, probe, sample.answer) }));
    arms[arm] = {
      total: graded.length,
      pass: graded.filter((sample) => sample.pass).length,
      ms: graded.reduce((sum, sample) => sum + (sample.ms || 0), 0),
      cost: graded.reduce((sum, sample) => sum + (sample.cost || 0), 0),
      output_tokens: graded.reduce((sum, sample) => sum + (sample.output_tokens || 0), 0),
      failures: graded.filter((sample) => !sample.pass).flatMap((sample) => sample.failed),
    };
  }
  return arms;
}

export const probeNeedsSite = (probe) => needsSite(probe.grade);
