// Minimal Plotly wrapper (no react-plotly.js dependency needed).
import { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-dist-min';

export default function Plot({ data, layout, style }) {
  const el = useRef(null);
  useEffect(() => {
    const base = { displayModeBar: false, responsive: true };
    Plotly.react(el.current, data, { margin: { t: 10, r: 10, b: 40, l: 50 },
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      font: { family: 'Inter, sans-serif', size: 12, color: '#334155' },
      ...layout }, base);
  }, [data, layout]);
  return <div ref={el} style={{ width: '100%', height: 320, ...style }} />;
}
