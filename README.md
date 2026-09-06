# Group 3 — Data Engineering Lab Project

## About This Project

This repository contains the work of Group 3 for the Data Engineering course. Our goal across the labs is to take a raw, real-world dataset through the core stages of a data engineering workflow: identifying data quality problems, designing a proper database schema, loading real data into that schema, and running meaningful analytical queries against it.

## The Dataset

- **Source:** [Health Dataset](https://www.kaggle.com/datasets/prasad22/healthcare-dataset) (Kaggle)
- **File:** `healthcare_dataset.csv`
- **Domain:** Health

## Lab 1 — Data Problem Statement

Before touching schema design, we explored the raw dataset to identify what was broken. We found:

1. **534 duplicate admission records** - full-row duplicates that would inflate patient volume and room/bed usage counts in any downstream aggregation.
2. **Negative billing amounts** (minimum observed: -2,008.49, against a mean of ~25,539) — a hospital bill cannot be negative; this points to either a data entry error or an unlabeled refund/adjustment.
3. **Inconsistent name capitalization** in `Name` and `Doctor` (e.g. "Bobby JacksOn", "LesLie TErRy") — this breaks exact-match joins, groupings, and deduplication, and likely masks additional duplicate records beyond the 534 caught by exact row matching.

The full one-page Data Problem Statement is in this repo as `data_problem_statement_healthcare.pdf`.

## Lab 2 — Schema Design Decision

We chose a **deliberate hybrid** schema: normalized lookup tables for low-cardinality categorical columns, joined to one central fact table (`fact_admissions`) at the grain of "one hospital admission."

**Why not one big table?** Storing text values like `"UnitedHealthcare"` or `"Hypertension"` repeatedly across 55,500 rows wastes space and risks inconsistent spelling/casing over time, we saw exactly this problem with `Name`/`Doctor` capitalization in Lab 1. Splitting these into lookup tables means each value is stored once, referenced by a small integer key, and can be corrected or extended in a single place.

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

**What stayed in the fact table:** `Doctor` (40,341 distinct), `Hospital` (39,876 distinct), and `Name` (49,992 distinct) are all near-unique relative to 55,500 total rows, normalizing them would add join overhead without meaningfully reducing storage or improving consistency, since almost every value appears once or twice anyway. `Room Number` (400 distinct, clearly bounded/reused) was a borderline case, but since the dataset has no other room attributes (floor, ward, etc.) to hang off a `dim_room` table, we kept it as a plain integer in the fact table flagged as a future dimension candidate if richer room data becomes available.

**Schema summary:**
- `fact_admissions` — one row per hospital admission (55,500 rows), holding measures (`billing_amount`), degenerate attributes (`patient_name`, `doctor`, `hospital`, `room_number`, `age`, dates, `medication`), and foreign keys into the six lookup tables
- `dim_gender`, `dim_blood_type`, `dim_medical_condition`, `dim_insurance_provider`, `dim_admission_type`, `dim_test_results` - small reference tables with surrogate integer keys

All foreign key joins were verified to preserve the full row count (55,500 in `raw_admissions` → 55,500 in `fact_admissions`), confirming no category value was missed by a lookup table.

**Sample query:** We ran an analytical query grouping admission count and billing totals by medical condition and insurance provider, directly supporting the cost-planning and billing-accuracy decisions identified in our Data Problem Statement. Notably, average billing came out fairly uniform (~$25,000–26,000) across all conditions and insurers, suggesting the billing figures in this dataset may be synthetically generated rather than reflecting real-world cost variation worth flagging as an additional data quality observation.

The SQL schema and queries are in this repo as the Lab 2 Colab notebook / SQL file.

## Lab 3 — Re-runnable Ingestion Script

The ingestion script fetches the healthcare CSV, validates it (rejects rows with negative billing amounts), and loads it idempotently into DuckDB using a row-hash primary key safe to re-run any number of times without creating duplicates.

**Run it (from the `ingestion/` folder):**
```bash
python3 ingest.py
```

**Proof of idempotency:** the script was run twice in succession. First run: 0 → 54,860 rows loaded (55,392 valid rows in, 532 exact-duplicate rows deduplicated via row-hash). Second run: 54,860 → 54,860 rows unchanged, confirming no duplicates are created on re-run. See `ingestion/logs/ingestion_log.txt` for the full run log.

## Lab 4 — Storage & Query Benchmark

Unit 4's core lesson is not to assume a dataset needs "big data" infrastructure — measure it. We benchmarked our own ~55,500-row healthcare admissions dataset against the three-question decision path from the lecture (fits in memory? fits on one disk? truly beyond one machine?) by running the same aggregate query three ways: pandas on CSV, PostgreSQL, and DuckDB on Parquet.

**Query benchmarked:** average billing amount and admission count, grouped by medical condition — a real query a hospital administrator or insurance analyst (our Lab 1 audience) would actually run.

**File size comparison:**

| Format | Size |
|---|---|
| CSV | 8,202.4 KB |
| Parquet | 2,755.6 KB |

Converting to Parquet alone shrank the file by roughly 3x, purely from columnar layout and compression — no data was changed.

**Query time comparison:**

| Tool | Cold run | Warm (repeated) run |
|---|---|---|
| pandas (CSV) | 0.0192 s | 0.0449 s |
| PostgreSQL | 0.0277 s | 0.0297 s |
| DuckDB (Parquet) | 0.2636 s | 0.0093 s |

DuckDB's first run was the slowest of the three, not the fastest as the lecture's illustrative numbers suggested. Investigating this: the 0.2636s cold run was a one-time cost from initializing the DuckDB engine and opening the Parquet file for the first time in the session — not the query itself. Rerunning the identical query afterward dropped to 0.0093s, faster than either pandas or PostgreSQL, while pandas and PostgreSQL stayed roughly stable across their own repeated runs. This is a direct, self-measured example of the unit's warning against "believing benchmarks you never ran" — the raw first number would have supported the wrong conclusion.

**Verdict:** We choose DuckDB with Parquet. Once warmed up, it was the fastest of all three tools tested, and its Parquet file is roughly 3x smaller than the raw CSV. Its one-time cold-start cost is a session-level engine initialization, not a repeated query cost, so it doesn't change the recommendation. DuckDB gives Postgres-level reliability with pandas-level simplicity and zero server setup — the right tool for this dataset now, and it scales better if the data grows later.

The benchmark notebook (data load, Postgres/Parquet setup, and all timed queries) is in this repo as the Lab 4 Colab notebook.

## Lab 5 — Cloud Data Engineering (BigQuery)

Unit 5's core lesson is that cloud platforms separate storage from compute, and bill on four "meters" (storage, compute, scanning, egress) — so we designed and built a cloud pipeline for our healthcare dataset to see this in practice, not just on paper.

**Setup:** We uploaded `healthcare_dataset.csv` into a BigQuery sandbox project (`lab-5-healthcare`, region `africa-south1`), creating a table `Admissions` (55,500 rows, 8.06 MB) inside dataset `healthcare_lab_5`.

**Sandbox query:** We ran an aggregate query — average billing amount by medical condition — which BigQuery estimated at 975.81 KB processed, confirming the "scanning" cost meter directly: even a tiny table has a real, visible cost to *read*, separate from the cost to *store*.

**Implemented pipeline (beyond the lab's minimum):** We rebuilt Lab 3's `ingest.py` validation and deduplication logic as a real, chained BigQuery pipeline (BigQuery Studio's Pipelines feature, built on Dataform), where each stage reads from the previous stage's output:

| Table | Rows | Logic |
|---|---|---|
| `Admissions` | 55,500 | Raw upload |
| `Admissions_validated` | 55,392 | Rejects `Billing Amount < 0` |
| `Admissions_deduped` | 54,860 | `SELECT DISTINCT` |

These numbers match Lab 3's `ingest.py` output exactly (55,392 valid rows in, 532 duplicates removed, 54,860 final).

**Does cleaning the data change the answer?** We re-ran the billing-by-condition query on both the raw `Admissions` table and the final `Admissions_deduped` table:

| Medical Condition | Raw avg billing | Cleaned avg billing | Change |
|---|---|---|---|
| Obesity | 25,805.97 | 25,859.22 | +53.25 |
| Diabetes | 25,638.41 | 25,714.33 | +75.92 |
| Asthma | 25,635.25 | 25,685.39 | +50.14 |
| Hypertension | 25,497.10 | 25,559.84 | +62.75 |
| Arthritis | 25,497.33 | 25,542.90 | +45.57 |
| Cancer | 25,161.79 | 25,205.92 | +44.13 |

Every average rose slightly after cleaning, and Hypertension and Arthritis swapped rank order — proof that validation isn't just a formality, it can change which condition ranks where.

**Sandbox limitations we hit (and documented, not worked around with billing):**
- **DML and scheduling are blocked** in sandbox mode — `INSERT` statements and scheduled pipeline runs both require billing to be enabled, so we used `CREATE TABLE ... AS SELECT` (DDL) instead.
- **Partition expiration is mandatory and capped at 60 days** in sandbox mode. Since our `Date of Admission` values span 2019–2024, partitioning by that column deleted every partition instantly. This is a genuine sandbox constraint, not a bug — production would need billing enabled to retain historical partitions.
- **Dataform's "Run task" button was unreliable** — it sometimes compiled and previewed correct results (e.g. 55,392 rows) without persisting the table, confirmed via `INFORMATION_SCHEMA.TABLES`. Running the same compiled SQL directly as a query reliably created the table; we believe this is specific to the sandbox tier combined with an institutional Google Workspace account.

**Serve layer — Streamlit dashboard:** Rather than Looker Studio, we built the "serve" stage as a Python/Streamlit dashboard (`Lab 5 - Dashboard/app.py`) querying `Admissions_deduped` directly via `google-cloud-bigquery` — reusing the same pandas skills from earlier labs. It includes sidebar filters (condition, gender, admission type, date range, age), KPI cards, multiple charts (bar, donut, line, box plot), a live pipeline row-count summary, and a CSV export.

The full one-page pipeline design writeup (with screenshots) is in this repo as `Lab5_Cloud_Pipeline_Design.pdf`. The dashboard code is in `Lab 5 - Dashboard/`.

## Team
- Allen L. Lyimo
- Asina Mchomvu
- Frank Mtimbili
- Claverfred Mhidze
- Kelvin Mwanga
