// Client-side Value Score, scored against the real distribution.
//
// The backend ships 101 percentile breakpoints per component once; this re-derives
// a percentile rank from them locally so the sandbox can respond to a slider drag
// without a request. Same arithmetic the backend does with pandas `rank(pct=True)`,
// to within half a percentile.

// Position of `value` in an ascending p0..p100 breakpoint array, as 0..1.
// Linear interpolation inside the bracketing pair, so dragging a slider moves the
// score smoothly instead of stepping between whole percentiles.
export function percentileRank(breakpoints, value, higherIsBetter = true) {
  if (value == null || !Number.isFinite(value)) return null;
  if (!breakpoints?.length) return null;

  const last = breakpoints.length - 1;
  let p;
  if (value <= breakpoints[0]) p = 0;
  else if (value >= breakpoints[last]) p = 1;
  else {
    // Binary search for the last breakpoint at or below `value`.
    let lo = 0, hi = last;
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1;
      if (breakpoints[mid] <= value) lo = mid; else hi = mid;
    }
    const span = breakpoints[hi] - breakpoints[lo];
    p = (lo + (span > 0 ? (value - breakpoints[lo]) / span : 0)) / last;
  }
  return higherIsBetter ? p : 1 - p;
}

// Every derived figure the sandbox shows, from the raw slider inputs.
// Mirrors scoring.add_metrics() — if that changes, this has to change with it.
// `extras` is housing + books: IPEDS has no single column for it, so the sandbox
// splits the sticker two ways rather than three.
export function derive(dist, { tuition, extras, grant, netPrice, gradRate }) {
  const coa = tuition + extras;
  const aidShare = coa > 0 ? grant / coa : null;
  const mgi = tuition > 0 ? grant / tuition : null;

  const c = dist?.components;
  const ranks = c && {
    affordability: percentileRank(c.net_price.breakpoints, netPrice, c.net_price.higher_is_better),
    quality: percentileRank(c.grad_rate.breakpoints, gradRate, c.grad_rate.higher_is_better),
    generosity: percentileRank(c.aid_share.breakpoints, aidShare, c.aid_share.higher_is_better),
  };

  // NaN propagates on purpose, exactly as the backend does: a college missing any
  // component is not scoreable, and showing a partial score would be a lie.
  const parts = ranks && [ranks.affordability, ranks.quality, ranks.generosity];
  const scoreable = parts && parts.every((p) => p != null);
  const valueScore = scoreable ? (parts.reduce((a, b) => a + b, 0) / 3) * 100 : null;

  // Where that score would land among the colleges that actually have one.
  let rank = null;
  if (valueScore != null && dist?.value_score_breakpoints && dist?.scored_n) {
    const better = percentileRank(dist.value_score_breakpoints, valueScore, true);
    rank = Math.min(dist.scored_n, Math.max(1, Math.round((1 - better) * dist.scored_n) + 1));
  }

  return {
    coa, aidShare, mgi, netPrice, gradRate,
    discount: coa - netPrice,
    netPriceRatio: coa > 0 ? netPrice / coa : null,
    ranks, valueScore, rank,
  };
}
