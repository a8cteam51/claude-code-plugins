// What the three arms say about one probe. Each arm is { pass, total }.
//
//   needed         the model does not do it unaided, and does with the plugin. Keep.
//   known          the model does it unaided every time, and still does with the passage cut
//                  from the plugin. A candidate to delete.
//   counterweight  unaided it passes, but inside the plugin without the passage it fails:
//                  something else in the plugin pulls the other way. Keep.
//   partly known   unaided it passes some of the time. Keep; perhaps shorten.
//   not followed   it fails even with the plugin. The passage, or the probe, needs work.
//   worse with plugin  unaided it passes every time, and with the plugin it does not.
//   no data        too few samples to say.
//
// "Every time" is deliberate. Keeping a passage the model did not need costs tokens;
// deleting one it did need costs a build.
export const VERDICTS = ['needed', 'partly known', 'counterweight', 'not followed', 'worse with plugin', 'known', 'no data'];

export function verdict(arms, config, coversText = true) {
  const { bare, guided, ablated } = arms;
  const rate = (arm) => (arm && arm.total ? arm.pass / arm.total : null);
  const enough = (arm, count) => Boolean(arm && arm.total >= count);
  const { first, full } = config.samples;
  const { followed, unaided_low: low } = config.thresholds;

  if (!enough(bare, first) || !enough(guided, first)) {
    return 'no data';
  }
  if (rate(guided) < followed && rate(bare) < 1) {
    return 'not followed';
  }
  if (rate(bare) === 1) {
    if (!enough(bare, full) || !enough(guided, full)) {
      return 'no data';
    }
    if (rate(guided) < followed) {
      return 'worse with plugin';
    }
    if (!coversText) {
      return 'known';
    }
    if (!enough(ablated, full)) {
      return 'no data';
    }
    return rate(ablated) === 1 ? 'known' : 'counterweight';
  }
  return rate(bare) <= low ? 'needed' : 'partly known';
}

// How many more samples each arm needs before the verdict can settle. The cheap case, a
// clear "needed", stops at the first few; anything near deletion gets the full count.
export function wanted(arms, probe, config) {
  const { first, full } = config.samples;
  const have = (arm) => arms[arm]?.total || 0;
  const pass = (arm) => arms[arm]?.pass || 0;

  if (have('bare') < first || have('guided') < first) {
    return { bare: first, guided: first, ablated: 0 };
  }
  if (pass('bare') === 0 && pass('guided') === have('guided')) {
    return { bare: have('bare'), guided: have('guided'), ablated: 0 };
  }
  const allBare = have('bare') >= full && pass('bare') === have('bare');
  return { bare: full, guided: full, ablated: allBare && probe.items.length ? full : 0 };
}
