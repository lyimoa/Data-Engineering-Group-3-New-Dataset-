# Split Strategy

Decided before any modeling, per Lab 8's requirement.

## Decision: time-based split, not random, not group-based

**Why time-based:** the deployed use case is predicting billing cost for
admissions that have not happened yet. A random shuffle would let future
admissions (e.g. 2024 billing patterns, inflation, insurance changes) help
train a model tested on past admissions (e.g. 2019) — backwards, and not
representative of how the model will actually be used. Any time-ordered
dataset (sensors, sales, health records — this one included) should be
split by time, never at random, per Unit 8.

## Split boundaries (from `build_features.py`, run on 54,860 clean rows)

| Split | Rows | Date range ends |
|---|---|---|
| Train | 38,402 (70%) | 2022-11-04 |
| Validate | 8,230 (15%) | 2023-08-05 |
| Test | 8,228 (15%) | most recent dates, touched once |

The test set is touched exactly once, at the very end, to report the honest
number — never peeked at during development.

## Why not group-based (and the residual risk we're accepting)

Group-based splitting (holding out entire doctors/hospitals/patients) matters
most when an entity repeats often enough in the data for a model to
memorize it rather than learn a general pattern — the flood-sensor-station
case from the lecture. We checked this empirically rather than assuming it,
using Lab 2's cardinality numbers:

| Entity | Distinct values | Rows | Avg. repeats per entity |
|---|---|---|---|
| Doctor | 40,341 | 55,500 | ~1.4 |
| Hospital | 39,876 | 55,500 | ~1.4 |
| Name (patient) | 49,992 | 55,500 | ~1.1 |

Each entity appears only ~1–1.4 times on average — near-unique, unlike a
sensor station reporting thousands of readings. This makes the specific
risk group-splitting defends against structurally small here.

**Residual limitation, stated honestly:** because the split is time-based
only, it remains possible for the same Doctor or Hospital to appear in both
train and test. Given the near-uniqueness shown above, we judge this risk
low, but it is not zero, and a stricter group-aware split would be the
next refinement if this model were headed toward real deployment rather
than a coursework exercise.
