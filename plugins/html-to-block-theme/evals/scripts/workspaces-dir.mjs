import os from 'node:os';
import path from 'node:path';

// Workspaces live outside the plugin repo on purpose. When they sat inside evals/, the
// skill-off arm walked up out of its working directory, found
// plugins/html-to-block-theme/skills/.../references/mapping-guide.md, and answered from the
// very file under test — citing line numbers. The baseline has to have nothing to find.
export const workspacesDir = path.join(os.tmpdir(), 'h2bt-eval-workspaces');
export const workspacesEnvVar = 'H2BT_WORKSPACES';
