# Formulas & Scoring — Merit Aid App

The definitive reference for every number the app computes. All of it lives in
`backend/app/scoring.py` (metrics + ranking) and `backend/app/data.py` (inputs).
If you change a formula, update this file in the same turn.

> **Status:** these formulas are a *reconstruction* of the reference app's described
> behavior, not a verified copy of an original implementation. They are internally
> consistent and defensible, but "matches the original" is unproven. See
> §6 for the specific things still open.

---

## 1. Inputs

| Column | Meaning | Source file |
|---|---|---|
| `TUITION2` | Tuition sticker (in-state/published) | IC2022_AY.csv |
| `CHG4AY3`, `CHG5AY3` | Room & board / other charge components | IC2022_AY.csv |
| `COA` | Total sticker (cost of attendance) — **derived**, see §2 | IC2022_AY.csv |
| `IGRNT_A` | Average institutional grant per student | SFA2122_P1.csv |
| `NET_PRICE_MID` | Net price, $75k–$110k income band (IPEDS `NPT442`) | SFA2122_P2.csv |
| `ADMISSIONS_RATE` | Admit rate (IPEDS `DVADM01`) | DRVADM2022.csv |
| `GRAD_RATE` | 4-year graduation rate (IPEDS `GBA4RTT`) | DRVGR2022.csv |
| `SATVR75`, `SATMT75` | SAT 75th percentile, verbal + math | ADM2022.csv |

**Cleaning applied first** (`data.py`):
- IPEDS missing sentinels `-1, -2, -3, -9` → `NaN`.
- Universe filter: `ICLEVEL == 1` **and** `HDEGOFR1 >= 3` (4-year, degree-granting).
- All 8 files joined on `UNITID` (left joins onto the directory table).
- Rows missing **any** of `TUITION2`, `IGRNT_A`, `NET_PRICE_MID` are dropped — no
  financial basis to analyze.
- `ADMISSIONS_RATE` and `GRAD_RATE` are divided by 100 **only if** the column max
  exceeds 1.5 (heuristic to detect percent-vs-fraction encoding). See §6.

---

## 2. COA (total sticker)

```
COA = TUITION2 + CHG4AY3 + CHG5AY3     # summed with min_count=1
COA = TUITION2                          # fallback if charge columns absent
COA_COMPLETE = COA is not NaN
```

`min_count=1` means the sum is non-NaN if *at least one* component exists — so a
college with tuition but no room/board figure gets a COA equal to tuition alone, and
is **not** flagged as incomplete. That understates its sticker and therefore
understates its Discount and Aid Share. See §6.

---

## 3. The metrics

All computed in `add_metrics()`.

### Discount
```
DISCOUNT = COA - NET_PRICE_MID
```
Dollars the sticker price overstates what a middle-income family actually pays.
Bigger = better deal. This is what the dumbbell chart draws.

### MGI — Merit Generosity Index
```
MGI = IGRNT_A / TUITION2
```
The original project's metric. Grant relative to **tuition only**.
Used by the `mgi_at_least_median` filter, not by Value Score.

### Aid Share
```
AID_SHARE = IGRNT_A / COA
```
Grant relative to the **full** sticker. The headline generosity measure, and the
generosity input to Value Score.

> Note the denominators differ: `MGI` divides by tuition, `AID_SHARE` by total COA.
> Both are reported; they are not interchangeable and `AID_SHARE` is always the
> smaller of the two when charge components exist.

### Net Price Ratio
```
NET_PRICE_RATIO = NET_PRICE_MID / COA
```
Fraction of sticker the family still pays. **Lower is better.**

---

## 4. Value Score (0–100) — the primary ranking metric

```
affordability = percentile_rank(NET_PRICE_MID, higher_is_better=False)
quality       = percentile_rank(GRAD_RATE,     higher_is_better=True)
generosity    = percentile_rank(AID_SHARE,     higher_is_better=True)

VALUE_SCORE = (affordability + quality + generosity) / 3 * 100
```

- `percentile_rank` is pandas `Series.rank(pct=True)`; for "lower is better" it
  returns `1 - rank`.
- Three components, **equal weight** (⅓ each). Weights are hard-coded, not configurable.
- **Scope:** percentiles are computed over the *entire cleaned dataset*, before any
  user filter is applied. So a Value Score of 90 means "top 10% of all 4-year
  colleges", not "top 10% of the colleges currently shown". This is deliberate —
  scores stay stable as the user moves the filters — but it surprises people.
- **A missing component makes the college unscoreable**, and `rank_and_filter()`
  excludes it (see §5, step 2). It is not imputed and not scored on the components
  that happen to be present — see "Resolved" in §6 for why.

### Legacy Score
```
COMPOSITE_LEGACY = (MGI + GRAD_RATE) / NET_PRICE_RATIO
```
The original assignment's composite, retained for comparison only. Never used for
ranking. Note it is **not** a faithful reproduction of the original: the original
divided by a tuition-based ratio, whereas `NET_PRICE_RATIO` here is COA-based.
Unbounded and heavily skewed — don't treat it as comparable to Value Score.

---

## 5. Filtering & ranking order

`rank_and_filter()` applies steps **in this order** — the order matters:

