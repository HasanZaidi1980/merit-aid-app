// Trade-offs: a parallel-coordinates plot, built from scatter traces.
//
// This replaces Plotly's `parcoords`, which had three problems that could not be
// fixed from the outside:
//
//   1. It colored lines by a continuous ramp over VALUE_SCORE. The shortlist spans
//      roughly 89-96, so every college landed on nearly the same shade -- a value
//      ramp on what are really nominal categories. Colour carried no identity.
//   2. `parcoords` exposes no line width, so the lines stayed hairline-thin.
//   3. `parcoords` has no legend, so nothing on screen said which line was which.
//
// Drawn as one scatter trace per college instead, each dimension normalised to
// 0..1 on its own axis, which buys line width, per-college colour and a legend.
//
// On colour: only THREE hues clear the all-pairs CVD and normal-vision gates
// (blue/orange/aqua -- worst CVD dE 9.2, worst normal-vision dE 24.0). Every pair
// of lines here sits side by side, so all-pairs is the right gate, and a fourth
// hue fails it: red-vs-orange is dE 7.1 even to full colour vision. Twenty
// distinct hues would be twenty indistinguishable hues. So the top three are
// coloured, the rest are a recessive grey, and identity for *any* college comes
// from the legend -- hover or click a row and that line is isolated.

import { useMemo, useRef, useState } from 'react';
import Plot from '../Plot.jsx';
import { fmt$, pct } from '../education/format.js';

// Validated all-pairs safe, in fixed order. Never cycled, never extended.
const HUES = ['#2a78d6', '#eb6834', '#1baf7a'];
const GREY = '#94a3b8';
const ACCENT = '#1E2761';   // isolating a grey college needs a strong, neutral ink
const AXIS_LINE = '#dbe1ea';

const AXES = [
  { key: 'sticker', col: 'COA', label: 'Sticker', unit: 'money' },
  { key: 'grant', col: 'IGRNT_A', label: 'Avg grant', unit: 'money' },
  { key: 'admit_rate', col: 'ADMISSIONS_RATE', label: 'Admit rate', unit: 'pct' },
  { key: 'grad_rate', col: 'GRAD_RATE', label: 'Grad rate', unit: 'pct' },
  { key: 'net_price', col: 'NET_PRICE_MID', label: 'Net price', unit: 'money' },
];

const fmtBy = (v, unit) => (unit === 'pct' ? pct(v) : fmt$(v));
const compact = (v, unit) => {
  if (v == null) return '—';
  if (unit === 'pct') return pct(v);
  return Math.abs(v) >= 1000
    ? '$' + (v / 1000).toFixed(1).replace(/\.0$/, '') + 'k'
    : fmt$(v);
};

/** Stable UNITID -> hue slot.
 *
 * "Colour follows the entity, never its rank": if the net-price slider knocks out
 * the #2 college, #3 must not repaint from aqua to orange just because it moved up
 * a place. So assignments persist per UNITID, and a slot is only reused once its
 * college leaves the shortlist entirely.
 */
function useStableHues(rows) {
  const assigned = useRef(new Map());
  return useMemo(() => {
    const live = new Set(rows.map((r) => r.UNITID));
    const map = assigned.current;
    for (const id of [...map.keys()]) if (!live.has(id)) map.delete(id);

    const taken = new Set(map.values());
    const free = HUES.map((_, i) => i).filter((i) => !taken.has(i));
    for (const r of rows) {                       // rows arrive rank-ordered
      if (!free.length) break;
      if (!map.has(r.UNITID)) map.set(r.UNITID, free.shift());
    }
    return new Map(map);
  }, [rows]);
}

