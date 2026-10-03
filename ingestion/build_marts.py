import duckdb
from datetime import datetime

DB_PATH = "db/healthcare_ingested.duckdb"

def log(msg):
    """Timestamped log line, same style as ingest.py."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def build_marts_admissions_daily(con):
    """
    Build the one curated output table for Lab 7:
    one row per admission date, aggregated from the CLEAN admissions table only
    (never from raw CSV, never from quarantined rows).
    """
    con.execute("""
        CREATE OR REPLACE TABLE marts_admissions_daily AS
        SELECT
            "Date of Admission" AS admission_date,
            COUNT(*) AS total_admissions,
            ROUND(AVG("Billing Amount"), 2) AS avg_billing_amount,
            CURRENT_TIMESTAMP AS refreshed_at
        FROM admissions
        GROUP BY "Date of Admission"
        ORDER BY "Date of Admission"
    """)

    row_count = con.execute("SELECT COUNT(*) FROM marts_admissions_daily").fetchone()[0]
    log(f"Built marts_admissions_daily: {row_count} daily rows, refreshed_at set to now")

if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)
    build_marts_admissions_daily(con)
    con.close()
    log("Mart build complete.")
