// "Build a College" -- the interactive half of the education section.
//
// Definitions tell you what a metric is. They do not tell you how the metrics
// push against each other, which is the part that actually misleads families:
// raise the sticker and Aid Share falls even though the grant never moved; a
// huge discount off a huge sticker still loses to a cheap public.
//
// So this does not explain the formulas, it runs them. Every drag re-scores a
// hypothetical college against the real 1,907 and shows where it would land in
// the ranking. Scoring happens in the browser off the shipped percentile
// breakpoints, so there is no request per pixel of slider travel.

import { useMemo, useState } from 'react';
import { TERMS } from '../education/glossary.js';
import { derive } from '../education/valueScore.js';
import { fmt$, fmtUnit, num, ordinal, pct } from '../education/format.js';
import DistStrip from './DistStrip.jsx';
import Explain from './Explain.jsx';

// `feeds` names the Value Score component this input drives, or null when the
// app displays the number but never scores on it. Surfacing that is itself a
// lesson: two of the headline metrics do not affect the ranking at all.
const SLIDERS = [
  { key: 'tuition', label: 'Tuition', dim: 'tuition', term: 'sticker', step: 500, feeds: 'sticker' },
  { key: 'extras', label: 'Housing + books', dim: 'extras', term: 'sticker', step: 500, feeds: 'sticker' },
  { key: 'grant', label: 'Avg institutional grant', dim: 'grant', term: 'grant', step: 500, feeds: 'generosity' },
  { key: 'netPrice', label: 'Net price', dim: 'net_price', term: 'net_price', step: 500, feeds: 'affordability' },
  { key: 'gradRate', label: 'Graduation rate', dim: 'grad_rate', term: 'grad_rate', step: 0.01, feeds: 'quality' },
  { key: 'admitRate', label: 'Admissions rate', dim: 'admit_rate', term: 'admit_rate', step: 0.01, feeds: null },
  { key: 'sat', label: 'SAT 75th', dim: 'sat', term: 'sat', step: 10, feeds: null },
];

// Presets are read off the live distribution rather than hardcoded, so they stay
// true when the dataset changes and so "typical" means the actual median college.
const PRESETS = [
  { id: 'typical', label: 'Typical college', hint: 'every value at the median' },
  { id: 'generous', label: 'Rich private', hint: 'high sticker, huge grant, low net price' },
  { id: 'bargain', label: 'Cheap public', hint: 'low sticker, small grant' },
];

function presetValues(dist, id) {
  const at = (k, q) => dist.dimensions?.[k]?.[q] ?? 0;
  if (id === 'generous') {
    return {
      tuition: at('tuition', 'p75'), extras: at('extras', 'p75'),
      grant: at('grant', 'p75'), netPrice: at('net_price', 'p25'),
      gradRate: at('grad_rate', 'p75'), admitRate: at('admit_rate', 'p25'),
      sat: at('sat', 'p75'),
    };
  }
  if (id === 'bargain') {
    return {
      tuition: at('tuition', 'p25'), extras: at('extras', 'p25'),
      grant: at('grant', 'p25'), netPrice: at('net_price', 'p25'),
      gradRate: at('grad_rate', 'median'), admitRate: at('admit_rate', 'p75'),
      sat: at('sat', 'median'),
    };
  }
  return {
    tuition: at('tuition', 'median'), extras: at('extras', 'median'),
    grant: at('grant', 'median'), netPrice: at('net_price', 'median'),
    gradRate: at('grad_rate', 'median'), admitRate: at('admit_rate', 'median'),
    sat: at('sat', 'median'),
  };
}

// Round slider bounds outward to a whole step, so the handle can reach the ends.
const bound = (summary, step, which) => {
  const raw = summary?.[which] ?? (which === 'min' ? 0 : 1);
  return which === 'min' ? Math.floor(raw / step) * step : Math.ceil(raw / step) * step;
};

