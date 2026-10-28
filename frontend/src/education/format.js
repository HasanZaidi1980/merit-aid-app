// Shared value formatting. Lives here rather than in App.jsx so the table, the
// explain cards, the sandbox and the comparison all render the same number the
// same way -- a net price that reads $21,019 in one place and 21019.0 in another
// reads as two different figures.

export const fmt$ = (v) => (v == null ? '—' : '$' + Math.round(v).toLocaleString());
export const pct = (v) => (v == null ? '—' : (v * 100).toFixed(0) + '%');
export const num = (v, d = 0) => (v == null ? '—' : v.toFixed(d));

// `unit` comes from the glossary entry, so each term formats itself.
export function fmtUnit(v, unit) {
  if (v == null || Number.isNaN(v)) return '—';
  switch (unit) {
    case 'money': return fmt$(v);
    case 'pct': return pct(v);
    case 'score': return Math.round(v).toLocaleString();   // SAT points
    case 'score1': return num(v, 1);                       // Value Score
    case 'ratio': return num(v, 2);
    default: return String(v);
  }
}

export const ordinal = (n) => {
  if (n == null) return '—';
  const s = ['th', 'st', 'nd', 'rd'], v = n % 100;
  return n.toLocaleString() + (s[(v - 20) % 10] || s[v] || s[0]);
};
