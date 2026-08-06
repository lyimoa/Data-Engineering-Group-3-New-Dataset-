# Group 3 — Data Engineering Lab Project

## About This Project

This repository contains the work of Group 3 for the Data Engineering course. Our goal across the labs is to take a raw, real-world dataset through the core stages of a data engineering workflow: identifying data quality problems, designing a proper database schema, loading real data into that schema, and running meaningful analytical queries against it.

## The Dataset

- **Source:** [Health Dataset](https://www.kaggle.com/datasets/prasad22/healthcare-dataset) (Kaggle)
- **File:** `healthcare_dataset.csv`
- **Domain:** Health

## Lab 1 — Data Problem Statement

Before touching schema design, we explored the raw dataset to identify what was broken. We found:

1. **534 duplicate admission records** — full-row duplicates that would inflate patient volume and room/bed usage counts in any downstream aggregation.
2. **Negative billing amounts** (minimum observed: -2,008.49, against a mean of ~25,539) — a hospital bill cannot be negative; this points to either a data entry error or an unlabeled refund/adjustment.
3. **Inconsistent name capitalization** in `Name` and `Doctor` (e.g. "Bobby JacksOn", "LesLie TErRy") — this breaks exact-match joins, groupings, and deduplication, and likely masks additional duplicate records beyond the 534 caught by exact row matching.

The full one-page Data Problem Statement is in this repo as `data_problem_statement_healthcare.pdf`.

## Lab 2 — Schema Design Decision

We chose a **deliberate hybrid** schema: normalized lookup tables for low-cardinality categorical columns, joined to one central fact table (`fact_admissions`) at the grain of "one hospital admission."

**Why not one big table?** Storing text values like `"UnitedHealthcare"` or `"Hypertension"` repeatedly across 55,500 rows wastes space and risks inconsistent spelling/casing over time — we saw exactly this problem with `Name`/`Doctor` capitalization in Lab 1. Splitting these into lookup tables means each value is stored once, referenced by a small integer key, and can be corrected or extended in a single place.

**How we decided what becomes a dimension:** We checked actual distinct-value counts across the full dataset first, rather than assuming. Six columns had small, fixed value sets:

| Column | Distinct Values |
|---|---|
| Gender | 2 |
| Admission Type | 3 |
| Test Results | 3 |
| Insurance Provider | 5 |
| Medical Condition | 6 |
| Blood Type | 8 |

These became lookup tables: `dim_gender`, `dim_blood_type`, `dim_medical_condition`, `dim_insurance_provider`, `dim_admission_type`, `dim_test_results`.

**What stayed in the fact table:** `Doctor` (40,341 distinct), `Hospital` (39,876 distinct), and `Name` (49,992 distinct) are all near-unique relative to 55,500 total rows — normalizing them would add join overhead without meaningfully reducing storage or improving consistency, since almost every value appears once or twice anyway. `Room Number` (400 distinct, clearly bounded/reused) was a borderline case, but since the dataset has no other room attributes (floor, ward, etc.) to hang off a `dim_room` table, we kept it as a plain integer in the fact table — flagged as a future dimension candidate if richer room data becomes available.

**Schema summary:**
- `fact_admissions` — one row per hospital admission (55,500 rows), holding measures (`billing_amount`), degenerate attributes (`patient_name`, `doctor`, `hospital`, `room_number`, `age`, dates, `medication`), and foreign keys into the six lookup tables
- `dim_gender`, `dim_blood_type`, `dim_medical_condition`, `dim_insurance_provider`, `dim_admission_type`, `dim_test_results` — small reference tables with surrogate integer keys

All foreign key joins were verified to preserve the full row count (55,500 in `raw_admissions` → 55,500 in `fact_admissions`), confirming no category value was missed by a lookup table.

**Sample query:** We ran an analytical query grouping admission count and billing totals by medical condition and insurance provider, directly supporting the cost-planning and billing-accuracy decisions identified in our Data Problem Statement. Notably, average billing came out fairly uniform (~$25,000–26,000) across all conditions and insurers, suggesting the billing figures in this dataset may be synthetically generated rather than reflecting real-world cost variation — worth flagging as an additional data quality observation.

The SQL schema and queries are in this repo as the Lab 2 Colab notebook / SQL file.

## Team
- Allen L. Lyimo
- Asina Mchomvu
- Frank Mtimbili
- Claverfred Mhidze
- Kelvin Mwanga
