import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import YAML from 'yaml';
import { query } from '@anthropic-ai/claude-agent-sdk';
import { pool } from '../lib/agent.mjs';
import { grade } from '../lib/graders.mjs';
import { evalsDir, pluginDir } from '../lib/inventory.mjs';
import { loadConfig } from '../lib/registry.mjs';
import { resultsDir, runName } from '../lib/samples.mjs';

// Does SKILL.md's pointer to a reference file work? Installs the skill in an empty
// workspace, asks a question whose answer is written only in one reference, and records
// whether the model opened that file. Read-only: the model gets Read, Grep, Glob and Skill.
//
//   node scripts/routing.mjs [--samples n]

const args = process.argv.slice(2);
const samples = Number(args.includes('--samples') ? args[args.indexOf('--samples') + 1] : 3);
const config = loadConfig();
const cases = YAML.parse(fs.readFileSync(path.join(evalsDir, 'registry', 'routing.yaml'), 'utf8'));
const skill = 'html-to-block-theme';

// The workspace lives outside the repository. Inside it, a model without the skill once
// walked up out of its directory and answered from the guides themselves.
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'h2bt-eval-routing-'));
process.on('exit', () => fs.rmSync(workspace, { recursive: true, force: true }));
const installed = path.join(workspace, '.claude', 'skills', skill);
fs.cpSync(path.join(pluginDir, 'skills', skill), installed, { recursive: true });
fs.cpSync(path.join(pluginDir, 'scripts'), path.join(installed, 'scripts'), { recursive: true });

// ${CLAUDE_PLUGIN_ROOT} resolves only for an installed plugin; a skill in .claude/skills
// gets ${CLAUDE_SKILL_DIR}. Without the rewrite the model cannot open a single reference.
for (const entry of fs.readdirSync(installed, { withFileTypes: true, recursive: true })) {
  if (entry.isFile() && entry.name.endsWith('.md')) {
    const file = path.join(entry.parentPath || entry.path, entry.name);
    const text = fs
      .readFileSync(file, 'utf8')
      .replaceAll(`\${CLAUDE_PLUGIN_ROOT}/skills/${skill}/`, '${CLAUDE_SKILL_DIR}/')
      .replaceAll('${CLAUDE_PLUGIN_ROOT}/scripts/', '${CLAUDE_SKILL_DIR}/scripts/');
    if (text.includes('${CLAUDE_PLUGIN_ROOT}')) {
      console.error(`${path.relative(installed, file)} still names \${CLAUDE_PLUGIN_ROOT}: add a rewrite, or the model cannot open what it points at.`);
      process.exit(1);
    }
    fs.writeFileSync(file, text);
  }
}
execFileSync('git', ['init', '--quiet'], { cwd: workspace });

const preamble = [
  'You are advising on converting a directory of static HTML/CSS designs into a WordPress block theme on a local Studio site.',
  'If a relevant skill is available, follow it and only open reference files it explicitly directs you to. Do not read files outside this working directory, do not run commands, and do not modify files.',
  'Answer briefly. Name exact file paths, PHP functions, block names, and settings.',
].join(' ');

async function one(routingCase) {
  const opened = new Set();
  let result;
  try {
    for await (const message of query({
      prompt: `${preamble}\n\n${routingCase.task}`,
      options: {
        model: config.model,
        effort: config.effort,
        cwd: workspace,
        settingSources: ['project'],
        skills: [skill],
        allowedTools: ['Read', 'Grep', 'Glob', 'Skill'],
        permissionMode: 'dontAsk',
        maxTurns: 12,
        persistSession: false,
      },
    })) {
      if (message.type === 'assistant') {
        for (const block of message.message?.content || []) {
          if (block.type === 'tool_use' && block.name === 'Read' && block.input?.file_path) {
            opened.add(path.basename(block.input.file_path));
          }
        }
      }
      if (message.type === 'result') {
        result = message;
      }
    }
  } catch (error) {
    return { error: String(error.message || error).slice(0, 200) };
  }
  if (!result || result.subtype !== 'success') {
    return { error: String(result?.subtype || 'no result') };
  }
  return { opened: opened.has(routingCase.opens), read: [...opened], content: grade(result.result, routingCase.grade).pass, answer: result.result };
}

const jobs = cases.flatMap((routingCase) => Array.from({ length: samples }, () => routingCase));
const rows = [];
await pool(jobs, config.concurrency, async (routingCase) => {
  rows.push({ id: routingCase.id, opens: routingCase.opens, ...(await one(routingCase)) });
});

const summary = cases.map((routingCase) => {
  const mine = rows.filter((row) => row.id === routingCase.id && !row.error);
  return {
    id: routingCase.id,
    opens: routingCase.opens,
    total: mine.length,
    opened: mine.filter((row) => row.opened).length,
    content: mine.filter((row) => row.content).length,
    errors: rows.filter((row) => row.id === routingCase.id && row.error).length,
  };
});

fs.mkdirSync(resultsDir(config), { recursive: true });
fs.writeFileSync(path.join(resultsDir(config), 'routing.json'), `${JSON.stringify({ run: runName(config), at: new Date().toISOString(), summary, rows }, null, 2)}\n`);

console.log(`${runName(config)} · does the skill send its reader to the right guide?`);
for (const entry of summary) {
  const verdict = entry.opened === 0 ? 'POINTER FAILED' : entry.opened < entry.total ? 'pointer works some of the time' : entry.content === entry.total ? 'pointer works and the guide answers' : 'pointer works; the guide did not yield the answer';
  console.log(`  ${entry.id}: opened ${entry.opens} ${entry.opened}/${entry.total} · answer ${entry.content}/${entry.total} · ${verdict}${entry.errors ? ` · ${entry.errors} errors` : ''}`);
}