export default function Sandbox({ dist }) {
  const [vals, setVals] = useState(() => presetValues(dist, 'typical'));
  const [preset, setPreset] = useState('typical');

  const d = useMemo(() => derive(dist, vals), [dist, vals]);

  const set = (key, v) => { setVals((p) => ({ ...p, [key]: v })); setPreset(null); };
  const apply = (id) => { setVals(presetValues(dist, id)); setPreset(id); };

  // The three percentile ranks, drawn as bars because the Value Score is their
  // mean -- seeing which bar is short explains the score better than the number.
  const bars = [
    ['Affordability', d.ranks?.affordability, 'cheaper net price'],
    ['Graduation', d.ranks?.quality, 'more finish in 4 years'],
    ['Generosity', d.ranks?.generosity, 'bigger grant vs sticker'],
  ];

  return (
    <div className="card sandbox">
      <h3>Build a College</h3>
      <p className="cap">
        Drag anything. The college is re-scored against all {dist.n.toLocaleString()} real
        colleges as you go, so you can see which numbers move the ranking and which
        never do.
      </p>

      <div className="presets">
        {PRESETS.map((p) => (
          <button key={p.id} type="button" title={p.hint}
            className={'chip' + (preset === p.id ? ' on' : '')}
            onClick={() => apply(p.id)}>{p.label}</button>
        ))}
      </div>

      <div className="sb-grid">
        <div className="sb-controls">
          {SLIDERS.map((s) => {
            const summary = dist.dimensions?.[s.dim];
            const isRate = s.step < 1;
            const unit = isRate ? 'pct' : TERMS[s.term].unit;
            return (
              <div className="sb-row" key={s.key}>
                <label>
                  <span className="sb-label">
                    {s.label}
                    <Explain term={s.term} dist={dist} distKey={s.dim} value={vals[s.key]} />
                    {!s.feeds && (
                      <em className="badge-off"
                        title="Shown in the table, but not part of the Value Score">not scored</em>
                    )}
                  </span>
                  <b className="sb-val">{fmtUnit(vals[s.key], unit)}</b>
                </label>
                <input type="range" step={s.step}
                  min={bound(summary, s.step, 'min')} max={bound(summary, s.step, 'max')}
                  value={vals[s.key]} onChange={(e) => set(s.key, +e.target.value)} />
              </div>
            );
          })}
        </div>

        <div className="sb-out">
          <div className="sb-score">
            <div className="sb-score-n">{d.valueScore == null ? '—' : num(d.valueScore, 1)}</div>
            <div className="sb-score-l">
              Value Score
              <Explain term="value_score" dist={dist} distKey="value_score" value={d.valueScore} />
            </div>
            <div className="sb-rank">
              would rank <b>{d.rank == null ? '—' : ordinal(d.rank)}</b> of {dist.scored_n.toLocaleString()}
            </div>
          </div>

          {bars.map(([label, v, why]) => (
            <div className="sb-bar" key={label}>
              <div className="sb-bar-top"><span>{label}</span><b>{v == null ? '—' : pct(v)}</b></div>
              <div className="sb-bar-track"><i style={{ width: `${(v ?? 0) * 100}%` }} /></div>
              <div className="sb-bar-why">{why}</div>
            </div>
          ))}
          <p className="sb-formula">Value Score = average of those three, &times;100.</p>

          <dl className="sb-derived">
            <div>
              <dt>Total Sticker<Explain term="sticker" dist={dist} distKey="sticker" value={d.coa} /></dt>
              <dd>{fmt$(d.coa)}</dd>
            </div>
            <div>
              <dt>Aid Share<Explain term="aid_share" dist={dist} distKey="aid_share" value={d.aidShare} /></dt>
              <dd>{pct(d.aidShare)}</dd>
            </div>
            <div>
              <dt>Discount<Explain term="discount" dist={dist} distKey="discount" value={d.discount} /></dt>
              <dd>{fmt$(d.discount)}</dd>
            </div>
            <div>
              <dt>Grant ÷ Tuition<Explain term="mgi" dist={dist} value={d.mgi} /></dt>
              <dd>{num(d.mgi, 2)}</dd>
            </div>
          </dl>
        </div>
      </div>

      <div className="sb-strip">
        <div className="sb-strip-l">Where this college would sit</div>
        <DistStrip summary={dist.dimensions?.value_score} value={d.valueScore}
          unit="score1" label="your college" />
      </div>

      {/* The misconception worth the most money, so it gets its own callout
          rather than hiding inside an explain card. */}
      <p className="sb-note">
        <b>Sticker &minus; grant is {fmt$(d.coa - vals.grant)}, but net price is {fmt$(vals.netPrice)}.</b>
        {' '}Different numbers, reported separately. The grant is an average across aided
        students; net price is what $75k&ndash;$110k families actually paid after every kind
        of aid. Only net price is a bill.
      </p>
    </div>
  );
}
