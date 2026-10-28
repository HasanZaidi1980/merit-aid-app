// Plain-English definitions for the education section and the inline explain
// cards.
//
// Deliberately terse. These get read by a parent partway through a decision, not
// by a researcher, and every extra clause is one more thing to misread. Three
// lines each, no more: what it is, how it is worked out, and the mistake people
// actually make with it.
//
// `myth` is the load-bearing field. Every one of these numbers is routinely
// misread in a specific, predictable way, and naming that error does more for
// comprehension than a longer definition would.

export const TERMS = {
  sticker: {
    label: 'Total Sticker (COA)',
    what: 'The full published price for one year.',
    how: 'tuition + housing + books',
    myth: 'Almost nobody pays this.',
    unit: 'money',
  },
  grant: {
    label: 'Avg Institutional Grant',
    what: 'Free money the college itself gives, averaged per aided student.',
    how: 'college grant dollars ÷ students who got one',
    myth: 'Mixes need-based and merit aid together — IPEDS never splits them.',
    unit: 'money',
  },
  net_price: {
    label: 'Net Price',
    what: 'What a $75k–$110k family actually pays.',
    how: 'sticker − grants (loans are not subtracted)',
    myth: 'This is the real number. The sticker is the distraction.',
    unit: 'money',
  },
  admit_rate: {
    label: 'Admissions Rate',
    what: 'Share of applicants let in.',
    how: 'admitted ÷ applied',
    myth: 'A low rate means popular, not better taught.',
    unit: 'pct',
  },
  grad_rate: {
    label: 'Graduation Rate',
    what: 'Share who finish the degree in four years.',
    how: 'graduated in 4 years ÷ started',
    myth: 'A fifth year adds a whole year of cost.',
    unit: 'pct',
  },
  sat: {
    label: 'SAT 75th',
    what: 'One in four admitted students scored above this.',
    how: '75th percentile of admitted scores',
    myth: 'Not a cutoff — three in four admits scored below it.',
    unit: 'score',
  },
  // --- derived metrics: same treatment, since the table shows them too ---
  aid_share: {
    label: 'Aid Share',
    what: 'How much of the sticker the college covers itself.',
    how: 'grant ÷ sticker',
    myth: 'Generosity, not merit. Need-based aid counts here too.',
    unit: 'pct',
  },
  discount: {
    label: 'Discount',
    what: 'The gap between the price on the website and the price you pay.',
    how: 'sticker − net price',
    myth: 'A big discount off a huge sticker can still cost more.',
    unit: 'money',
  },
  value_score: {
    label: 'Value Score',
    what: '0–100. How a college ranks on cost, finishing and generosity at once.',
    how: 'average of three percentile ranks',
    myth: 'A rank among colleges, not a grade. 50 is exactly average.',
    unit: 'score1',
  },
  mgi: {
    label: 'Grant ÷ Tuition',
    what: 'Grant measured against tuition alone, ignoring housing and books.',
    how: 'grant ÷ tuition',
    myth: 'Originally called a "merit" index. It does not measure merit.',
    unit: 'ratio',
  },
};

// Why the generosity numbers cannot be read as merit numbers. Shown wherever the
// app would otherwise imply that it found merit scholarships.
export const MERIT_DISCLOSURE = {
  headline: 'Institutional grant aid is not merit aid',
  body: [
    'IPEDS publishes one figure for all grant money a college gives — need-based '
    + 'and merit awards added together. No variable splits them.',
    'The two work in opposite ways. Need-based aid depends on your family\'s '
    + 'finances. Merit aid depends on the student\'s record. A college can be '
    + 'very generous and still have nothing a strong student can earn.',
    'So read Aid Share and Grant ÷ Tuition as generosity, not merit.',
  ],
};

// Table column -> glossary key, for the explain affordance on table headers.
export const COLUMN_TERMS = {
  COA: 'sticker',
  IGRNT_A: 'grant',
  NET_PRICE_MID: 'net_price',
  DISCOUNT: 'discount',
  ADMISSIONS_RATE: 'admit_rate',
  GRAD_RATE: 'grad_rate',
  SAT_TOTAL_75: 'sat',
  AID_SHARE: 'aid_share',
  VALUE_SCORE: 'value_score',
};
