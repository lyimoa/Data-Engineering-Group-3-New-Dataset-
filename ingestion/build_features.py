import duckdb
import pandas as pd
from datetime import datetime

DB_PATH = "db/healthcare_ingested.duckdb"

CHRONIC_CONDITIONS = {"Diabetes", "Hypertension", "Asthma"}

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def age_group(age):
    if age < 18:
        return "Child"
    elif age < 65:
        return "Adult"
    else:
        return "Senior"

def build_feature_table(con):
    """
    Lab 8: build an ML-ready feature table for predicting Billing Amount
    at the moment of discharge, from the CLEAN admissions table only.
    Every feature here is engineered deliberately and checked against the
    leakage question: would this value be knowable at prediction time?
    """
    df = con.execute("""
        SELECT row_hash, Age, Gender, "Blood Type", "Medical Condition",
               "Admission Type", "Insurance Provider",
               "Date of Admission", "Discharge Date", "Billing Amount"
        FROM admissions
    """).fetchdf()

    df["Date of Admission"] = pd.to_datetime(df["Date of Admission"])
    df["Discharge Date"] = pd.to_datetime(df["Discharge Date"])

    # ---- Engineered features (each with a one-line story — see features.md) ----
    df["length_of_stay_days"] = (df["Discharge Date"] - df["Date of Admission"]).dt.days
    df["admission_month"] = df["Date of Admission"].dt.month
    df["admission_dayofweek"] = df["Date of Admission"].dt.dayofweek
    df["is_weekend_admission"] = df["admission_dayofweek"].isin([5, 6])
    df["age_group"] = df["Age"].apply(age_group)
    df["is_chronic_condition"] = df["Medical Condition"].isin(CHRONIC_CONDITIONS)

    # ---- Time-based split: sort by admission date, assign by quantile ----
    df = df.sort_values("Date of Admission").reset_index(drop=True)
    n = len(df)
    train_cutoff = int(n * 0.70)
    val_cutoff = int(n * 0.85)

    df["split"] = "test"
    df.loc[:train_cutoff, "split"] = "train"
    df.loc[train_cutoff:val_cutoff, "split"] = "validate"

    feature_cols = [
        "row_hash", "Age", "Gender", "Blood Type", "Medical Condition",
        "Admission Type", "Insurance Provider",
        "length_of_stay_days", "admission_month", "admission_dayofweek",
        "is_weekend_admission", "age_group", "is_chronic_condition",
        "Date of Admission", "split", "Billing Amount"
    ]
    out = df[feature_cols].rename(columns={
        "Blood Type": "blood_type",
        "Medical Condition": "medical_condition",
        "Admission Type": "admission_type",
        "Insurance Provider": "insurance_provider",
        "Date of Admission": "admission_date",
        "Billing Amount": "billing_amount"
    })

    con.execute("CREATE OR REPLACE TABLE ml_features AS SELECT * FROM out")

    counts = con.execute("SELECT split, COUNT(*) FROM ml_features GROUP BY split ORDER BY split").fetchdf()
    log(f"Built ml_features: {n} rows")
    log(f"Split counts:\n{counts.to_string(index=False)}")
    log(f"Date range — train ends: {df.loc[train_cutoff, 'Date of Admission'].date()}, "
        f"validate ends: {df.loc[val_cutoff, 'Date of Admission'].date()}")

if __name__ == "__main__":
    con = duckdb.connect(DB_PATH)
    build_feature_table(con)
    con.close()
    log("Feature table build complete.")
