// Progressive-disclosure check: did the agent actually open the reference file that
// SKILL.md points at, or did it answer from what it already knew?
//
// Without this, a disclosure case is indistinguishable from a recall case — a correct
// answer proves the model knows the fact, not that the pointer works. Pairing this with
// the content assertions splits the result into four meaningful outcomes:
//
//   opened + correct    → the pointer works and the guide is clear
//   opened + wrong      → the pointer works; the guide's wording is the problem
//   not opened + correct→ base knowledge; the case proves nothing about disclosure
//   not opened + wrong  → the pointer failed — the thing this case exists to catch
//
// The expected filename comes from the test's `reference` var.

const READ_TOOLS = /^(Read|Grep|Glob|LS)$/;

module.exports = (output, context) => {
  const expected = context?.vars?.reference;
  if (!expected) {
    return {
      pass: false,
      score: 0,
      reason: 'Test is missing a `reference` var naming the file that should be opened',
    };
  }

  const calls = context?.metadata?.toolCalls ?? [];
  const fileReads = calls.filter((call) => READ_TOOLS.test(call?.name ?? ''));

  // Match against the whole serialized input rather than a specific field — Read uses
  // file_path, Grep/Glob use path/pattern, and the shape varies by tool.
  const hit = fileReads.some((call) => JSON.stringify(call.input ?? {}).includes(expected));

  if (hit) {
    return {
      pass: true,
      score: 1,
      reason: `Opened ${expected}`,
    };
  }

  const opened = fileReads
    .map((call) => {
      const input = call.input ?? {};
      return input.file_path || input.path || input.pattern || JSON.stringify(input);
    })
    .map((path) => String(path).split('/').pop());

  const detail = opened.length > 0
    ? `read ${[...new Set(opened)].join(', ')}`
    : 'made no file reads at all';

  return {
    pass: false,
    score: 0,
    reason: `Never opened ${expected} — ${detail}`,
  };
};