export default function TradeOffs({ rows, dims }) {
  const [hovered, setHovered] = useState(null);
  const [pinned, setPinned] = useState(null);
  const hues = useStableHues(rows);

  const axes = AXES.filter((a) => dims[a.key]);
  const active = hovered ?? pinned;

  // Per-axis min/max over the shown rows, ignoring blanks. Each axis is scaled on
  // its own range, which is what makes the dimensions comparable at all.
  const scales = useMemo(() => axes.map((a) => {
    const vals = rows.map((r) => r[a.col]).filter((v) => v != null && Number.isFinite(v));
    const lo = Math.min(...vals), hi = Math.max(...vals);
    return { lo, hi, span: hi - lo || 1 };
  }), [rows, axes.map((a) => a.key).join()]);

  const data = useMemo(() => rows.map((r) => {
    const slot = hues.get(r.UNITID);
    const own = slot != null ? HUES[slot] : GREY;
    const isActive = active === r.UNITID;
    const dimmed = active != null && !isActive;

    return {
      type: 'scatter',
      mode: 'lines',
      x: axes.map((_, i) => i),
      // null breaks the line rather than drawing the college at the axis floor.
      // The old chart used `?? 0`, which drew a college with no reported admit
      // rate as if it admitted 3% -- inventing the most dramatic value on the axis.
      y: axes.map((a, i) => {
        const v = r[a.col];
        return v == null || !Number.isFinite(v) ? null : (v - scales[i].lo) / scales[i].span;
      }),
      connectgaps: false,
      line: {
        color: isActive ? (slot != null ? own : ACCENT) : own,
        width: isActive ? 3.5 : slot != null ? 2.5 : 1.5,
        shape: 'linear',
      },
      opacity: dimmed ? 0.1 : slot != null || isActive ? 0.95 : 0.5,
      text: axes.map((a) => `${a.label}: ${fmtBy(r[a.col], a.unit)}`),
      hovertemplate: `<b>${r.INSTNM}</b><br>%{text}<extra></extra>`,
      hoverlabel: { bgcolor: '#fff', bordercolor: isActive ? own : GREY },
      showlegend: false,
    };
  }), [rows, axes, scales, hues, active]);

  const layout = useMemo(() => ({
    margin: { t: 66, r: 14, b: 22, l: 14 },
    // Labels go on top, where parcoords put them, with each axis's real range
    // underneath. t:66 is the fix for the clipped titles -- the old chart left 30px
    // for two lines of text plus the tick gap.
    xaxis: {
      side: 'top', fixedrange: true, showgrid: false, zeroline: false, showline: false,
      range: [-0.4, axes.length - 1 + 0.4],
      tickvals: axes.map((_, i) => i),
      ticktext: axes.map((a, i) =>
        `<b>${a.label}</b><br>${compact(scales[i].lo, a.unit)} – ${compact(scales[i].hi, a.unit)}`),
      tickfont: { size: 11, color: '#475569' },
    },
    yaxis: {
      // Normalised, so the numbers would be meaningless; the axis ranges in the
      // headers carry the scale instead.
      range: [-0.06, 1.06], fixedrange: true,
      showticklabels: false, showgrid: false, zeroline: false, showline: false,
    },
    shapes: axes.map((_, i) => ({
      type: 'line', xref: 'x', yref: 'y', x0: i, x1: i, y0: 0, y1: 1,
      line: { color: AXIS_LINE, width: 1 },
    })),
    hovermode: 'closest',
    showlegend: false,
  }), [axes, scales]);

  if (!rows.length) return <p className="cap">No colleges to plot.</p>;

  return (
    <div className="to-wrap">
      <div className="to-plot">
        <Plot data={data} layout={layout} style={{ height: 400 }} />
      </div>

      {/* The legend is the identity mechanism, not decoration: with 3 hues and 20
          lines, hovering a row is how you find any college that is not top-three. */}
      <ol className="to-legend" onMouseLeave={() => setHovered(null)}>
        {rows.map((r) => {
          const slot = hues.get(r.UNITID);
          return (
            <li key={r.UNITID}>
              <button type="button"
                className={'to-item' + (pinned === r.UNITID ? ' pinned' : '')
                  + (active === r.UNITID ? ' active' : '')}
                aria-pressed={pinned === r.UNITID}
                onMouseEnter={() => setHovered(r.UNITID)}
                onFocus={() => setHovered(r.UNITID)}
                onBlur={() => setHovered(null)}
                onClick={() => setPinned((p) => (p === r.UNITID ? null : r.UNITID))}>
                <i className="to-sw" style={{ background: slot != null ? HUES[slot] : GREY }} />
                <span className="to-rank">{r.RANK}</span>
                <span className="to-name">{r.INSTNM}</span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
