import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { evalsDir, pluginDir, stripFrontmatter, withoutItems } from './inventory.mjs';

const REFERENCES = 'skills/html-to-block-theme/references';

// Whose context a rule lives in during a real run, and what that reader has loaded when it
// meets the rule. A probe can add guides with `guides:`.
export const consumers = {
  builder: { role: 'agents/section-builder.md', guides: ['mapping-guide.md', 'standards.md'] },
  orchestrator: { role: 'skills/html-to-block-theme/SKILL.md', guides: ['mapping-guide.md'] },
};

export const ARMS = ['bare', 'guided', 'ablated'];

function base(config) {
  const themeJson = fs.readFileSync(path.join(evalsDir, 'fixtures', 'theme', 'theme.json'), 'utf8').trim();
  return [
    'You are working on a WordPress block theme that reproduces a static HTML/CSS design.',
    `The site runs WordPress ${config.wordpress}. The active theme's theme.json is:`,
    '```json\n' + themeJson + '\n```',
    'There are no tools in this session. Do the one piece of work the message asks for, from what you know and what you have been given, and reply with exactly the output it asks for.',
  ].join('\n\n');
}

// The system prompt for one arm of one probe.
//   bare     the model and the task, nothing of the plugin
//   guided   what the rule's reader has loaded in a real run
//   ablated  the same, with the passages the probe covers cut out
export function systemPrompt(arm, probe, config) {
  if (arm === 'bare') {
    return base(config);
  }
  const consumer = consumers[probe.consumer];
  if (!consumer) {
    throw new Error(`${probe.id}: unknown consumer "${probe.consumer}"`);
  }
  const cut = arm === 'ablated' ? probe.items : [];
  const read = (file) => stripFrontmatter(cut.length ? withoutItems(file, cut) : fs.readFileSync(path.join(pluginDir, file), 'utf8'));
  const guides = [...new Set([...consumer.guides, ...(probe.guides || [])])];

  return [
    base(config),
    '# Your instructions',
    read(consumer.role),
    '# Reference guides',
    'You have read these guides in full, as your instructions tell you to.',
    ...guides.map((guide) => `<guide file="${guide}">\n${read(`${REFERENCES}/${guide}`)}\n</guide>`),
  ].join('\n\n');
}

// What a stored sample was produced from. A sample is reused only while this is unchanged:
// the model, the effort, the task, and for the plugin arms the text of the covered passages.
export function sampleHash(arm, probe, config) {
  const parts = [config.model, config.effort, config.wordpress, arm, probe.task];
  if (arm !== 'bare') {
    parts.push(probe.consumer, ...(probe.guides || []), ...probe.items.map((item) => item.id));
  }
  return crypto.createHash('sha1').update(parts.join('\n')).digest('hex').slice(0, 12);
}
