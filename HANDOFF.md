# Handoff — Merit Aid App (current status)

For Claude Code or Claude Cowork picking this up. Read `PROJECT_BRIEF.md` next for full architecture, metrics, and task ideas; this doc is just *where things stand right now*. See "Who works on this" below for how the two agents split the work.

## Status: real data, runs locally, not deployed

*Last updated 2026-10-28 @ `ec37a8a`.*

- **On real IPEDS 2022-23 data.** 1,907 colleges. Validated against the reference
  app's published numbers — 4 of 5 match exactly; the fifth is explained (see below).
- **In git and on GitHub.** `main` @ `ec37a8a`, pushed to
  github.com/HasanZaidi1980/merit-aid-app.
- **Works locally.** Docker (`docker compose up --build` → http://localhost:8080) and
  direct (uvicorn :8000 + vite :5173).
- **17 tests pass.** `cd backend && pytest` — in-memory fixtures, no data files needed.
- **Not deployed to GCP.** Nothing pushed to GKE/Artifact Registry. `DEPLOYMENT.md` has
  the steps; they have not been run. The manifests contain a known bug — see
  `PROJECT_STATE.md` Phase 8.

## New to this project? Start here

1. `git clone https://github.com/HasanZaidi1980/merit-aid-app.git`
2. **Get data.** `backend/data/` is gitignored, so a clone has none. Either copy that
   folder from someone who has it, or `python backend/scripts/make_sample_data.py`.
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
  - **COA construction** vs net price. The one unexplained gap: `median_aid_share` is
    0.343 against the reference's 0.3184. A larger denominator closes it, which points at
    COA. `PROJECT_STATE.md` Phase 3 has the fix.
  - **Percentage-scaling heuristic** for admit/grad rates (`max > 1.5` is fragile).
  - **Equal 1/3 weighting** in Value Score is an assertion, not a finding.
  - **The curated need-only list** (26 colleges) is provisional — compiled from published
    institutional policy, not yet checked against each school's Common Data Set.
  - Reference app showed intermittent **502s** on `/api/*` — reproduce under load.
- **17 tests** cover scoring, the flag split, net-price coalescing and merit policy.
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

Phases 1-2 are **complete**: real data loaded and validated. Phase 3 (the COA
question) is unblocked and is the highest-value next change. Phase 4 — splitting
merit aid from need-based aid via the Common Data Set — is **deferred by decision**,
not dropped.

Recent work: the app no longer calls any generosity metric "merit" (IPEDS conflates
need-based and merit grants and publishes no split), an education section was added,
and the trade-offs chart was rebuilt so its lines can be told apart.

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
  README.md               how to run
  ANALYSIS.md             what the reference app is + cloud/hosting findings
  observed-api-contract.md  exact endpoints + 25-field schema
  DEPLOYMENT.md           GCP deploy + teardown
  docker-compose.yml
  backend/   app/{config,data,scoring,merit_policy,education,rag,main}.py
             scripts/  tests/  requirements.txt  Dockerfile
  frontend/  src/{App.jsx,Plot.jsx,api.js,main.jsx,styles.css}
             src/education/  src/components/  nginx.conf  Dockerfile
  deploy/    terraform/*.tf   k8s/*.yaml
```
