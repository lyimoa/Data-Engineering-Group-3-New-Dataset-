# Feature Table — `ml_features`

Built by `build_features.py` from the clean `admissions` table (post Lab 3/6
validation) in `db/healthcare_ingested.duckdb`. Target: `billing_amount`,
predicted at the moment of discharge.

## Engineered features

| Feature | Formula | Story | Knowable at prediction time? |
|---|---|---|---|
| `length_of_stay_days` | `Discharge Date − Date of Admission` | Longer stays cost more — the single strongest cost driver | ✅ Yes — discharge date is set once the stay ends, which is our prediction moment |
| `admission_month` | `MONTH(Date of Admission)` | Captures seasonal demand patterns (e.g. flu-season volume) | ✅ Yes — known at admission |
| `admission_dayofweek` | `DAYOFWEEK(Date of Admission)` | Weekday vs weekend admissions skew toward different care types | ✅ Yes — known at admission |
| `is_weekend_admission` | `admission_dayofweek IN (Sat, Sun)` | Weekend admissions often lean Emergency, which bills differently | ✅ Yes — derived from the above |
| `age_group` | `Age` bucketed into Child (<18) / Adult (18–64) / Senior (65+) | Age affects cost non-linearly; bucketing avoids a false straight-line assumption | ✅ Yes — known at admission |
| `is_chronic_condition` | `Medical Condition IN (Diabetes, Hypertension, Asthma)` | Chronic conditions often mean longer, costlier management | ✅ Yes — diagnosis is known at admission |

## Raw columns kept as features

| Column | Knowable at prediction time? |
|---|---|
| `Age`, `Gender`, `blood_type` | ✅ Yes — known at admission |
| `medical_condition` | ✅ Yes — diagnosis known at admission |
| `admission_type` | ✅ Yes — known at admission |
| `insurance_provider` | ✅ Yes — known at admission |

## Columns deliberately excluded

| Column | Reason excluded |
|---|---|
| `Name`, `Doctor`, `Hospital`, `Room Number` | Near-unique identifiers (see Lab 2 cardinality check) — add no generalizable signal, only memorization risk |
| `Discharge Date` (raw) | Only used indirectly, via `length_of_stay_days` — kept engineered, not raw, to avoid the model exploiting calendar artifacts in the raw date itself |
| `Test Results` | **Borderline.** Plausibly known before billing is finalized, but we could not confirm from the dataset's documentation exactly when during the stay it is recorded. Excluded under the leakage question's "if not sure, cut it" rule, rather than risk target leakage (an abnormal result could itself be a proxy for a costlier stay, uncomfortably close to "disguised copy of the answer") |

## Leakage audit — the one question asked of every column

> "Would this exact value have been knowable at the moment the prediction had to be made?"

Every feature above was checked against this question individually, not assumed.
No feature in the final table uses any value that originates after discharge
(the prediction moment), and `billing_amount` itself is excluded from the
feature set — it is the target, never an input.
