# Handoff — Merit Aid App (current status)

For Claude Code or Claude Cowork picking this up. Read `PROJECT_BRIEF.md` next for full architecture, metrics, and task ideas; this doc is just *where things stand right now*. See "Who works on this" below for how the two agents split the work.

## Status: runs locally, not deployed

- **Works locally via Docker.** `docker compose up --build` builds both images and serves the app at http://localhost:8080. Backend confirmed starting cleanly (`Uvicorn running on 0.0.0.0:8000`, "Application startup complete").
- **Not deployed to GCP.** Nothing pushed to GKE/Cloud/Artifact Registry. Deployment steps exist in `DEPLOYMENT.md` but have not been run.
- **Not in git / not on GitHub.** The project lives only as local files on the user's machine (`C:\Users\amatu\Downloads\merit-aid-app`) plus the zip from this chat. No repo initialized yet.

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

- **Verified:** backend API (meta, colleges, RAG endpoints), frontend build, Docker stack boot, sample-data generation.
- **Unverified — audit these:**
  - **Scoring formulas** (`backend/app/scoring.py`) are reconstructed from on-screen descriptions, not confirmed against the original. The Value Score / percentile logic is the top priority to validate.
  - **COA construction** vs net price (apples-to-apples for Discount / Aid Share).
  - **Percentage-scaling heuristic** for admit/grad rates against the real IPEDS files.
  - Reference app showed intermittent **502s** on `/api/*` — reproduce under load.
- **No automated tests exist yet.**

## Data

- Currently running on **generated sample data** (`backend/scripts/make_sample_data.py` → `backend/data/`).
- Real IPEDS files drop into `backend/data/` with the same 8 names (see PROJECT_BRIEF §4). Not yet swapped in.

## Fixes already applied this session (so they're not re-flagged)

- Old PowerShell rejects `&&` — run commands one per line.
- Local `pip install scikit-learn` fails on Python 3.13 (no wheel) — not needed locally; Docker builds it on 3.12. Local step only needs `pandas numpy` for sample data.
- `frontend/nginx.conf` and `frontend/.dockerignore` had been lost in an earlier cleanup and were missing from the user's copy — **recreated**; the Docker build needs `nginx.conf`.

## Suggested next steps (in order)

1. `git init` + push to the user's GitHub (github.com/HasanZaidi1980) so there's version control.
2. Add a `pytest` suite for `data.py` + `scoring.py`, and FastAPI `TestClient` tests for the endpoints.
3. Validate scoring against the real IPEDS dataset; make weights configurable and documented.
4. Swap in real IPEDS data; sanity-check rankings.
5. Only then attempt GCP deploy per `DEPLOYMENT.md` (remember the teardown step to avoid billing).

## Guardrails

- Keep the API contract in `observed-api-contract.md` stable (frontend depends on it).
- **Only Claude Code commits** — Claude Cowork has equal access to files and the console but never runs git write commands (see "Who works on this" above).
- `ANTHROPIC_API_KEY` from env / K8s secret only — never commit or log it.
- Don't commit real IPEDS data or the generated vector index (already git-ignored).

## File map
```
merit-aid-app/
  HANDOFF.md              ← this file (current status)
  PROJECT_BRIEF.md        full architecture, metrics, task list — read next
  README.md               how to run
  ANALYSIS.md             what the reference app is + cloud/hosting findings
  observed-api-contract.md  exact endpoints + 23-field schema
  DEPLOYMENT.md           GCP deploy + teardown
  docker-compose.yml
  backend/   app/{config,data,scoring,rag,main}.py  scripts/  requirements.txt  Dockerfile
  frontend/  src/{App.jsx,Plot.jsx,api.js,main.jsx,styles.css}  nginx.conf  Dockerfile
  deploy/    terraform/*.tf   k8s/*.yaml
```
