import fs from 'node:fs';
import { workspacesDir } from './workspaces-dir.mjs';

fs.rmSync(workspacesDir, { recursive: true, force: true });
console.log(`Removed generated eval workspaces from ${workspacesDir}`);
