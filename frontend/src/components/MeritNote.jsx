// The correction the app owes its own name.
//
// Every generosity figure here comes from IGRNT_A, which is need-based and merit
// grants added together, and 11 of the top 23 ranked colleges award no merit aid
// at all. The rankings are not wrong -- the net prices are real -- but a family
// reading them as merit scholarships is being misled about the mechanism, so the
// correction goes where the ranking is, not in a footnote.

import { MERIT_DISCLOSURE as D } from '../education/glossary.js';

export default function MeritNote({ meta, shown = 0 }) {
  return (
    <div className="card merit-note">
      <h3>⚠ {D.headline}</h3>
      {D.body.map((p) => <p className="cap" key={p.slice(0, 24)}>{p}</p>)}
      <p className="cap mn-foot">
        {shown > 0 && (
          <>
            <b>{shown}</b> of the colleges shown
            {' '}{shown === 1 ? 'is' : 'are'} on a curated list of institutions that publicly
            award no merit scholarships — marked <em>need-based only</em> in the table.{' '}
          </>
        )}
        That list covers {meta?.no_merit_aid_count ?? 0} institutions out of{' '}
        {meta?.colleges_in_dataset?.toLocaleString() ?? '—'}, so a blank means
        <b> not checked</b>, not that merit aid is on offer. Splitting the two properly
        needs Common Data Set section H2A, per institution.
      </p>
    </div>
  );
}
