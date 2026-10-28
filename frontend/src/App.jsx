import { useEffect, useMemo, useState } from 'react';
import Plot from './Plot.jsx';
import { getMeta, getColleges, getRagStatus, askRag } from './api.js';

const NAVY = '#1E2761', GREEN = '#2C7A4B', RED = '#c2453b';
const fmt$ = (v) => v == null ? '—' : '$' + Math.round(v).toLocaleString();
const pct = (v) => v == null ? '—' : (v * 100).toFixed(0) + '%';
// DATA_GAPS markers are display-only — a gap never drops a college from the ranking.
const GAP_LABELS = { no_sat: 'no SAT', no_admit_rate: 'no admit rate' };

export default function App() {
  const [meta, setMeta] = useState(null);
  const [dims, setDims] = useState({});           // dimension key -> on/off
  const [filters, setFilters] = useState({ maxNetPrice: 25000, mgiMedian: true, topN: 20, excludeFlagged: true });
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [sort, setSort] = useState({ key: 'RANK', dir: 1 });
  const [rag, setRag] = useState({ ready: false });
  const [q, setQ] = useState('');
  const [answer, setAnswer] = useState(null);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    getMeta().then((m) => {
      setMeta(m);
      setDims(Object.fromEntries(m.dimensions.map((d) => [d.key, true])));
    });
    getRagStatus().then((s) => setRag(s)).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    getColleges(filters).then((r) => { setRows(r.colleges); setLoading(false); })
      .catch(() => setLoading(false));
  }, [filters]);

  const on = (k) => dims[k];
  const sorted = useMemo(() => {
    const s = [...rows].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      if (x == null) return 1; if (y == null) return -1;
      return (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
    });
    return s;
  }, [rows, sort]);

  const names = Object.fromEntries(rows.map((r) => [r.UNITID, r.INSTNM]));
  const short = (n) => n && n.length > 22 ? n.slice(0, 20) + '…' : n;

  function downloadCSV() {
    const cols = Object.keys(rows[0] || {});
    const csv = [cols.join(',')].concat(rows.map((r) =>
      cols.map((c) => JSON.stringify(r[c] ?? '')).join(','))).join('\n');
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = 'merit_aid_rankings.csv'; a.click();
  }

  async function ask(question) {
    const text = question ?? q;
    if (!text) return;
    setAsking(true); setAnswer(null);
    try {
      const unitids = rows.map((r) => r.UNITID);
      const res = await askRag(text, unitids, names);
      setAnswer(res);
    } catch (e) { setAnswer({ answer: 'Request failed: ' + e.message, sources: [] }); }
    setAsking(false);
  }

  // ---- chart builders (each respects the dimension toggles) ----
  const labels = rows.map((r) => short(r.INSTNM));

  const dumbbell = () => {
    const data = [];
    rows.forEach((r, i) => data.push({
      x: [r.COA, r.NET_PRICE_MID], y: [i, i], mode: 'lines',
      line: { color: '#cbd5e1', width: 3 }, showlegend: false, hoverinfo: 'skip',
    }));
    data.push({ x: rows.map(r => r.COA), y: rows.map((_, i) => i), mode: 'markers',
      name: 'Sticker', marker: { color: RED, size: 9 },
      text: labels, hovertemplate: '%{text}<br>Sticker %{x:$,}<extra></extra>' });
    data.push({ x: rows.map(r => r.NET_PRICE_MID), y: rows.map((_, i) => i), mode: 'markers',
      name: 'Net price', marker: { color: GREEN, size: 9 },
      text: labels, hovertemplate: '%{text}<br>Net %{x:$,}<extra></extra>' });
    return data;
  };

  const parcoords = () => {
    const d = [];
    if (on('sticker')) d.push({ label: 'Sticker', values: rows.map(r => r.COA) });
    if (on('grant')) d.push({ label: 'Avg grant', values: rows.map(r => r.IGRNT_A) });
    if (on('admit_rate')) d.push({ label: 'Admit rate', values: rows.map(r => r.ADMISSIONS_RATE ?? 0) });
    if (on('grad_rate')) d.push({ label: 'Grad rate', values: rows.map(r => r.GRAD_RATE ?? 0) });
    if (on('net_price')) d.push({ label: 'Net price', values: rows.map(r => r.NET_PRICE_MID) });
    return [{ type: 'parcoords', dimensions: d,
      line: { color: rows.map(r => r.VALUE_SCORE), colorscale: 'Viridis' } }];
  };

  const scatterGenVal = () => [{
    x: rows.map(r => r.AID_SHARE), y: rows.map(r => r.VALUE_SCORE), mode: 'markers',
    marker: { size: 11, color: rows.map(r => r.VALUE_SCORE), colorscale: 'Viridis', showscale: false },
    text: labels, hovertemplate: '%{text}<br>Aid share %{x:.0%}<br>Value %{y:.0f}<extra></extra>',
  }];

  const valueBar = () => [{
    type: 'bar', orientation: 'h', x: sorted.map(r => r.VALUE_SCORE).reverse(),
    y: sorted.map(r => short(r.INSTNM)).reverse(),
    marker: { color: GREEN }, hovertemplate: '%{y}<br>Value %{x:.0f}<extra></extra>',
  }];

  const bubble = () => [{
    x: rows.map(r => r.NET_PRICE_MID), y: rows.map(r => r.GRAD_RATE), mode: 'markers',
    marker: { size: rows.map(r => Math.sqrt(Math.max(r.AID_SHARE, 0)) * 55 + 6),
      color: NAVY, opacity: 0.55, line: { color: '#fff', width: 1 } },
    text: labels, hovertemplate: '%{text}<br>Net %{x:$,}<br>Grad %{y:.0%}<extra></extra>',
  }];

  if (!meta) return <div className="loading" style={{ padding: 40 }}>Loading…</div>;

  const dimList = meta.dimensions;
  const cols = [
    ['RANK', '#', 'l'], ['INSTNM', 'College', 'l'], ['STABBR', 'St', 'l'],
    ['COA', 'Sticker'], ['IGRNT_A', 'Avg Grant'], ['NET_PRICE_MID', 'Net'],
    ['DISCOUNT', 'Discount'], ['ADMISSIONS_RATE', 'Admit'], ['GRAD_RATE', 'Grad'],
    ['SAT_TOTAL_75', 'SAT 75'], ['AID_SHARE', 'Aid Share'], ['VALUE_SCORE', 'Value'],
    ['COMPOSITE_LEGACY', 'Legacy'], ['DATA_GAPS', 'Gaps', 'l'],
  ];
  const cell = (r, k) => {
    if (['COA', 'IGRNT_A', 'NET_PRICE_MID', 'DISCOUNT'].includes(k)) return fmt$(r[k]);
    if (['ADMISSIONS_RATE', 'GRAD_RATE', 'AID_SHARE'].includes(k)) return pct(r[k]);
    if (['VALUE_SCORE', 'COMPOSITE_LEGACY'].includes(k)) return r[k]?.toFixed(1) ?? '—';
    if (k === 'DATA_GAPS') {
      const gaps = (r[k] || '').split(',').filter(Boolean);
      return gaps.length ? gaps.map((g) => GAP_LABELS[g] ?? g).join(', ') : '—';
    }
    return r[k] ?? '—';
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Merit Aid Finder</h1>
        <div className="sub">Hidden college deals · IPEDS 2022-23 · families $75k–$110k</div>

        <h2>Data dimensions</h2>
        {dimList.map((d) => (
          <label className="toggle" key={d.key}>
            <input type="checkbox" checked={!!dims[d.key]}
              onChange={() => setDims({ ...dims, [d.key]: !dims[d.key] })} />
            {d.label}
          </label>
        ))}

        <h2>Filters</h2>
        <div className="field">
          <label>Max net price: <span className="val">{fmt$(filters.maxNetPrice)}</span></label>
          <input type="range" min="5000" max="60000" step="1000" value={filters.maxNetPrice}
            onChange={(e) => setFilters({ ...filters, maxNetPrice: +e.target.value })} />
        </div>
        <div className="field">
          <label>Show top: <span className="val">{filters.topN}</span></label>
          <input type="range" min="5" max="50" step="5" value={filters.topN}
            onChange={(e) => setFilters({ ...filters, topN: +e.target.value })} />
        </div>
        <label className="toggle">
          <input type="checkbox" checked={filters.mgiMedian}
            onChange={() => setFilters({ ...filters, mgiMedian: !filters.mgiMedian })} />
          {/* Show the threshold actually applied. median_aid_share is a different
              ratio (grant / COA), so it can't stand in for it here. */}
          MGI ≥ median{meta.median_mgi != null ? ` (${meta.median_mgi.toFixed(2)})` : ''}
        </label>
        <label className="toggle">
          <input type="checkbox" checked={filters.excludeFlagged}
            onChange={() => setFilters({ ...filters, excludeFlagged: !filters.excludeFlagged })} />
          Exclude flagged
        </label>
        <p className="hint">
          Drops only colleges whose ranking is unreliable — a partly reconstructed
          sticker price. A missing SAT or admissions rate never removes a college;
          those show up in the Gaps column instead.
        </p>
      </aside>

      <main className="main">
        <div className="header">
          <h1>Hidden Deals: Institutional Aid vs Sticker Price</h1>
          <p>4-year colleges ranked by all-around value · U.S. Dept. of Education IPEDS 2022-23</p>
        </div>

        <div className="stats">
          <div className="stat"><div className="n">{meta.colleges_in_dataset.toLocaleString()}</div><div className="l">Colleges in dataset</div></div>
          <div className="stat"><div className="n">{loading ? '…' : rows.length}</div><div className="l">Shown after filters</div></div>
          <div className="stat"><div className="n">{pct(meta.median_aid_share)}</div><div className="l">Median aid share</div></div>
          <div className="stat"><div className="n">{rows[0] ? fmt$(rows[0].DISCOUNT) : '—'}</div><div className="l">Top pick discount</div></div>
        </div>

        {loading ? <div className="loading">Crunching the rankings…</div> : (
        <>
          <div className="grid">
            <div className="card">
              <h3>The Discount Gap</h3>
              <p className="cap">Each line runs from full sticker (red) to what mid-income families actually pay (green). #1 on top.</p>
              <Plot data={dumbbell()} layout={{ yaxis: { autorange: 'reversed', showticklabels: false }, xaxis: { tickformat: '$,.0s' }, showlegend: true, legend: { orientation: 'h', y: 1.1 } }} />
            </div>
            <div className="card">
              <h3>Trade-offs at a Glance</h3>
              <p className="cap">Each college is one line across price, aid and quality axes, colored by Value Score. Toggle dimensions in the sidebar.</p>
              <Plot data={parcoords()} layout={{ margin: { t: 30, r: 30, b: 20, l: 30 } }} />
            </div>
            <div className="card">
              <h3>Generosity vs Overall Value</h3>
              <p className="cap">Aid share = institutional grants ÷ total sticker. Top-right = generous AND strong all-around.</p>
              <Plot data={scatterGenVal()} layout={{ xaxis: { tickformat: '.0%', title: 'Aid share' }, yaxis: { title: 'Value Score' } }} />
            </div>
            <div className="card">
              <h3>Value Ranking</h3>
              <p className="cap">Value Score 0–100: the mean of three percentile ranks — affordability, graduation rate, aid generosity.</p>
              <Plot data={valueBar()} layout={{ margin: { l: 130, t: 10, r: 10, b: 30 } }} />
            </div>
          </div>

          <div className="card">
            <h3>Price, Quality and Generosity Together</h3>
            <p className="cap">Up and to the left is the dream: high grad rate at low real price. Bubble area scales with aid share.</p>
            <Plot data={bubble()} layout={{ xaxis: { tickformat: '$,.0s', title: 'Net price' }, yaxis: { tickformat: '.0%', title: '4-yr grad rate' } }} style={{ height: 360 }} />
          </div>

          <div className="card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div><h3>Comparison table</h3><p className="cap">Every metric for the shortlist — click any header to sort. "Legacy" is the original assignment formula.</p></div>
              <button className="btn" onClick={downloadCSV}>⬇ Download CSV</button>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table>
                <thead><tr>{cols.map(([k, lbl, cls]) => (
                  <th key={k} className={cls || ''} onClick={() => setSort({ key: k, dir: sort.key === k ? -sort.dir : 1 })}>
                    {lbl}{sort.key === k ? (sort.dir === 1 ? ' ▲' : ' ▼') : ''}
                  </th>))}</tr></thead>
                <tbody>{sorted.map((r) => (
                  <tr key={r.UNITID}>{cols.map(([k, , cls]) => (
                    <td key={k} className={cls || ''}>{cell(r, k)}</td>))}</tr>))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="card rag">
            <h3>Ask about mission &amp; values (AI)</h3>
            <p className="cap">Sanity-check the numbers against what each college says it stands for. Answers draw only from the mission statements of the colleges shown above. {rag.index_ready ? '' : '(index warming up)'}</p>
            <div className="chips">
              {['Which of these schools emphasize leadership and service?',
                'Which colleges focus on undergraduate research?',
                'Are any of these faith-based institutions?',
                'Which schools talk about affordability or access?'].map((c) => (
                <span className="chip" key={c} onClick={() => { setQ(c); ask(c); }}>{c}</span>))}
            </div>
            <div className="row">
              <input type="text" value={q} placeholder="Ask a question…"
                onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask()} />
              <button className="btn" onClick={() => ask()} disabled={asking}>{asking ? 'Asking…' : 'Ask'}</button>
            </div>
            {answer && (
              <div className="answer">
                {answer.answer}
                {answer.sources?.length ? <div className="src">Sources: {answer.sources.map((s) => names[s.unitid] || s.unitid).join(' · ')}</div> : null}
              </div>
            )}
          </div>
        </>)}
      </main>
    </div>
  );
}
