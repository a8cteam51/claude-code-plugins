import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { query } from '@anthropic-ai/claude-agent-sdk';

// An empty directory for every call to start in, so nothing on disk can inform an answer.
const emptyDir = fs.mkdtempSync(path.join(os.tmpdir(), 'h2bt-eval-cwd-'));
process.on('exit', () => fs.rmSync(emptyDir, { recursive: true, force: true }));

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// One answer from the model: a system prompt, one message, no tools, no settings from the
// machine it runs on. Goes through the Agent SDK so it uses the same sign-in as Claude Code.
async function once({ system, prompt, model, effort }) {
  let result;
  for await (const message of query({
    prompt,
    options: {
      model,
      effort,
      systemPrompt: system,
      tools: [],
      allowedTools: [],
      settingSources: [],
      maxTurns: 1,
      cwd: emptyDir,
      persistSession: false,
      permissionMode: 'dontAsk',
    },
  })) {
    if (message.type === 'result') {
      result = message;
    }
  }
  if (!result) {
    throw new Error('no result message');
  }
  if (result.subtype !== 'success' || result.is_error) {
    throw new Error(String(result.result || result.subtype).slice(0, 300));
  }
  return {
    answer: result.result,
    ms: result.duration_ms,
    cost: result.total_cost_usd ?? null,
    output_tokens: result.usage?.output_tokens ?? null,
  };
}

// Rate limits and dropped connections are expected in a run of hundreds of calls.
export async function ask(request, { retries = 3 } = {}) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await once(request);
    } catch (error) {
      if (attempt >= retries) {
        return { error: String(error.message || error).slice(0, 300) };
      }
      await wait(15000 * 2 ** attempt);
    }
  }
}

export async function pool(jobs, concurrency, worker) {
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(concurrency, jobs.length) }, async () => {
      while (next < jobs.length) {
        const job = jobs[next++];
        await worker(job);
      }
    }),
  );
}
