# FORMULAS.md — every derived number, and why it is derived that way

The system of record for the app's arithmetic. `CLAUDE.md` requires this file to be
updated in the same change that alters a formula.

Survey years are mixed by necessity and are stated per formula. **SFA is 2021-22**
(net price, grant aid); **IC, ADM, DRVADM, DRVGR are 2022-23**. Where a formula
combines them, the mismatch is called out.

---

## 1. The universe

```
HD2022 filtered to ICLEVEL == 1 AND HDEGOFR1 >= 3      (4-year, degree-granting)
then dropna(TUITION2, IGRNT_A, NET_PRICE_MID)
= 1,907 colleges
```

`colleges_in_dataset = 1907`, `net_price_min = 2200`, `net_price_max = 63997`,
`sat_coverage = 985` reproduce the reference app exactly and are the project's
structural validation targets. They do not depend on any COA choice.

---

## 2. Net price — `NET_PRICE_MID`

```
NET_PRICE_MID = NPT442  coalesced with  NPIS442
```

**2021-22.** Average net price for full-time, first-time Title IV recipients in the
**$75,001–$110,000** income band.

The two variables carry an **identical dictionary title** and are mutually exclusive:

| variable | applies to | n |
|---|---|---|
| `NPT442` | private institutions | 1,181 |
| `NPIS442` | public institutions, **in-state** | 726 |

Reading `NPT442` alone silently drops every public university. This is the canonical
example of the `CLAUDE.md` §1 rule that a variable's title does not tell you what it
contains.

---

## 3. Cost of attendance — `COA`

```
COA = NET_PRICE_MID + BAND_GRANT

BAND_GRANT = GRN4A42  coalesced with  GIS4A42
```

**2021-22**, matching net price. `GRN4A42` is private, `GIS4A42` is public in-state —
the same 1,181 / 726 split as the net-price pair, never both populated, and neither
ever appears without its matching net-price column (verified on all 1,907).

### Why this, and not a hand-summed sticker

IPEDS *defines* net price as

> total cost of attendance − average grant and scholarship aid

for one cohort. `GIS4A42` / `GRN4A42` **are** that published average grant, for that
same cohort, band and year. So adding them back recovers the exact basket the net
price was computed against. COA and net price are comparable by construction rather
than by assumption, which is what `DISCOUNT` and `NET_PRICE_RATIO` require.

The dictionary spells the basket out: tuition and required fees (for publics, the
*lower of in-district or in-state*), books and supplies, and a **weighted average** of
room/board and other expenses across the three living arrangements, weighted by
student counts, with "unknown" excluded.

**Verified two independent ways on the real 1,907:**

1. Against a from-scratch reconstruction of that weighted formula, built from the
   2021-22 charge columns (`CHG*AY2`) and the living-arrangement counts
   (`GIS4ON2`/`GIS4WF2`/`GIS4OF2`, `GRN4*` for privates):
   **1,543 of 1,544 agree to under \$1; median difference \$0.**
2. No college can land below its own net price. The previous hand-summed COA put
   **459 of 1,907 (24%) at a negative discount**, which is impossible by definition.

### What was wrong before

```
OLD:  COA = TUITION2 + CHG4AY3 + CHG5AY3
```

Three defects: `TUITION2` is tuition with **no required fees**; on-campus **other
expenses** (`CHG6AY3`) were omitted entirely; and 2022-23 charges were measured
against a 2021-22 net price.

### Candidates considered, measured on the real 1,907

| COA candidate | coverage | median aid share | negative discounts |
|---|---|---|---|
| `TUITION2+CHG4AY3+CHG5AY3` (old) | 1907 | 0.3430 | **459** |
| + `FEE2` | 1907 | 0.3255 | 363 |
| + `FEE2` + `CHG6AY3` | 1907 | 0.2951 | 274 |
| `CINSON` (DRVIC2022) | 1606 | 0.3090 | 5 |
| `CINSON` → `CINSOFF` fallback | 1907 | 0.2686 | 9 |
| weighted basket, reconstructed | 1535 | 0.3278 | 2 |
| **`NET_PRICE_MID + BAND_GRANT`** | **1907** | **0.2942** | **0** |

The published identity is the only candidate with full coverage **and** no impossible
values, and it is the only one that is year-matched to net price.

### Accepted trade-offs

- COA is a **cohort-weighted cost basket, not an on-campus published sticker.** It runs
  about **6% under `CINSON`** (median ratio 0.942, p10 0.817, p90 0.979) because IPEDS
  weights room/board across living arrangements, including students living with family.
  The UI calls it "Total Cost of Attendance" rather than "Total Sticker" for this reason.
- **`DISCOUNT` is now identically `BAND_GRANT`** (see §4). That is not circularity —
  it is the published figure the old subtraction was trying to estimate, and was
  getting wrong often enough to go negative on a quarter of the dataset.
- **One college has `COA < TUITION2`** (Mount Carmel College of Nursing). Left as
  reported rather than patched.

---

## 4. Money metrics

```
DISCOUNT        = COA - NET_PRICE_MID        ( == BAND_GRANT, exactly )
NET_PRICE_RATIO = NET_PRICE_MID / COA        ( bounded (0, 1] )
AID_SHARE       = IGRNT_A / COA
MGI             = IGRNT_A / TUITION2
```

`AID_SHARE` and `MGI` are **not** circular: `IGRNT_A` averages a different cohort
(all aided undergraduates, full year) than `BAND_GRANT` (the $75k–$110k Title IV band).

