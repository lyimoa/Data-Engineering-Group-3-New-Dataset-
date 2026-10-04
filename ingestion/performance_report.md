# Lab 9 — Performance Report: Profile, Fix, Prove

## 1. The complaint, and why we didn't trust it

Before this lab, our working assumption — shaped by the unit's own worked example (CSV re-parsing) — was that reading `healthcare_dataset.csv` would be the pipeline's bottleneck. Unit 9's core rule is **measure first**, so instead of acting on that assumption, we timed every real, runnable step of the pipeline three separate times (to rule out one-off noise, per the unit's warning against "benchmarking once").

## 2. Profiling table (average of 3 runs per phase)

| Step | Before (avg) | After (avg) | Change |
|---|---|---|---|
| `fetch_source` (read CSV) | 0.144s | 0.148s | ~flat |
| `validate` (5 quality checks) | 0.058s | 0.059s | ~flat |
| `load_to_duckdb` (hash, dedupe, load) | 0.726s | 0.760s | ~flat |
| `build_marts` (Lab 7 mart) | 0.211s | 0.150s | ~flat (noise — see §4) |
| **`build_features`** (Lab 8 feature table) | **1.287s** | **1.134s** | **−0.153s** |

**Our assumption was wrong.** `fetch_source` was never the bottleneck — it was consistently the second-fastest step in every run. The step that actually dominated, in all three baseline runs, was `build_features.py`, at roughly double the next-slowest step.

## 3. The fix

`build_features.py` computed each patient's age bracket with:

```python
df["age_group"] = df["Age"].apply(age_group)
```

`.apply()` calls a plain Python function once per row — 54,860 individual calls for this dataset, each paying pandas' per-call overhead on top. We replaced it with a single vectorized operation:

```python
df["age_group"] = pd.cut(
    df["Age"], bins=[-1, 17, 64, 200], labels=["Child", "Adult", "Senior"]
).astype(str)
```

This is a **query/processing rewrite** — one of the four improvement types this unit names (format, partition, index, query rewrite) — applied to pandas code rather than SQL: the same bucketing logic, computed on the whole column at once instead of row by row.

## 4. Result, honestly reported

`build_features.py` dropped from an average of 1.287s to 1.134s — a real, reproducible **−0.153s (≈12% faster)**, with every one of the three "after" runs faster than every one of the three "before" runs. This is a modest win, not a dramatic one: most of this step's time is Python/library startup overhead (importing pandas, duckdb, connecting to the database), not the loop itself, so vectorizing one column was never going to produce a 10× speedup here. We report it as what it is.

**A note on percentages:** `build_marts` shows a −28.9% change despite never being touched. Its absolute time is tiny (~0.15–0.27s), so ordinary system noise (background CPU load, disk cache state) swings it by a large-looking percentage even with no code change. This is exactly why we judge an improvement by (a) whether it lands on the step we deliberately changed, and (b) whether it holds consistently across repeated runs — not by percentage size alone.

## 5. Why this matters

Had we skipped profiling and "optimised" the CSV read (our original guess), we would have spent effort on a step that was already fast — slide 12's "optimising the 1% step" mistake — while the real, dominant cost sat untouched. Measuring first redirected the fix to where it actually mattered.

## 6. Artifacts

- `profile_pipeline.py` — times every real pipeline step, writes results to `performance_results.csv`
- `performance_results.csv` — raw timing data (3 before runs, 3 after runs)
- `performance_dashboard.py` — Streamlit dashboard visualizing the before/after comparison
- `build_features.py` — the actual file changed (vectorized `age_group` computation)

**Run it (from the `ingestion/` folder):**
```bash
python3 profile_pipeline.py before   # repeat 3x before any change
python3 profile_pipeline.py after    # repeat 3x after the fix
streamlit run performance_dashboard.py
```
