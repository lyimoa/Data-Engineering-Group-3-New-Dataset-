-- =====================================================================
-- Group 3 — Healthcare Dataset Schema (Lab 2)
-- DuckDB SQL schema: lookup/dimension tables + central fact table
--
-- Design decision: deliberate hybrid schema. Low-cardinality categorical
-- columns (2-8 distinct values, verified against the full 55,500-row
-- dataset) are normalized into lookup tables. High-cardinality columns
-- (Doctor, Hospital, Name — all 40,000+ distinct values) stay as plain
-- attributes in the fact table, since normalizing near-unique values
-- adds join overhead with no meaningful storage or consistency benefit.
-- See README.md for full reasoning.
-- =====================================================================

-- ---------------------------------------------------------------------
-- Raw staging table (loaded from source CSV via pandas -> DuckDB)
-- ---------------------------------------------------------------------
CREATE OR REPLACE TABLE raw_admissions AS SELECT * FROM df;

-- ---------------------------------------------------------------------
-- Lookup / dimension tables — schema definitions
-- ---------------------------------------------------------------------

CREATE OR REPLACE TABLE dim_gender (
    gender_id INTEGER PRIMARY KEY,
    gender VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE TABLE dim_blood_type (
    blood_type_id INTEGER PRIMARY KEY,
    blood_type VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE TABLE dim_medical_condition (
    condition_id INTEGER PRIMARY KEY,
    condition_name VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE TABLE dim_insurance_provider (
    insurance_id INTEGER PRIMARY KEY,
    provider_name VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE TABLE dim_admission_type (
    admission_type_id INTEGER PRIMARY KEY,
    admission_type VARCHAR NOT NULL UNIQUE
);

CREATE OR REPLACE TABLE dim_test_results (
    test_result_id INTEGER PRIMARY KEY,
    test_result VARCHAR NOT NULL UNIQUE
);

-- ---------------------------------------------------------------------
-- Lookup / dimension tables — populate with distinct values
-- ---------------------------------------------------------------------

INSERT INTO dim_gender
SELECT ROW_NUMBER() OVER (ORDER BY Gender) AS gender_id, Gender
FROM (SELECT DISTINCT Gender FROM raw_admissions);

INSERT INTO dim_blood_type
SELECT ROW_NUMBER() OVER (ORDER BY "Blood Type") AS blood_type_id, "Blood Type"
FROM (SELECT DISTINCT "Blood Type" FROM raw_admissions);

INSERT INTO dim_medical_condition
SELECT ROW_NUMBER() OVER (ORDER BY "Medical Condition") AS condition_id, "Medical Condition"
FROM (SELECT DISTINCT "Medical Condition" FROM raw_admissions);

INSERT INTO dim_insurance_provider
SELECT ROW_NUMBER() OVER (ORDER BY "Insurance Provider") AS insurance_id, "Insurance Provider"
FROM (SELECT DISTINCT "Insurance Provider" FROM raw_admissions);

INSERT INTO dim_admission_type
SELECT ROW_NUMBER() OVER (ORDER BY "Admission Type") AS admission_type_id, "Admission Type"
FROM (SELECT DISTINCT "Admission Type" FROM raw_admissions);

INSERT INTO dim_test_results
SELECT ROW_NUMBER() OVER (ORDER BY "Test Results") AS test_result_id, "Test Results"
FROM (SELECT DISTINCT "Test Results" FROM raw_admissions);

-- ---------------------------------------------------------------------
-- Central fact table — schema definition
-- Grain: one row per hospital admission
-- ---------------------------------------------------------------------

CREATE OR REPLACE TABLE fact_admissions (
    admission_id INTEGER PRIMARY KEY,
    patient_name VARCHAR,
    age INTEGER,
    gender_id INTEGER REFERENCES dim_gender(gender_id),
    blood_type_id INTEGER REFERENCES dim_blood_type(blood_type_id),
    condition_id INTEGER REFERENCES dim_medical_condition(condition_id),
    date_of_admission DATE,
    doctor VARCHAR,
    hospital VARCHAR,
    insurance_id INTEGER REFERENCES dim_insurance_provider(insurance_id),
    billing_amount DOUBLE,
    room_number INTEGER,
    admission_type_id INTEGER REFERENCES dim_admission_type(admission_type_id),
    discharge_date DATE,
    medication VARCHAR,
    test_result_id INTEGER REFERENCES dim_test_results(test_result_id)
);

-- ---------------------------------------------------------------------
-- Central fact table — populate, resolving text values to foreign keys
-- via joins against each lookup table
-- ---------------------------------------------------------------------

INSERT INTO fact_admissions
SELECT
    ROW_NUMBER() OVER () AS admission_id,
    r.Name AS patient_name,
    r.Age AS age,
    g.gender_id,
    bt.blood_type_id,
    mc.condition_id,
    r."Date of Admission" AS date_of_admission,
    r.Doctor AS doctor,
    r.Hospital AS hospital,
    ip.insurance_id,
    r."Billing Amount" AS billing_amount,
    r."Room Number" AS room_number,
    adm_t.admission_type_id,
    r."Discharge Date" AS discharge_date,
    r.Medication AS medication,
    tr.test_result_id
FROM raw_admissions r
JOIN dim_gender g ON r.Gender = g.gender
JOIN dim_blood_type bt ON r."Blood Type" = bt.blood_type
JOIN dim_medical_condition mc ON r."Medical Condition" = mc.condition_name
JOIN dim_insurance_provider ip ON r."Insurance Provider" = ip.provider_name
JOIN dim_admission_type adm_t ON r."Admission Type" = adm_t.admission_type
JOIN dim_test_results tr ON r."Test Results" = tr.test_result;

-- ---------------------------------------------------------------------
-- Verification: row counts should match (55,500 each)
-- ---------------------------------------------------------------------

-- SELECT COUNT(*) FROM raw_admissions;
-- SELECT COUNT(*) FROM fact_admissions;

-- ---------------------------------------------------------------------
-- Sample analytical query: admission count and billing totals by
-- medical condition and insurance provider (supports the cost-planning
-- and billing-accuracy decisions identified in the Data Problem Statement)
-- ---------------------------------------------------------------------

SELECT
    mc.condition_name,
    ip.provider_name,
    COUNT(*) AS admission_count,
    ROUND(AVG(f.billing_amount), 2) AS avg_billing,
    ROUND(SUM(f.billing_amount), 2) AS total_billing
FROM fact_admissions f
JOIN dim_medical_condition mc ON f.condition_id = mc.condition_id
JOIN dim_insurance_provider ip ON f.insurance_id = ip.insurance_id
GROUP BY mc.condition_name, ip.provider_name
ORDER BY mc.condition_name, total_billing DESC;
