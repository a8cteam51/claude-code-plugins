// A plain `not-icontains: front-page.html` is the obvious assertion here and it is wrong.
// A correct answer names the anti-pattern in order to reject it — the skill arm opened with
// "**Not `templates/front-page.html`.**" and failed on a perfect answer. What matters is
// whether the answer *recommends* the file.
//
// So: every mention must carry a rejection cue tight against it. The window is deliberately
// small. An earlier version used 200 characters and passed an answer that recommended
// `templates/front-page.html` outright, because unrelated prose ("No PHP, no registration")
// drifted into range. This is a heuristic, not comprehension — if it starts misjudging real
// answers, replace it with an llm-rubric rather than widening the window.

const MENTION = /front-page\.html/gi;
const REJECTION = /\b(never|not|avoid|avoids|don'?t|instead of|rather than|wrong|incorrect|anti-?pattern|forbidden|disallow\w*|reject\w*)\b|[✗✘❌]/i;

const LOOK_BEHIND = 60;
const LOOK_AHEAD = 30;

module.exports = (output) => {
  const text = String(output || '');
  const mentions = [...text.matchAll(MENTION)];

  if (mentions.length === 0) {
    return {
      pass: true,
      score: 1,
      reason: 'Never mentions front-page.html',
    };
  }

  const endorsed = mentions.filter((match) => {
    const start = Math.max(0, match.index - LOOK_BEHIND);
    const window = text.slice(start, match.index + match[0].length + LOOK_AHEAD);
    return !REJECTION.test(window);
  });

  if (endorsed.length > 0) {
    const start = Math.max(0, endorsed[0].index - LOOK_BEHIND);
    const excerpt = text.slice(start, endorsed[0].index + endorsed[0][0].length + LOOK_AHEAD)
      .replace(/\s+/g, ' ')
      .trim();
    return {
      pass: false,
      score: 0,
      reason: `Recommends front-page.html (${endorsed.length} of ${mentions.length} mentions not rejected): "…${excerpt}…"`,
    };
  }

  return {
    pass: true,
    score: 1,
    reason: `Mentions front-page.html ${mentions.length} time(s), rejecting it each time`,
  };
};
