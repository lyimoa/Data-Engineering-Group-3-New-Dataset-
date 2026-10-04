import os
import sys
import csv
import time
import subprocess
import pandas as pd
import duckdb

from ingest import (
    fetch_source, validate, add_row_hash, check_uniqueness,
    write_quarantine, load_idempotent_conn, SOURCE_PATH, DB_PATH
)

PARQUET_PATH = "source_data/healthcare_dataset.parquet"
RESULTS_PATH = "performance_results.csv"


def fetch_source_parquet(path):
    """Same role as ingest.py's fetch_source(), but reads the converted Parquet file."""
    if not os.path.exists(path):
        print(f"ERROR: parquet file not found at {path}. Run convert_to_parquet.py first.")
        sys.exit(1)
    df = pd.read_parquet(path)
    print(f"Fetched source file: {path} ({len(df)} rows read)")
    return df


def append_result(step, phase, duration):
    file_exists = os.path.exists(RESULTS_PATH)
    with open(RESULTS_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["step", "phase", "duration_seconds"])
        writer.writerow([step, phase, f"{duration:.4f}"])


def time_step(label, phase, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed = time.perf_counter() - start
    print(f"[{phase}] {label}: {elapsed:.3f}s")
    append_result(label, phase, elapsed)
    return result


def time_subprocess(label, phase, script):
    start = time.perf_counter()
    subprocess.run(["python3", script], check=True, capture_output=True)
    elapsed = time.perf_counter() - start
    print(f"[{phase}] {label}: {elapsed:.3f}s")
    append_result(label, phase, elapsed)


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else "before"
    print(f"=== Profiling pipeline — phase: {phase} ===\n")

    df = time_step("fetch_source", phase, fetch_source, SOURCE_PATH)

    clean, quarantined_validation = time_step("validate", phase, validate, df)

    def do_load():
        c = add_row_hash(clean)
        c, quarantined_dupes = check_uniqueness(c)
        con = duckdb.connect(DB_PATH)
        write_quarantine(con, quarantined_validation)
        write_quarantine(con, quarantined_dupes)
        load_idempotent_conn(con, c)
        con.close()

    time_step("load_to_duckdb", phase, do_load)
    time_subprocess("build_marts", phase, "build_marts.py")
    time_subprocess("build_features", phase, "build_features.py")

    print(f"\nDone. Results appended to {RESULTS_PATH} (phase={phase}).")
