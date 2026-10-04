# Datasheet — Healthcare Admissions Dataset (as prepared for `ml_features`)

Following the "Datasheets for Datasets" framework (Gebru et al., 2021), adapted to the questions most relevant to this coursework pipeline.

## Motivation

**For what purpose was the dataset created?**
The underlying dataset was published on Kaggle as a general-purpose, synthetic healthcare admissions dataset for practicing data analysis and machine learning. We did not create the raw data; we built an ingestion, quality, governance, analytics, and ML-preparation pipeline on top of it for DSAI 6226 (Data Engineering and Analytics) coursework — not for any real clinical or business purpose.

**Who created the dataset, and who funded it?**
Raw data: Kaggle user `prasad22`, published publicly, no stated funding source. No real hospital, insurer, or health authority is the source. The `ml_features` table and all engineered columns were created by Group 3 (NM-AIST, DSAI 6226) as part of Labs 1–8 of this course.

## Composition

**What do the instances represent?**
Each row is one simulated hospital admission record (patient, admission dates, condition, insurer, doctor, hospital, billing amount, and — in `ml_features` — engineered features and a train/validate/test split label).

**How many instances, and is this all possible instances or a sample?**
55,500 raw rows → 54,860 rows after Lab 6 quality checks removed 108 negative-billing rows and 532 exact-duplicate rows → 54,860 rows carried into `ml_features`. This is the full Kaggle release, not a sample we drew ourselves.

**Does the data contain sensitive information?**
`Name` is direct personal data. `Age`, `Gender`, `Medical Condition`, `Hospital`, and `Doctor` are indirectly identifying. As established in our Lab 6 PDPA note, this is synthetic data, not real patient records, so no real individual's privacy is at risk — but we treat the fields with the same minimization discipline we would apply to real health data, and the design decisions below (e.g. excluding `Name` from `ml_features`) follow from that.

**Is the dataset synthetic, and how do we know?**
Strong evidence from Lab 2: average billing amount is nearly flat (~$25,000–26,000) across every medical condition and every insurance provider — a pattern inconsistent with real-world healthcare cost variation, where condition severity and treatment type drive large billing differences. We treat this as a known limitation, not a hidden one.

## Collection Process

**How was the raw data acquired?**
Downloaded once from Kaggle as `healthcare_dataset.csv`; no original collection instrument, consent process, or data-collection protocol is documented by the source, consistent with it being a synthetic/demonstration dataset.

**Over what timeframe?**
Admission dates in the file span from 2019 to 2024, but this reflects simulated date generation, not an actual multi-year clinical data collection effort.

## Preprocessing / Cleaning / Labeling (our pipeline's contribution)

This is the stage we are directly responsible for and can describe precisely, hop by hop:

1. **Ingestion (Lab 3):** row-hash primary key computed per row; idempotent `INSERT OR REPLACE` so re-running never duplicates.
2. **Quality checks (Lab 6):** 5 executable checks — non-negative billing, plausible age (0–120), discharge date not before admission date, required fields not null, no exact-duplicate rows. Failing rows are quarantined with a reason code, not silently dropped (see `quarantine` table and `test_quarantine.py` proof).
3. **Schema (Lab 2):** clean rows loaded into a star schema — `fact_admissions` plus six dimension tables for low-cardinality categorical columns.
4. **Feature engineering (Lab 8):** `build_features.py` derives `length_of_stay_days`, `admission_month`, `admission_dayofweek`, `is_weekend_admission`, `age_group`, and `is_chronic_condition` from the clean admissions table — see `features.md` for the full leakage audit of every column, including what was deliberately excluded (`Name`, `Doctor`, `Hospital`, `Room Number`, and the borderline `Test Results` column) and why.
5. **Split (Lab 8):** a single time-based 70/15/15 split by `admission_date`, computed once in `build_features.py` and stored as a `split` column — see `split_strategy.md` for the full reasoning and the stated residual limitation (possible Doctor/Hospital overlap across the time boundary, since those fields are not grouped on).

No manual labeling was performed anywhere in this pipeline — every derived column is a deterministic function of existing raw fields, which is itself part of why we were able to audit each one for leakage with a yes/no answer rather than a judgment call.

## Uses

**What other tasks could this dataset be used for?**
Within the scope of this course, the `ml_features` table could support a billing-amount regression or a length-of-stay prediction exercise. It is not validated for anything beyond that.

**Is there anything about the composition or collection process that might impact future uses?**
Yes — the flat billing-amount pattern (synthetic-data signal) means any model trained to predict `billing_amount` from this data will learn a dataset artifact, not a real cost driver, and that limitation must be disclosed with any such model rather than presented as a real-world finding.

**Should this dataset NOT be used for certain tasks?**
It must not be used, or presented, as a basis for real clinical, insurance, or hospital-operations decisions. It is coursework data for learning the pipeline, not a validated real-world source.

## Distribution

**Will the dataset be distributed to third parties?**
No. It lives only in this course repository (`github.com/lyimoa/Data-Engineering-Group-3-New-Dataset-`) for DSAI 6226 assessment and presentation purposes.

## Maintenance

**Who maintains the dataset, and how can errors be reported?**
Group 3 maintains the pipeline and all derived tables/files in this repository for the duration of the course. The raw CSV itself is maintained upstream by its Kaggle publisher and is not something we can correct; any issue we find in it (as in Lab 1 and Lab 6) is handled downstream, in our own quality checks, rather than by editing the source file.

## Known Gaps and Limitations (summary)

- Billing amounts are near-uniform across conditions/insurers — strong evidence of synthetic generation (Lab 2).
- `Doctor`, `Hospital`, and `Name` are near-unique (Doctor 40,341/55,500, Hospital 39,876/55,500, Name 49,992/55,500 distinct) — informative for schema design (Lab 2) and split strategy (Lab 8), but also meaning our time-based split does not guarantee zero Doctor/Hospital overlap between splits (stated explicitly in `split_strategy.md`).
- `Test Results` was excluded from `ml_features` as a borderline leakage risk rather than included — see `features.md` for the specific reasoning.
- This is coursework analysis of a synthetic dataset. No part of this project should be read as a claim about real healthcare costs, outcomes, or operations.
