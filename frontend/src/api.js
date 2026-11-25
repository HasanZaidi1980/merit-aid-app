// Thin API client. Same-origin /api/* — nginx proxies to the backend in prod,
// Vite proxies in dev.

// Errors carry what the server said, not just that something went wrong.
//
// This used to be `if (!r.ok) throw new Error(r.status)`, which discarded the
// response body — so the one message worth showing a user was the one message
// thrown away. The backend answers a missing dataset with 503 and a `detail` that
// names the file and the directory it looked in (see app/data.py), and a bad filter
// with a 400 or 422 that names the parameter. Those diagnose the problem; "Error:
// 503" does not.
//
// `kind` separates the two failures the UI has to describe differently:
//   'unreachable' — fetch itself rejected. No server answered: it is down, the pod
//                   is not ready, or the network is gone. Nothing to quote.
//   'http'        — a server answered and said no. Quote it.
async function j(r) {
  if (r.ok) return r.json();

  let detail = '';
  try {
    const body = await r.json();
    // FastAPI's validation errors put an array of objects in `detail`; its
    // HTTPException puts a string there.
    detail = typeof body.detail === 'string'
      ? body.detail
      : Array.isArray(body.detail)
        ? body.detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join('; ')
        : '';
  } catch {
    /* not JSON — a proxy error page, say. Fall back to the status alone. */
  }

  const err = new Error(detail || `HTTP ${r.status} from the API`);
  err.kind = 'http';
  err.status = r.status;
  err.detail = detail;
  throw err;
}

// fetch rejects (rather than resolving with !ok) when nothing answered at all.
const call = (url) => fetch(url).then(j, (cause) => {
  const err = new Error('The API did not respond.');
  err.kind = 'unreachable';
  err.cause = cause;
  throw err;
});

export const getMeta = () => call('/api/meta');
export const getColleges = (f) => {
  const q = new URLSearchParams({
    max_net_price: f.maxNetPrice, mgi_at_least_median: f.mgiMedian,
    top_n: f.topN, exclude_flagged: f.excludeFlagged,
    exclude_no_merit: f.excludeNoMerit,
  });
  return call(`/api/colleges?${q}`);
};
// Reference distributions for the education section. Fetched once -- they describe
// the whole dataset and never change while the server is up.
export const getDistributions = () => call('/api/education/distributions');
