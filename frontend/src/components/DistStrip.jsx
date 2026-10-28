// Where one value sits in the distribution of all 1,907 colleges.
//
// Inline SVG rather than a Plot: these appear inside popovers and comparison rows,
// several at a time, and spinning up a Plotly instance per strip would cost more
// than the whole chart grid. It also has to stay legible at 240x44.

import { fmtUnit } from '../education/format.js';

const W = 240, H = 40;

export default function DistStrip({ summary, value, unit, label = 'this college' }) {
  if (!summary?.bin_counts?.length) return null;

  const { bin_edges: edges, bin_counts: counts, min, max, median } = summary;
  const span = max - min || 1;
  const x = (v) => ((v - min) / span) * W;
  const peak = Math.max(...counts) || 1;

  // A long right tail (sticker price, grant) squashes every other bar to nothing
  // on a linear height scale. sqrt keeps the small bins visible without implying
  // the tail is bigger than it is.
  const h = (c) => (Math.sqrt(c) / Math.sqrt(peak)) * (H - 6);

  const inRange = value != null && Number.isFinite(value) && value >= min && value <= max;
  const vx = inRange ? x(value) : null;

  return (
    <div className="strip">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img"
        aria-label={`Distribution across all colleges; ${label} at ${fmtUnit(value, unit)}`}>
        {counts.map((c, i) => {
          const x0 = x(edges[i]), x1 = x(edges[i + 1]);
          const bh = h(c);
          return <rect key={i} x={x0} y={H - bh} width={Math.max(x1 - x0 - 0.6, 0.6)}
            height={bh} className="strip-bar" />;
        })}
        {/* Median first, so the value marker draws over it when they coincide. */}
        <line x1={x(median)} x2={x(median)} y1={0} y2={H} className="strip-median" />
        {vx != null && <line x1={vx} x2={vx} y1={0} y2={H} className="strip-mark" />}
        {vx != null && <circle cx={vx} cy={4} r={3.2} className="strip-dot" />}
      </svg>
      <div className="strip-cap">
        <span><i className="sw-median" /> median {fmtUnit(median, unit)}</span>
        {value != null && (
          <span><i className="sw-mark" /> {label} {fmtUnit(value, unit)}</span>
        )}
      </div>
    </div>
  );
}
