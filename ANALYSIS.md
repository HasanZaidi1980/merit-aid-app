# Merit Aid Finder — Live App Analysis

Target: `http://136.68.78.253/` — inspected live on 10 Aug 2026.

## IMPORTANT: what can and can't be copied from a URL

The full source code **cannot** be recovered by visiting the website. A browser only receives:
- the **compiled/minified** frontend bundle (not the original readable React source), and
- **data** returned by the API (not the code that produced it).

The backend Python (FastAPI + RAG), Terraform, Kubernetes manifests, and Dockerfiles are never sent to the browser — they live on the server and in the GitHub repo. So a folder of "replicated" backend code would be a **reconstruction from the outside**, not your friend's actual code, and it could not be verified against his or guaranteed mistake-free.

**For a true, verified copy, get the repo** (ask your friend to `git clone`, `git bundle`, or zip it — or add you later). Everything below is what was legitimately observable from the running app.

---

## What the app is

A "Merit Aid Finder" — 4-year colleges ranked by all-around value for families earning $75k–$110k, using IPEDS 2022-23 data. It matches the build prompt we wrote, and the friend extended it.

**Charts present (more than the original 2):**
1. The Discount Gap (dumbbell) — sticker vs net price
2. Trade-offs at a Glance (parallel coordinates)
3. Generosity vs Overall Value (scatter)
4. Value Ranking (scored bar/strip)
5. Price, Quality and Generosity Together (bubble; area = aid share)
6. Sortable comparison table with CSV download
7. RAG "Ask about mission & values (AI)" chat panel

**Scoring evolved:** the original assignment formula is kept as `COMPOSITE_LEGACY`. The new headline metric is **Value Score (0–100)** = the average of three percentile ranks (affordability, graduation rate, aid generosity), equally weighted. Rows also carry `RISK_FLAGS` and `COMPONENTS_USED`, i.e. it degrades gracefully when a data dimension is missing — as specified.

**Dataset (from `/api/meta`):** 1,907 colleges; median aid share 0.318; net price range $2,200–$63,997; 1,352 flagged; SAT coverage 985.

---

## Cloud, hosting & storage (evidence-based)

**Hosting — Google Cloud Platform (GCP).**
- Every response carries `via: 1.1 google` → traffic flows through a **Google Cloud Load Balancer**. This is the strongest signal, and it matches the GCP target in the build prompt.
- The raw IP (`136.68.78.253`, no domain, plain HTTP) is the load balancer's external IP — consistent with the "no custom domain / HTTPS optional" decision.

**Web server — nginx.**
- `server: nginx/1.27.5` serves the frontend. The frontend is **static files** (a Vite build: `assets/index-CYJlgjog.js` + `assets/index-Bt4x7w8r.css`), so nginx is acting as the static host + reverse proxy to the API.

**Compute — almost certainly GKE (Google Kubernetes Engine).**
- The build prompt targeted GKE, and the split (nginx front-end pod + `/api` backend pod behind one load balancer) is the classic GKE + Ingress layout.
- Corroborating signal: during inspection the `/api/*` routes briefly returned **502 Bad Gateway** while the static site stayed up — i.e. nginx was healthy but the upstream backend was momentarily unreachable. That front/back split is exactly what you'd see with separate Kubernetes Deployments/Services.

**Backend — FastAPI (Python).**
- JSON API under `/api/*` with query-param filtering; response shapes and the `/docs`-style layout are typical FastAPI. (Serves `application/json`.)

**AI / RAG — live and working.**
- `GET /api/rag/status` → `{ "index_ready": true, "api_key_set": true }`. So the vector index is built and an API key (Anthropic, per the build prompt) is configured — presumably via Kubernetes Secret / Google Secret Manager, not hard-coded.

**Storage (inferred — not directly visible):**
- Per the build prompt, the 8 IPEDS CSVs live in a **Cloud Storage bucket** and the **vector index on a Persistent Disk (PVC)**. The live app can't confirm the backend's disk layout from outside, but `index_ready: true` means the embeddings are persisted and loaded server-side.

### One-line summary
Static React/Vite frontend served by **nginx**, a **FastAPI** backend, and a **RAG** service, containerized and running on **GKE** behind a **Google Cloud Load Balancer** — all on **GCP**, with data in **Cloud Storage** and the vector index on a **Persistent Disk**.

---

## The honest bottom line on "no mistakes in the existing app"

Checking the existing app for mistakes requires reading the existing app's code. From the outside I can only see behavior, not implementation — I can't spot bugs in logic I can't read. The one behavioral issue I *did* observe is the intermittent **502 on `/api/*`** (backend flakiness / restart / resource limits) — worth mentioning to your friend as a real, reproducible symptom.

See `observed-api-contract.md` for the exact endpoints and data shapes recovered from the live app.
