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
    """Step 2: Validate at the door — check shape and sanity, quarantine failures with a reason."""
    missing_cols = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing_cols:
        log(f"ERROR: missing expected columns: {missing_cols}")
        sys.exit(1)

    df = df.copy()
    df["reject_reason"] = None

    # Check 1 (validity): billing amount must not be negative
    mask = df["Billing Amount"] < 0
    df.loc[mask & df["reject_reason"].isna(), "reject_reason"] = "negative_billing_amount"

    # Check 2 (validity): age must be a plausible human age
    mask = (df["Age"] < 0) | (df["Age"] > 120)
    df.loc[mask & df["reject_reason"].isna(), "reject_reason"] = "implausible_age"

    # Check 3 (validity): a patient can't be discharged before they were admitted
    admission = pd.to_datetime(df["Date of Admission"], errors="coerce")
    discharge = pd.to_datetime(df["Discharge Date"], errors="coerce")
    mask = discharge < admission
    df.loc[mask & df["reject_reason"].isna(), "reject_reason"] = "discharge_before_admission"

    # Check 4 (completeness): key fields must not be null/empty
    required_fields = ["Name", "Medical Condition", "Billing Amount"]
    mask = df[required_fields].isna().any(axis=1)
    df.loc[mask & df["reject_reason"].isna(), "reject_reason"] = "missing_required_field"

    quarantined = df[df["reject_reason"].notna()].copy()
    clean = df[df["reject_reason"].isna()].copy()

    log(f"Validated: {len(clean)} rows passed, {len(quarantined)} rows quarantined")
    for reason, count in quarantined["reject_reason"].value_counts().items():
        log(f"  - {reason}: {count} rows")

    return clean, quarantined

def add_row_hash(df):
    """Stable unique key: hash of every column's value, per row."""
    def hash_row(row):
        row_str = "|".join(str(v) for v in row.values)
        return hashlib.md5(row_str.encode()).hexdigest()
    df = df.copy()
    df["row_hash"] = df.apply(hash_row, axis=1)
    return df

def check_uniqueness(df):
    """Check 5 (uniqueness): flag exact duplicate rows, keep the first occurrence."""
    df = df.copy()
    is_dup = df.duplicated(subset="row_hash", keep="first")
    duplicates = df[is_dup].copy()
    duplicates["reject_reason"] = "duplicate_row"
    unique = df[~is_dup].copy()

    log(f"Uniqueness check: {len(unique)} unique rows, {len(duplicates)} duplicate rows quarantined")
    return unique, duplicates

def write_quarantine(con, quarantined_df):
    """Write quarantined rows to a holding table, tagged with why they failed."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS quarantine (
            row_hash VARCHAR,
            reject_reason VARCHAR,
            quarantined_at TIMESTAMP DEFAULT current_timestamp,
            Name VARCHAR, Age INTEGER, Gender VARCHAR, "Blood Type" VARCHAR,
            "Medical Condition" VARCHAR, "Date of Admission" VARCHAR, Doctor VARCHAR,
            Hospital VARCHAR, "Insurance Provider" VARCHAR, "Billing Amount" DOUBLE,
            "Room Number" INTEGER, "Admission Type" VARCHAR, "Discharge Date" VARCHAR,
            Medication VARCHAR, "Test Results" VARCHAR
        )
    """)

    if len(quarantined_df) == 0:
        log("No rows to quarantine.")
        return 0

    cols = ["row_hash", "reject_reason", "Name", "Age", "Gender", "Blood Type",
            "Medical Condition", "Date of Admission", "Doctor", "Hospital",
            "Insurance Provider", "Billing Amount", "Room Number", "Admission Type",
            "Discharge Date", "Medication", "Test Results"]

    to_insert = quarantined_df.copy()
    if "row_hash" not in to_insert.columns:
        to_insert["row_hash"] = None
    to_insert["Date of Admission"] = to_insert["Date of Admission"].astype(str)
    to_insert["Discharge Date"] = to_insert["Discharge Date"].astype(str)

    con.register("quarantine_batch", to_insert[cols])
    con.execute(f"""
        INSERT INTO quarantine ({', '.join(f'"{c}"' if ' ' in c else c for c in cols)})
        SELECT {', '.join(f'"{c}"' if ' ' in c else c for c in cols)} FROM quarantine_batch
    """)
    con.unregister("quarantine_batch")

    log(f"Quarantined {len(to_insert)} rows written to quarantine table")
    return len(to_insert)

def load_idempotent_conn(con, df):
    """Load into DuckDB via staging table, then INSERT OR REPLACE into target keyed on row_hash."""
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

    log(f"Loaded idempotently: {before_count} rows before, {after_count} rows after (this run had {len(df)} clean rows)")
    return after_count

if __name__ == "__main__":
    df = fetch_source(SOURCE_PATH)
    clean, quarantined_validation = validate(df)          # checks 1-4
    clean = add_row_hash(clean)
    clean, quarantined_dupes = check_uniqueness(clean)     # check 5

    con = duckdb.connect(DB_PATH)

    # write quarantine (validation failures have no row_hash yet; that's fine)
    write_quarantine(con, quarantined_validation)
    write_quarantine(con, quarantined_dupes)

    final_count = load_idempotent_conn(con, clean)
    log(f"Ingestion run complete. Final clean table row count: {final_count}")
    log(f"Total quarantined this run: {len(quarantined_validation) + len(quarantined_dupes)}")

    con.close()