// Two colleges, metric by metric.
//
// The ranking table answers "which is best overall". It cannot answer "why is
// this one above that one", because the Value Score folds three percentile ranks
// into a single number. Putting two rows side by side unfolds it.
//
// `better: null` is the point of the component as much as the comparison is. A
// lower admissions rate and a higher SAT 75th are not better colleges, and
// marking them "no winner" says so in the one place a user is actively looking
// for a winner.

import { useEffect, useMemo, useState } from 'react';
import { TERMS } from '../education/glossary.js';
import { fmtUnit } from '../education/format.js';
import Explain from './Explain.jsx';

const METRICS = [
  { term: 'sticker', key: 'COA', dim: 'sticker', better: 'lower' },
  { term: 'grant', key: 'IGRNT_A', dim: 'grant', better: 'higher' },
  { term: 'net_price', key: 'NET_PRICE_MID', dim: 'net_price', better: 'lower' },
  { term: 'discount', key: 'DISCOUNT', dim: 'discount', better: 'higher' },
  { term: 'aid_share', key: 'AID_SHARE', dim: 'aid_share', better: 'higher' },
  { term: 'admit_rate', key: 'ADMISSIONS_RATE', dim: 'admit_rate', better: null,
    note: 'Harder to get into is not better taught.' },
  { term: 'grad_rate', key: 'GRAD_RATE', dim: 'grad_rate', better: 'higher' },
  { term: 'sat', key: 'SAT_TOTAL_75', dim: 'sat', better: null,
    note: 'A score range, not a quality score.' },
  { term: 'value_score', key: 'VALUE_SCORE', dim: 'value_score', better: 'higher' },
];

// Which side wins, or null when neither does / either value is missing.
function winner(m, x, y) {
  if (!m.better || x == null || y == null || x === y) return null;
  const xWins = m.better === 'higher' ? x > y : x < y;
  return xWins ? 'a' : 'b';
}

export default function Compare({ rows, dist }) {
  const [ids, setIds] = useState([null, null]);

  // Re-seed whenever the shortlist changes, because the previous pair may have
  // been filtered out -- a comparison of two blanks is worse than no comparison.
  useEffect(() => {
    setIds(([a, b]) => {
      const has = (u) => rows.some((r) => r.UNITID === u);
      return [has(a) ? a : rows[0]?.UNITID ?? null,
        has(b) ? b : rows[1]?.UNITID ?? null];
    });
  }, [rows]);

  const [A, B] = useMemo(
    () => ids.map((u) => rows.find((r) => r.UNITID === u) ?? null), [ids, rows]);

  if (rows.length < 2) {
    return (
      <div className="card">
        <h3>Head to head</h3>
        <p className="cap">Needs at least two colleges in the shortlist — widen the filters.</p>
      </div>
    );
  }

  const picker = (side) => (
    <select value={ids[side] ?? ''} aria-label={`College ${side === 0 ? 'A' : 'B'}`}
      onChange={(e) => setIds((p) => p.map((v, i) => (i === side ? +e.target.value : v)))}>
      {rows.map((r) => <option key={r.UNITID} value={r.UNITID}>{r.INSTNM}</option>)}
    </select>
  );

  return (
    <div className="card compare">
      <h3>Head to head</h3>
      <p className="cap">
        Pick two and see what the Value Score folded together. Click any <b>?</b> for what
        the metric means.
      </p>

      <div className="cmp-pick">{picker(0)}<span className="cmp-vs">vs</span>{picker(1)}</div>

      {A && B && (
        <table className="cmp">
          <tbody>
            {METRICS.map((m) => {
              const t = TERMS[m.term];
              const x = A[m.key], y = B[m.key];
              const w = winner(m, x, y);
              return (
                <tr key={m.key}>
                  <td className={'cmp-v' + (w === 'a' ? ' win' : '')}>{fmtUnit(x, t.unit)}</td>
                  <th>
                    <span className="cmp-term">
                      {t.label}
                      <Explain term={m.term} dist={dist} distKey={m.dim} value={x} />
                    </span>
                    <em className="cmp-note">
                      {m.better ? (m.better === 'higher' ? 'higher is better' : 'lower is better')
                        : m.note}
                    </em>
                  </th>
                  <td className={'cmp-v' + (w === 'b' ? ' win' : '')}>{fmtUnit(y, t.unit)}</td>
                </tr>
              );
            })}
            <tr>
              <td className="cmp-v">{A.MERIT_POLICY === 'need_only' ? 'Need-based only' : 'Not checked'}</td>
              <th>
                <span className="cmp-term">Merit aid</span>
                <em className="cmp-note">from a curated list, not from IPEDS</em>
              </th>
              <td className="cmp-v">{B.MERIT_POLICY === 'need_only' ? 'Need-based only' : 'Not checked'}</td>
            </tr>
          </tbody>
        </table>
      )}
    </div>
  );
}
