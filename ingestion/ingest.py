import pandas as pd
import os
import sys
import hashlib
import duckdb
from datetime import datetime

SOURCE_PATH = "source_data/healthcare_dataset.csv"
LOG_PATH = "logs/ingestion_log.txt"
DB_PATH = "db/healthcare_ingested.duckdb"

EXPECTED_COLUMNS = [
    "Name", "Age", "Gender", "Blood Type", "Medical Condition",
    "Date of Admission", "Doctor", "Hospital", "Insurance Provider",
    "Billing Amount", "Room Number", "Admission Type",
    "Discharge Date", "Medication", "Test Results"
]

def log(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")

def fetch_source(path):
    """Step 1: Fetch defensively — check the file actually exists before touching it."""
    if not os.path.exists(path):
        log(f"ERROR: source file not found at {path}")
        sys.exit(1)
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log(f"ERROR: failed to read source file — {e}")
        sys.exit(1)
    log(f"Fetched source file: {path} ({len(df)} rows read)")
    return df

def validate(df):
    """Step 2: Validate at the door — check shape and sanity before loading."""
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        log(f"ERROR: missing expected columns: {missing_cols}")
        sys.exit(1)

    initial_count = len(df)

    # Reject rows with negative billing amounts (data quality rule from Lab 1)
    bad_billing = df[df["Billing Amount"] < 0]
    df = df[df["Billing Amount"] >= 0]

    rejected_count = initial_count - len(df)
    log(f"Validated: {len(df)} rows passed, {rejected_count} rows rejected (negative billing amount)")

    return df

def add_row_hash(df):
    """Stable unique key: hash of every column's value, per row."""
    def hash_row(row):
        row_str = "|".join(str(v) for v in row.values)
        return hashlib.md5(row_str.encode()).hexdigest()
    df = df.copy()
    df["row_hash"] = df.apply(hash_row, axis=1)
    return df

def load_idempotent(df):
    """Load into DuckDB via staging table, then INSERT OR REPLACE into target keyed on row_hash."""
    con = duckdb.connect(DB_PATH)

    con.execute("""
        CREATE TABLE IF NOT EXISTS admissions (
            row_hash VARCHAR PRIMARY KEY,
            Name VARCHAR, Age INTEGER, Gender VARCHAR, "Blood Type" VARCHAR,
            "Medical Condition" VARCHAR, "Date of Admission" DATE, Doctor VARCHAR,
            Hospital VARCHAR, "Insurance Provider" VARCHAR, "Billing Amount" DOUBLE,
            "Room Number" INTEGER, "Admission Type" VARCHAR, "Discharge Date" DATE,
            Medication VARCHAR, "Test Results" VARCHAR
        )
    """)

    before_count = con.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

    con.execute("CREATE OR REPLACE TEMP TABLE staging AS SELECT * FROM df")

    con.execute("""
        INSERT OR REPLACE INTO admissions
        SELECT
            row_hash, Name, Age, Gender, "Blood Type", "Medical Condition",
            "Date of Admission", Doctor, Hospital, "Insurance Provider",
            "Billing Amount", "Room Number", "Admission Type", "Discharge Date",
            Medication, "Test Results"
        FROM staging
    """)

    after_count = con.execute("SELECT COUNT(*) FROM admissions").fetchone()[0]

    log(f"Loaded idempotently: {before_count} rows before, {after_count} rows after (source had {len(df)} valid rows)")
    con.close()
    return after_count

if __name__ == "__main__":
    df = fetch_source(SOURCE_PATH)
    df = validate(df)
    df = add_row_hash(df)
    final_count = load_idempotent(df)
    log(f"Ingestion run complete. Final table row count: {final_count}")