That cohort difference is also why `AID_SHARE` can exceed 1 — the average institutional
grant can exceed the whole cost of attendance at a college whose aided students are
unlike its mid-income ones. True of **one** college in 2022-23; flagged
`aid_share_above_coa` rather than left to top the ranking.

**`MGI` is a misnomer inherited from the original brief.** `IGRNT_A` conflates
need-based and merit aid and IPEDS publishes no split, so nothing user-facing calls it
"merit" — the UI labels it "Grant ÷ Tuition". See `merit_policy.py`.

---

## 5. Value Score

```
VALUE_SCORE = ( affordability * w_aff
              + graduation    * w_grad
              + generosity    * w_gen ) * 100          weights normalised to sum to 1

affordability = pct_rank(NET_PRICE_MID, higher_is_better=False)
graduation    = pct_rank(GRAD_RATE,     higher_is_better=True)
generosity    = pct_rank(AID_SHARE,     higher_is_better=True)
```

Weights live in `config.VALUE_WEIGHTS`, are overridable by environment variable
(`WEIGHT_AFFORDABILITY`, `WEIGHT_GRADUATION`, `WEIGHT_GENEROSITY`), and are reported
through `/api/meta` as `value_weights`. Default is **equal thirds**.

Normalising means a deployment can set `2/1/1` without also dividing by 4, and that no
setting can push scores off the 0–100 scale.

### Distribution on the real data (n = 1,727 scoreable)

```
p0 2.5   p5 25.1   p25 40.8   p50 50.0   p75 60.2   p95 74.3   p100 96.1
mean 50.27   sd 15.37   skew -0.020
```

Near-symmetric and centred on 50, as a mean of percentile ranks should be.

### Equal weighting is defensible — but it is not neutral

Each component contributes an almost identical share of summed variance (32.1% /
34.9% / 33.0%), because percentile ranks are uniform by construction. **Influence on
the final ordering is very unequal:**

| component | Spearman vs final score |
|---|---|
| affordability | **+0.107** |
| graduation | +0.667 |
| generosity | **+0.803** |

The cause is the correlation structure, not the weights:

```
affordability vs graduation   -0.447
affordability vs generosity   -0.234
graduation    vs generosity   +0.510
```

Affordability pulls *against* the other two, so it largely cancels; graduation and
generosity reinforce each other and drive the ranking. **This is pre-existing, not a
consequence of the COA change** — under the old COA the same figures were +0.152 /
+0.615 / +0.797.

Arguably this is the tool working: the ranking is not simply "cheap colleges", it is
cheap colleges that also graduate students and give aid. But a user who assumes equal
weight means equal influence is mistaken, so it is stated here and the weights are
configurable.

### Sensitivity of the top 20

| scenario | kept of 20 | median rank shift |
|---|---|---|
| equal thirds (default) | 20 | 0 |
| affordability ×2 | 15 | 1 |
| graduation ×2 | 18 | 1 |
| generosity ×2 | 18 | 1 |
| affordability ×0.5 | 17 | 1 |
| graduation ×0.5 | 17 | 0 |
| generosity ×0.5 | 17 | 0 |
| affordability only | **2** | 15 |
| graduation only | 10 | 5 |
| generosity only | 12 | 8 |

Robust to moderate reweighting, and genuinely a blend — single-component scoring
produces a substantially different shortlist, so no one component is the ranking in
disguise.

---

## 6. Missing data — why nothing is imputed

A college missing any Value Score component is **excluded**, not imputed.
`rank_and_filter()` drops rows with a null `VALUE_SCORE`.

Two alternatives were considered and **rejected**:

- **Partial averaging** (scoring on whichever components are present) rewards
  non-reporting, because the absent field is almost always the graduation rate that
  would have pulled a cheap, generous college down.
- **Median imputation** (what the original pipeline did via `fillna`) credits a
  college with outcomes it never reported, letting it outrank one that reported
  honestly.

`NaN` is therefore allowed to propagate through the Value Score sum on purpose.

---

## 7. Rate scaling

```
ADMISSIONS_RATE  declared "percent"  (DRVADM2022.DVADM01)  -> / 100
GRAD_RATE        declared "percent"  (DRVGR2022.GBA4RTT)   -> / 100
```

Declared in `config.RATE_COLUMNS` from each variable's dictionary entry — DVADM01's
reads "Ratios are converted to percentages and rounded to the nearest whole number".
`load_rates()` converts, then **verifies the result lands in 0..1** and raises if not.

This replaced a `max > 1.5` heuristic. The heuristic fired correctly on the full
2022-23 universe (both columns observe min 0.00, max 100.00), but it read the data to
decide what the data meant: on a filtered or small subset where every rate happened to
be small it would leave percentages unscaled and make every rate 100× too low, with no
error. 7.4% of `GBA4RTT` values are already ≤ 1.5.

---

## 8. Flags

`RISK_FLAGS` are scoring-relevant and `exclude_flagged` drops them:

| flag | meaning |
|---|---|
| `no_grad_rate` | no graduation rate — Value Score is unscoreable |
| `aid_share_above_coa` | average grant exceeds total cost; generosity unusable |

`incomplete_coa` was **retired** by the COA change: COA no longer has partially
present components, so the flag could never fire again. `flagged_count` fell from 379
to 181 as a result.

`DATA_GAPS` are display-only and never remove a college: `no_sat`, `no_admit_rate`.

---

## 9. Legacy

```
COMPOSITE_LEGACY = (MGI + GRAD_RATE) / NET_PRICE_RATIO
```

The original assignment's formula. Retained for comparison only; nothing ranks on it.
