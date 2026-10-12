import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { evalsDir } from '../lib/inventory.mjs';
import { loadConfig } from '../lib/registry.mjs';

// Prepares the Studio site the evals grade on: creates it if it is missing, installs the
// fixture theme with its fixed tokens, and activates it. The site holds nothing else, and
// the graders write nothing to its database.

const config = loadConfig();
const site = config.site_path;
const studio = (args, options = {}) => execFileSync('studio', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...options });

if (!fs.existsSync(path.join(site, 'wp-content'))) {
  console.log(`Creating a Studio site at ${site}`);
  studio(['site', 'create', '--name', path.basename(site), '--path', site], { stdio: 'inherit' });
}

const theme = path.join(site, 'wp-content', 'themes', 'h2bt-eval');
fs.rmSync(theme, { recursive: true, force: true });
fs.cpSync(path.join(evalsDir, 'fixtures', 'theme'), theme, { recursive: true });
studio(['wp', 'theme', 'activate', 'h2bt-eval', `--path=${site}`], { cwd: site });

const version = studio(['wp', 'core', 'version', `--path=${site}`], { cwd: site }).trim().split('\n').pop();
console.log(`H2BT_EVAL_SITE path=${site} wordpress=${version} theme=h2bt-eval`);
if (!version.startsWith(`${config.wordpress}.`) && version !== config.wordpress) {
  console.log(`eval.config.json says WordPress ${config.wordpress}. The probes' examples were checked on that version: run \`npm run check -- --site\`, then update the config.`);
}
