# Handoff — Merit Aid App (current status)

For Claude Code or Claude Cowork picking this up. Read `PROJECT_BRIEF.md` next for full architecture, metrics, and task ideas; this doc is just *where things stand right now*. See "Who works on this" below for how the two agents split the work.

## Status: real data, tested, deployed and running on GCP

*Last updated 2026-11-25.*

- **On real IPEDS 2022-23 data.** 1,907 colleges. Validated against the reference
  app's published numbers — 4 of 5 match exactly; the fifth is explained (see below).
- **In git and on GitHub.** `main` pushed to
  github.com/HasanZaidi1980/merit-aid-app.
- **Works locally.** Docker (`docker compose up --build` → http://localhost:8080) and
  direct (uvicorn :8000 + vite :5173).
- **88 tests pass.** `cd backend && pytest` — in-memory fixtures plus the synthetic
  CSVs in `backend/tests/fixtures/`, so no real data files are needed. `ruff check .`
  is clean and both run in CI on every push (`.github/workflows/ci.yml`).
- **`python scripts/smoke_test.py`** boots real uvicorn over generated sample data and
  checks the three endpoints a deployment check would call. Touches nothing in
  `backend/data/`.
- **Live on GCP** *(2026-11-20; address made static 2026-11-25, so a redeploy keeps it)*.
  GKE zonal cluster in `us-central1-a`, two Spot `e2-medium` nodes, two replicas of each
  service on separate nodes, images in Artifact Registry, the six CSVs in
  `gs://merit-aid-ipeds-2026/` and copied onto each pod at start by an init container.
  **It billed $17.71 over 2026-11-01→27, about $2.53/day** — read from Billing → Reports
  on 2026-11-27, which also closed two open questions: the free zonal-cluster credit *is*
  applying (no cluster-management SKU appears at all) and the static IP does *not* bill
  while attached. The largest single line is the node boot disks at $4.54 — 2 × 100 GB,
  GKE's default, never chosen. `DEPLOYMENT.md` → Cost has the full SKU breakdown and the
  teardown cycle, which is `terraform destroy`, never a billing change (five-plus
  projects share that billing account). It is up deliberately for the demo.
- **HTTPS on a real domain** *(2026-11-28)*. `https://merit-aid-finder.com/` serves with
  a Google-managed certificate; the domain is registered through Cloud Domains at
  $12.00/year, renewing 2027-11-27. The apex A record is Terraform-managed and reads the
  static-IP resource, so the name and the address cannot drift. **`http://136.81.186.158/`
  is untouched and still serving** — there is no redirect, on purpose, so the
  certificate-free path stays a guaranteed fallback. `www` does not resolve and is not
  claimed to.
- **The UI explains its own failures** *(Phase 5, 2026-11-25)*. An unreachable API, an
  API that answers with a reason, and filters that match nothing are three different
  messages now, verified against the live site by scaling the backend to zero.

## New to this project? Start here

1. `git clone https://github.com/HasanZaidi1980/merit-aid-app.git`
2. **Get data.** `backend/data/` is gitignored, so a clone has none. Ask whoever set
   the project up for `merit-aid-data.zip` (that folder, zipped, ~3.8 MB) and unzip it
   into `backend/`. No one to ask? `python backend/scripts/make_sample_data.py` gives
   you a 300-college demo instead.
3. **Run it.** `docker compose up --build` → http://localhost:8080. No Docker? See
   `README.md` Option B (uvicorn + vite).
4. **Read, in this order:** `PROJECT_STATE.md` (where things stand, what's next) →
   `PROJECT_BRIEF.md` (architecture, formulas, gotchas).
5. **Before changing any formula**, read `PROJECT_BRIEF.md` §5 and §6. Several
   non-obvious decisions there are deliberate and tested; §4 of `PROJECT_STATE.md`
   lists the ones that are settled.

## Who works on this: Claude Code + Claude Cowork

Both agents work on this project together, with **equal access**. Claude Cowork is not a
read-only reviewer: it may run console commands and edit files in this repo whenever the
task calls for it, the same as Claude Code.

**The one asymmetry: only Claude Code commits.** Git is the single place where two agents
writing at once turns into a mess, so all `git add` / `commit` / `push` / branch / merge /
rebase operations go through Claude Code. Claude Cowork never commits, even for a one-line
change, and never resolves a merge conflict.

How that works in practice:

- **Cowork edits freely, then hands off.** When Cowork finishes a change it reports which
  files it touched and why; Claude Code reviews, stages, and commits them.
- **Say what you're opening.** Before editing a file, announce it, so the two agents don't
  write to the same file in parallel. Last-writer-wins silently destroys the other's work.
- **Leave the tree committable.** Don't leave a file half-edited or syntactically broken at
  the end of a turn — Claude Code may commit on top of it.
- **Claude Code owns `.gitignore` and anything git-related** (hooks, CI config, branch
  layout), since it's the one that has to live with the result.
- **Neither agent commits secrets or data.** `.env`, `backend/data/`, `backend/index/`, and
  the virtualenvs are gitignored — keep it that way.

## Important context

This is a **from-scratch reconstruction** that matches the *observable behavior* of a reference app (`http://136.68.78.253/`) — same API endpoints, data schema, charts, and described scoring. It is **NOT** the original author's source code (that was never available). See `ANALYSIS.md` and `observed-api-contract.md`.

## What's verified vs unverified

- **Verified:** all 7 API endpoints, frontend build, Docker boot, and the pipeline against
  the reference app's own numbers — `colleges_in_dataset` 1,907, `net_price_min` 2,200,
  `net_price_max` 63,997 and `sat_coverage` 985 all reproduce **exactly**.
- **Unverified — audit these:**
  - **Percentage-scaling heuristic** for admit/grad rates (`max > 1.5` is fragile).
  - **Equal 1/3 weighting** in Value Score is an assertion, not a finding.
  - ~~The curated need-only list is provisional~~ — **checked 2026-11-17 and 5 of its
    26 entries were wrong.** Now CDS-sourced with provenance for 9 institutions;
    the other 17 are `unknown`. A full crawl was measured and recommended against.
  - Reference app showed intermittent **502s** on `/api/*` — reproduce under load.
- **88 tests** cover scoring, the flag split, net-price coalescing, merit policy and
  its provenance, the COA basis, declared rate scales and the Value Score weights.
  No endpoint tests yet.

## Data

- **Real IPEDS 2022-23 is installed** in `backend/data/` — 7 files, ~21 MB.
- `backend/data/` is **gitignored**, so a fresh clone has no data. Either copy the folder
  across or run `python backend/scripts/make_sample_data.py` for a 300-college demo.
- Demo mode caveat: sample UNITIDs are synthetic, so the "Merit aid" column is all
  dashes. That is deliberate — see the note in the generator.

## Fixes already applied this session (so they're not re-flagged)

- Old PowerShell rejects `&&` — run commands one per line.
- Local `pip install scikit-learn` fails on Python 3.13 (no wheel) — not needed locally; Docker builds it on 3.12. Local step only needs `pandas numpy` for sample data.
- `frontend/nginx.conf` and `frontend/.dockerignore` had been lost in an earlier cleanup and were missing from the user's copy — **recreated**; the Docker build needs `nginx.conf`.

## Next steps

**See `PROJECT_STATE.md`** — it owns the roadmap, phase by phase, with a "done when"
for each. Don't keep a second list here; it drifts.

Phases 1-3.5 are **complete**. Phase 4 is **scoped down by measurement**: the merit
split is CDS-sourced across the default top 50 — 50 attempted, 23 resolved; 24 of
1,907 dataset-wide — with provenance and an expiry, and a 1,907-institution crawl is
recommended against (38% end-to-end success on the 26 best-documented institutions;
an existing third-party archive finds no public CDS for 49% of 3,000 schools).

**Every phase is now closed.** Phases 5, 6, 8, 9 and 10 are done; **Phase 7 (IPEDS
2023-24) was built, validated green on branch `phase7-ipeds-2023-24`, and deliberately
not adopted** — the new `GBA4RTT` is the 2017 subcohort whose four-year window closes in
the pandemic year, which reshuffles the top of the rankings for a reason unrelated to
college value. The branch is kept; switching is `IPEDS_YEAR=2023-24` plus the six new
CSVs in the bucket.

Two things are genuinely outstanding, and neither is code:

1. **Two measured cost savings are left on the table on purpose**, both because they
   mutate the cluster: dropping the node boot disks from GKE's default 100 GB (~$13/mo,
   recreates the node pool) and trimming the eleven managed-Prometheus component groups
   (~$7/mo, control-plane change). Take them after the presentation, not before.
2. **Teardown is still unverified**, by choice — the stack is up for the demo.

**A human is notified now** *(2026-11-28)*. An email channel sits on the alert policy
beside the Pub/Sub one, and delivery was proven with a failing decoy check that tripped a
real incident in **~292 seconds**. The address lives in cloud config, never in this repo.
One policy covers both uptime checks — it filters on `resource.type = "uptime_url"` with
no `check_id`, so adding a check needs no policy change. See `DEPLOYMENT.md` →
Monitoring for the recipe and for what the test does *not* prove.

Recent work: Phase 3 replaced the hand-summed cost of attendance with the basket
IPEDS itself nets against (459 impossible negative discounts → 0); rate scaling became
a declaration rather than a guess; Value Score weights became configurable. Then the
**RAG panel was removed** — it ran on fabricated mission text — and the **merit-aid
roster was corrected**, five of its 26 entries having asserted the opposite of what
those colleges' own Common Data Sets report. `FORMULAS.md` holds the formulas.

## Guardrails

- Keep the API contract in `observed-api-contract.md` stable (frontend depends on it).
- **Only Claude Code commits** — Claude Cowork has equal access to files and the console but never runs git write commands (see "Who works on this" above).
- `ANTHROPIC_API_KEY` from env / K8s secret only — never commit or log it.
- Don't commit real IPEDS data or the generated vector index (already git-ignored).

## File map
```
merit-aid-app/
  HANDOFF.md              ← this file (current status)
  PROJECT_STATE.md        status + the full roadmap to completion — read next
  PROJECT_BRIEF.md        full architecture, metrics, task list
  FORMULAS.md             every formula + why — read before changing any of them
  README.md               how to run
  ANALYSIS.md             what the reference app is + cloud/hosting findings
  observed-api-contract.md  exact endpoints + 25-field schema
  DEPLOYMENT.md           GCP deploy + teardown
  docker-compose.yml
  backend/   app/{config,data,scoring,merit_policy,education,main}.py
             scripts/  tests/  requirements.txt  Dockerfile
  frontend/  src/{App.jsx,Plot.jsx,api.js,main.jsx,styles.css}
             src/education/  src/components/  nginx.conf  Dockerfile
  deploy/    terraform/*.tf   k8s/*.yaml
```
