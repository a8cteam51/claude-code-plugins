import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { workspacesDir } from './workspaces-dir.mjs';

const evalsDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const pluginDir = path.resolve(evalsDir, '..');
const skillName = 'html-to-block-theme';
const sourceSkillDir = path.join(pluginDir, 'skills', skillName);

if (!fs.existsSync(path.join(sourceSkillDir, 'SKILL.md'))) {
  console.error(`No SKILL.md at ${sourceSkillDir}.`);
  process.exit(1);
}

// SKILL.md and its references address sibling files through ${CLAUDE_PLUGIN_ROOT}, which
// only resolves when Claude Code loads the skill as an installed plugin. A skill copied
// into .claude/skills/ gets ${CLAUDE_SKILL_DIR} instead, so rewrite on the way in.
// Without this the agent cannot open a single reference file, and the eval would measure
// a broken copy rather than the skill.
const rewrites = [
  [`\${CLAUDE_PLUGIN_ROOT}/skills/${skillName}/`, '${CLAUDE_SKILL_DIR}/'],
  ['${CLAUDE_PLUGIN_ROOT}/scripts/', '${CLAUDE_SKILL_DIR}/scripts/'],
];

function rewriteMarkdownIn(directory) {
  const dangling = [];

  for (const entry of fs.readdirSync(directory, { withFileTypes: true, recursive: true })) {
    if (!entry.isFile() || !entry.name.endsWith('.md')) {
      continue;
    }
    const file = path.join(entry.parentPath || entry.path, entry.name);
    let text = fs.readFileSync(file, 'utf8');
    for (const [from, to] of rewrites) {
      text = text.replaceAll(from, to);
    }
    if (text.includes('${CLAUDE_PLUGIN_ROOT}')) {
      dangling.push(path.relative(directory, file));
    }
    fs.writeFileSync(file, text);
  }

  return dangling;
}

fs.rmSync(workspacesDir, { recursive: true, force: true });

// Arm A: no skill at all. The provider omits setting_sources and skills, so nothing is
// discovered here. This is the baseline the skill has to beat.
const skillOff = path.join(workspacesDir, 'skill-off');
fs.mkdirSync(skillOff, { recursive: true });
execFileSync('git', ['init', '--quiet'], { cwd: skillOff });

// Arm B: the skill under test, copied verbatim except for the path rewrite above.
const skillOn = path.join(workspacesDir, 'skill-on');
const installedSkill = path.join(skillOn, '.claude', 'skills', skillName);
fs.cpSync(sourceSkillDir, installedSkill, { recursive: true });

const pluginScripts = path.join(pluginDir, 'scripts');
if (fs.existsSync(pluginScripts)) {
  fs.cpSync(pluginScripts, path.join(installedSkill, 'scripts'), { recursive: true });
}

const dangling = rewriteMarkdownIn(installedSkill);
if (dangling.length > 0) {
  console.error('These files still reference ${CLAUDE_PLUGIN_ROOT} after rewriting:');
  for (const file of dangling) {
    console.error(`  ${file}`);
  }
  console.error('Add a rewrite rule, or the agent cannot open them and the eval is invalid.');
  process.exit(1);
}

execFileSync('git', ['init', '--quiet'], { cwd: skillOn });

console.log(`Reset skill-off and skill-on workspaces in ${workspacesDir}`);
console.log(`Skill source: ${sourceSkillDir}`);
