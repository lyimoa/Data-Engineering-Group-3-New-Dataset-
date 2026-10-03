# Metrics Definitions

Every number shown on the Lab 7 dashboard is defined here once, computed in
`ingestion/build_marts.py`, and never recalculated separately inside the
dashboard or any other consumer.

---

## total_admissions

- **Formula:** `COUNT(*)` of rows in the clean `admissions` table
- **Grain:** per admission date (one value per day)
- **Filters:** none beyond what `ingest.py`'s 5 quality checks already excluded —
  rows that failed validation or were exact duplicates (see Lab 6) never reach
  `admissions`, so they are never counted here
- **Owner:** Group 3 · v1.0
- **Source table:** `marts_admissions_daily`

## avg_billing_amount

- **Formula:** `AVG(Billing Amount)`, rounded to 2 decimal places
- **Grain:** per admission date (one value per day)
- **Filters:** same as above — computed only over clean, quarantine-checked rows;
  the 108 negative-billing rows quarantined in Lab 6 are excluded by construction
- **Owner:** Group 3 · v1.0
- **Source table:** `marts_admissions_daily`

---

## Freshness

- **Label shown:** "Data as of `<refreshed_at>`"
- **Computed from:** `MAX(refreshed_at)` in `marts_admissions_daily`, set automatically
  by `build_marts.py` every time it runs — never typed by hand
- **Promise:** refreshed on demand by running `build_marts.py`
- **Staleness rule:** if `refreshed_at` is more than 24 hours old, the dashboard
  shows a visible warning instead of presenting the data as current
