// The correction the app owes its own name.
//
// Every generosity figure here comes from IGRNT_A, which is need-based and merit
// grants added together, and some of the top-ranked colleges award no merit aid
// at all. The rankings are not wrong -- the net prices are real -- but a family
// reading them as merit scholarships is being misled about the mechanism, so the
// correction goes where the ranking is, not in a footnote.

import { MERIT_DISCLOSURE as D } from '../education/glossary.js';

export default function MeritNote({ meta, shown = 0 }) {
  const cov = meta?.merit_policy_coverage;
  return (
    <div className="card merit-note">
      <h3>⚠ {D.headline}</h3>
      {D.body.map((p) => <p className="cap" key={p.slice(0, 24)}>{p}</p>)}
      <p className="cap mn-foot">
        {shown > 0 && (
          <>
            <b>{shown}</b> of the colleges shown
            {' '}{shown === 1 ? 'reports' : 'report'} no merit aid in their own Common
            Data Set — marked <em>no merit aid</em> in the table.{' '}
          </>
        )}
        {/* Three numbers, not one. A bare "24 checked" invites being read against
            1,907 as though the rest came back negative; resolved-of-attempted is
            what we can actually stand behind, and the total says how little of the
            dataset the effort touched. */}
        We read the Common Data Set for <b>{cov?.verified ?? 0}</b> institutions,
        from <b>{cov?.attempted ?? 0}</b> attempted, out of{' '}
        {meta?.colleges_in_dataset?.toLocaleString() ?? '—'}. Each label names the
        CDS edition it came from, because the answer moves: Yale reported 24
        non-need awards in 2024-25 and none in 2025-26. A label older than{' '}
        {cov?.stale_after_editions ?? 2} editions behind{' '}
        {cov?.current_edition ?? '2025-26'} expires back to unchecked rather than
        standing as a current claim.
      </p>
      <p className="cap mn-foot">
        {/* Say the skew where the number appears, not in a doc nobody opens. */}
        Sourcing went to the default top 50 — the rows you actually see — and all 50
        were attempted. That shortlist is 48 private nonprofits and 2 publics,
        against 57% private across the whole dataset, so this hit rate reflects the
        best-documented end of higher education and not the dataset. A dash means{' '}
        <b>not checked</b>; <em>not published</em> means we looked and the college
        does not publish a readable H2A. Neither is a finding that merit aid is on
        offer, or that it is not.
      </p>
    </div>
  );
}
