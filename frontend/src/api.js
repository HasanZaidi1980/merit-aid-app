// Thin API client. Same-origin /api/* — nginx proxies to the backend in prod,
// Vite proxies in dev.
const j = (r) => { if (!r.ok) throw new Error(r.status); return r.json(); };

export const getMeta = () => fetch('/api/meta').then(j);
export const getColleges = (f) => {
  const q = new URLSearchParams({
    max_net_price: f.maxNetPrice, mgi_at_least_median: f.mgiMedian,
    top_n: f.topN, exclude_flagged: f.excludeFlagged,
    exclude_no_merit: f.excludeNoMerit,
  });
  return fetch(`/api/colleges?${q}`).then(j);
};
// Reference distributions for the education section. Fetched once -- they describe
// the whole dataset and never change while the server is up.
export const getDistributions = () => fetch('/api/education/distributions').then(j);