1. Drop rows missing `COA`, `NET_PRICE_MID`, or `IGRNT_A`.
2. Drop rows with no `VALUE_SCORE` (any of the three components missing). These are
   excluded unconditionally — independent of `exclude_flagged` — because an unscoreable
   college cannot be ranked honestly.
3. `NET_PRICE_MID <= max_net_price` (default 25000).
4. If `mgi_at_least_median`: keep `MGI >= median(MGI)`, where the median is taken over
   the **whole cleaned dataset**, so the threshold does not move when the user changes
   the other filters.
5. If `exclude_flagged`: keep only rows where `RISK_FLAGS == ""`.
6. Sort by `VALUE_SCORE` descending; assign `RANK` starting at 1.
7. Truncate to `top_n` (default 20).

**Defaults** (`config.DEFAULTS`, echoed by `/api/meta`):
`max_net_price=25000`, `mgi_at_least_median=True`, `top_n=20`, `exclude_flagged=True`.

### Data-quality bookkeeping
- `COMPONENTS_USED` — comma-separated list of which inputs were present for that row.
- `RISK_FLAGS` — any of `incomplete_coa`, `no_sat`, `no_grad_rate`, `no_admit_rate`.

`exclude_flagged=True` is strict: a college missing **only** its SAT figure is dropped
along with genuinely incomplete rows. That is a large share of the dataset.

---

## 6. Open issues / things to verify

### Resolved (2026-10-28)

- **Unscoreable colleges were ranked, not excluded.** `Series.add(other,
  fill_value=np.nan)` was a no-op, so a college missing `GRAD_RATE` scored `NaN` and
  sorted last silently. Now `rank_and_filter()` drops rows without a `VALUE_SCORE`
  outright (§5 step 2). Two alternatives were rejected deliberately:
  *partial averaging* (scoring on the components present) rewards non-reporting,
  because the missing field is almost always the graduation rate that would have
  pulled a cheap, generous school down; and *median imputation* (what the original
  pipeline did via `fillna`) credits a college with outcomes it never reported,
  letting it outrank one that reported honestly.
- **Median MGI was computed post-filter.** It now uses the whole cleaned dataset.
  The old behavior took the median of the net-price-filtered subset, which (a) moved
  the bar whenever the user changed the slider and (b) set it far above "more generous
  than typical", because low net price is largely *caused* by large grants. On a test
  fixture the post-filter median was 0.691 against a dataset median of 0.596.

### Still open

Ordered by how much they could distort results.

1. **`exclude_flagged` gates on fields that don't affect the score.** `RISK_FLAGS`
   includes `no_sat` and `no_admit_rate`, but neither feeds Value Score — they are
   display/chart dimensions only. The reference app reported 1352 of 1907 colleges
   flagged with SAT coverage of just 985, so the default view may be discarding most
   of the dataset for reasons with no bearing on the ranking, hiding genuinely
   good-value colleges. Suggested fix: split scoring-relevant flags
   (`incomplete_coa`) from cosmetic data gaps (`no_sat`, `no_admit_rate`) and have
   `exclude_flagged` consider only the former. **This changes the meaning of a field
   in the API contract, so it needs a decision before implementing.**

2. **`/api/meta` reports the wrong median for the filter it describes.** It exposes
   `median_aid_share` (grant ÷ COA) while the filter applies a median of `MGI`
   (grant ÷ tuition). The number available to the UI is not the threshold being
   applied. Either report `median_mgi` as well, or gate the filter on `AID_SHARE` so
   there is a single generosity concept.

3. **`min_count=1` on COA.** A college with tuition only gets `COA == TUITION2` and is
   not marked `incomplete_coa`, which inflates its apparent affordability and deflates
   its Aid Share. Consider requiring all components, or flagging partial COA.

4. **COA vs net price comparability.** `DISCOUNT` and `NET_PRICE_RATIO` assume `COA`
   and `NPT442` cover the same basket of costs. IPEDS net price is defined against
   *total* cost of attendance including allowances this COA doesn't reconstruct, so
   the two may not be apples-to-apples. Verify against IPEDS documentation.

5. **Percent-scaling heuristic.** Dividing by 100 only when `max > 1.5` is fragile: a
   real dataset where every rate happens to be ≤ 1.5 (or already fractional) would be
   mis-scaled with no error. Prefer an explicit per-column declaration.

6. **Equal weighting is an assertion, not a finding.** ⅓/⅓/⅓ was chosen because the
   reference app described equal weight. Whether that produces sensible rankings on
   the real IPEDS data is untested — check the Value Score distribution and each
   component's correlation with the final rank.

7. **Weights are not configurable.** Exposing them (and reporting them in
   `/api/meta`) would make the methodology auditable instead of implicit.

---

## 7. Where to change things

| Change | File |
|---|---|
| Any formula, the weights, the ranking order | `backend/app/scoring.py` |
| Inputs, cleaning, COA construction, scaling | `backend/app/data.py` |
| Default filter values | `backend/app/config.py` (`DEFAULTS`) |
| Fields exposed by the API | `backend/app/main.py` (`ROW_FIELDS`) |

Changing `ROW_FIELDS` or renaming a column is a **breaking API change** — the frontend
reads these names directly. See `observed-api-contract.md`.
