// The inline "what is this?" affordance.
//
// Teaching happens where the confusion does: next to the number, at the moment
// it is read, rather than in a section the user has to leave the table to find.
// Each card is three short lines plus a strip showing where this college's value
// sits among all of them.

import { useEffect, useRef, useState } from 'react';
import { TERMS } from '../education/glossary.js';
import { fmtUnit } from '../education/format.js';
import DistStrip from './DistStrip.jsx';

export default function Explain({ term, dist, value, distKey }) {
  const [open, setOpen] = useState(false);
  const wrap = useRef(null);
  const t = TERMS[term];

  // Dismiss on outside click or Escape. Without this the cards stack up as the
  // user works down the table, which buries the table they came to read.
  useEffect(() => {
    if (!open) return;
    const away = (e) => { if (!wrap.current?.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', away);
      document.removeEventListener('keydown', esc);
    };
  }, [open]);

  if (!t) return null;
  const summary = dist?.dimensions?.[distKey ?? term];

  // stopPropagation throughout: these buttons sit inside sortable <th> cells, and
  // asking what a column means must not also re-sort the table.
  return (
    <span className="explain" ref={wrap} onClick={(e) => e.stopPropagation()}>
      <button type="button" className="explain-btn" aria-expanded={open}
        aria-label={`What is ${t.label}?`}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}>?</button>

      {open && (
        <span className="explain-card" role="dialog" aria-label={t.label}>
          <b className="ec-term">{t.label}</b>
          <span className="ec-what">{t.what}</span>
          <code className="ec-how">{t.how}</code>
          <span className="ec-myth"><b>Careful:</b> {t.myth}</span>
          {summary && (
            <span className="ec-strip">
              <DistStrip summary={summary} value={value} unit={t.unit} />
            </span>
          )}
          {value != null && (
            <span className="ec-val">This college: <b>{fmtUnit(value, t.unit)}</b></span>
          )}
        </span>
      )}
    </span>
  );
}
