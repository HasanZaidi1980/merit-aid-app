# CLAUDE.md — working rules for this repo

Applies to **both** Claude Code and Claude Cowork. Read before any analysis or code change.

---

## 1. Evidence, not assumption

**Every factual claim about the data must come from reading the data or its dictionary.**
No claim about a column, a value, a distribution, a scale, or a coverage rate is acceptable
on the basis of its name, prior experience with IPEDS, or what a doc in this repo says.

Before asserting anything about a column:

- Read the actual header: `head -1 backend/data/<FILE>.csv | tr ',' '\n' | grep ...`
- Read its definition in the IPEDS dictionary (`*_Dict.zip` → `varlist` / `Description`
  sheets). The `Description` sheet carries the methodology text; the `varTitle` alone is
  often ambiguous. Two variables can share an identical title and mean different things —
  `NPT442` and `NPIS442` do exactly that.
- Compute the value. Report real numbers: counts, medians, ranges, null coverage.

Prefer an experiment to an argument. When choosing between options, run each and compare
on a stated criterion. When a check contradicts a plan in `PROJECT_STATE.md` or
`PROJECT_BRIEF.md`, the check wins — fix the doc and say what changed.

**Say "I verified X by Y" or "I have not verified this."** Never let an unverified
statement pass as established. Flag it instead.

### Checks that caught real defects here

Keep using these; they are cheap and they work.

- **Impossible values.** Net price can never exceed cost of attendance. 459 of 1,907
  colleges violated that, which exposed an understated COA.
- **Who is actually in the rows.** `NPT442` looked universal and covers private
  institutions only; reading it alone silently dropped all 726 public universities.
- **Reproduce a known number.** Matching `colleges_in_dataset`, `net_price_min/max` and
  `sat_coverage` exactly is what proved the load/clean/merge path correct.
- **A reference number is a fingerprint, not ground truth.** `median_aid_share = 0.3184`
  came from the reference app's own COA choice. Do not optimize toward a number whose
  derivation you have not verified.

---

## 2. Displayed data must be true to IPEDS

Anything the app shows a user must be traceable to the IPEDS source. The app's only value
is that its numbers are real; a speculative figure is worse than no figure.

- **Never impute, estimate, or fill a value to make a row displayable.** A college missing
  a Value Score component is excluded, not imputed. (`FORMULAS.md` §6 records why
  median-filling and partial averaging were both rejected.)
- **Never let a label overstate what the data supports.** `IGRNT_A` conflates merit and
  need-based aid and IPEDS publishes no split, so nothing user-facing calls it "merit".
- **A derived metric must be defined and auditable.** Formulas live in `FORMULAS.md`;
  update it in the same change that alters a formula.
- **Surface known limits rather than hiding them.** `RISK_FLAGS`, `DATA_GAPS` and
  `COMPONENTS_USED` exist for this. Extend them instead of quietly dropping or fudging.
- **Sample data must never be mistaken for real.** `make_sample_data.py` output is
  synthetic; any analysis or screenshot drawn from it must say so.
- **Known-untrue content is a bug.** The mission text currently shipped in
  `IC2022Mission.csv` is generated, not IPEDS — IPEDS stopped publishing mission
  statements after 2007. The RAG panel must not present it as real.

Record the survey year of every source. SFA is 2021-22; IC, ADM and the derived files are
2022-23. Mixing years is sometimes unavoidable — say so where it shows.

---

## 3. Who commits

**Only Claude Code runs git write commands** (`add`, `commit`, `push`, branch, merge,
rebase, conflict resolution). Claude Cowork has equal file and console access and edits
freely, then reports which files it touched for Claude Code to stage.

`main` is protected on GitHub: collaborators need a pull request, force-pushes and
deletions are blocked. The owner can still push directly, so this workflow is unaffected.

Announce a file before editing it so the two agents don't write to it in parallel, and
leave the tree in a committable state at the end of a turn.

---

## 4. Never commit

`.env`, `backend/data/`, `backend/index/`, virtualenvs (`myenv/`, `venv/`),
`node_modules/`, dataset zips. All are gitignored — keep it that way. The repo is
**public**: anything committed is visible permanently, including in history.
`ANTHROPIC_API_KEY` comes from the environment or a Kubernetes secret, never from source.

---

## 5. Orientation

| Doc | Holds |
|---|---|
| `PROJECT_STATE.md` | Current status, phases, risks. Update when a phase moves. |
| `PROJECT_BRIEF.md` | Architecture, metrics, open questions. |
| `FORMULAS.md` | Every formula, with resolved and open issues. |
| `observed-api-contract.md` | Endpoints and the row schema. Breaking it breaks the frontend. |
| `GOTCHAS.md` | Environment traps that have actually cost time here. |
| `HANDOFF.md` | Where things stand right now. |

Run `cd backend && pytest` before reporting a change complete.
