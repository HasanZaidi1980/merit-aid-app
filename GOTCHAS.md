# Environment Gotchas — Merit Aid App

Things that have actually broken this project, and the fix. Check here before
debugging a setup problem from scratch.

Local machine: **Windows**, project at `C:\Users\amatu\Downloads\merit-aid-app`.

---

## Windows / PowerShell

**`&&` is not a valid statement separator.**
The installed PowerShell predates `&&` support, so chained commands fail with
`The token '&&' is not a valid statement separator in this version`.

Run them one per line:
```powershell
cd backend
pip install pandas numpy
python scripts/make_sample_data.py
cd ..
docker compose up --build
```
(`;` also works as a separator, but it ignores failures — one-per-line is safer.)

---

## Python versions

**Local Python is 3.13; the project targets 3.12.**

`pip install -r requirements.txt` fails locally on **scikit-learn** — there's no
prebuilt wheel for 3.13 against the pinned version, so pip tries to compile from
source and dies in ninja/MSVC.

You don't need the full install locally. Docker builds on `python:3.12-slim`, where
wheels exist. Locally you only need enough to generate sample data:
```powershell
pip install pandas numpy
python scripts/make_sample_data.py
```

**`backend/myenv/` is a Python 3.13 venv** left in the project. It's gitignored, so
harmless to the repo — but don't run the backend from it. Use Docker, or make a 3.12
venv if you want to run uvicorn directly.

---

## Docker

**Docker Desktop must be running before any `docker` command.**
Otherwise:
```
failed to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine
```
That is not a project error — open Docker Desktop, wait for the whale icon to report
running (~30s), then retry.

**`frontend/nginx.conf` is required by the frontend image.** It has gone missing once
(lost in a cleanup) and the build failed with:
```
COPY nginx.conf /etc/nginx/conf.d/default.conf: "/nginx.conf": not found
```
If you see that, the file is absent — recreate it. It serves the built SPA and proxies
`/api/` to `http://backend:8000`. `frontend/.dockerignore` went missing the same way.

**The large-bundle warning on build is expected** — Plotly is ~4.8 MB minified. Not an
error; cosmetic only.

**`docker compose up --build` is for local development, not production.** It builds the
same images you'd deploy, which makes it a good rehearsal, but it runs only on this
machine with no load balancer or scaling. Production is the Terraform + GKE path in
`DEPLOYMENT.md`.

---

## Ports

| Service | URL |
|---|---|
| Frontend (Docker) | http://localhost:8080 |
| Backend API | http://localhost:8000 |
| Frontend (Vite dev) | http://localhost:5173 |

In Docker the frontend proxies `/api` to the backend container by service name
(`backend:8000`). In Vite dev mode the proxy is configured in `vite.config.js`. Either
way the browser only ever calls same-origin `/api/*` — don't hard-code `localhost:8000`
in frontend code.

---

## Data

**The 8 IPEDS filenames are exact.** Drop them in `backend/data/`:
```
HD2022.csv  SFA2122_P1.csv  SFA2122_P2.csv  IC2022_AY.csv
ADM2022.csv  DRVADM2022.csv  DRVGR2022.csv  IC2022Mission.csv
```
A missing file raises a `FileNotFoundError` naming the file — that error means a name
mismatch, not corrupt data.

**`build_dataset()` is `lru_cache`d.** The dataset loads once per process, so swapping
CSVs has **no effect until the backend restarts.** If your numbers don't change after
replacing the data, that's why.

**Sample vs real data.** `scripts/make_sample_data.py` writes 300 synthetic colleges so
the app runs without the real dataset. Sample data will produce plausible-looking but
meaningless rankings — check which one you're on before drawing any conclusion from the
output. Real files overwrite the samples (same names).

---

## AI / RAG feature

**It runs without an API key.** `/api/rag/query` returns the retrieved mission passages
with a note instead of a synthesized answer. Set `ANTHROPIC_API_KEY` (in `.env` locally,
Secret Manager in GCP) to get Claude-generated answers.

**Retrieval silently falls back to TF-IDF** if `sentence-transformers` isn't installed
(it's commented out in `requirements.txt` because it pulls in torch). The response's
`mode` field reports which path ran — `sentence-transformers` or `tfidf-fallback`.
Retrieval quality differs noticeably, so check `mode` before judging answer quality.

**The index is built at startup** and persisted to `INDEX_DIR`. `/api/rag/status`
reports `index_ready` and `api_key_set`.

---

## Secrets & ignored paths

Never commit or log: `.env`, `backend/data/`, `backend/index/`, `backend/myenv/`,
`frontend/node_modules/`. All are already in `.gitignore` — keep it that way.
`ANTHROPIC_API_KEY` comes from the environment or a Kubernetes secret, never source.

---

## Git

**Only Claude Code commits.** Claude Cowork has equal file and console access but runs
no git write commands, and Claude Code owns `.gitignore`, hooks, and CI config. See
"Who works on this" in `HANDOFF.md`.

As of this writing the project is **not yet a git repo** — `git init` and the push to
github.com/HasanZaidi1980 are still pending.

---

## Cloud (not yet exercised)

Nothing has been deployed yet, so none of the GCP steps are battle-tested. Two things
to remember when you get there:

- **GKE plus a load balancer bills continuously.** Run the teardown in `DEPLOYMENT.md`
  (`kubectl delete -f deploy/k8s/` then `terraform destroy`) when a demo is done.
- **Delete the load balancer before `terraform destroy`**, or the destroy can hang on
  resources the Ingress still holds.
