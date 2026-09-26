import pandas as pd
import duckdb
from ingest import validate, write_quarantine, DB_PATH

bad_rows = pd.DataFrame([
    {
        "Name": "Test Patient A", "Age": 250, "Gender": "Male", "Blood Type": "O+",
        "Medical Condition": "Diabetes", "Date of Admission": "2024-01-01", "Doctor": "Dr. Test",
        "Hospital": "Test Hospital", "Insurance Provider": "TestCo", "Billing Amount": 5000.0,
        "Room Number": 101, "Admission Type": "Urgent", "Discharge Date": "2024-01-05",
        "Medication": "Aspirin", "Test Results": "Normal"
    },
    {
        "Name": "Test Patient B", "Age": 45, "Gender": "Female", "Blood Type": "A+",
        "Medical Condition": "Asthma", "Date of Admission": "2024-05-10", "Doctor": "Dr. Test",
        "Hospital": "Test Hospital", "Insurance Provider": "TestCo", "Billing Amount": 3000.0,
        "Room Number": 102, "Admission Type": "Elective", "Discharge Date": "2024-05-01",
        "Medication": "Ibuprofen", "Test Results": "Normal"
    },
    {
        "Name": None, "Age": 30, "Gender": "Male", "Blood Type": "B+",
        "Medical Condition": "Cancer", "Date of Admission": "2024-03-01", "Doctor": "Dr. Test",
        "Hospital": "Test Hospital", "Insurance Provider": "TestCo", "Billing Amount": 4000.0,
        "Room Number": 103, "Admission Type": "Emergency", "Discharge Date": "2024-03-05",
        "Medication": "Penicillin", "Test Results": "Abnormal"
    },
])

clean, quarantined = validate(bad_rows)
print(f"\nOut of {len(bad_rows)} test rows: {len(clean)} passed, {len(quarantined)} quarantined\n")
print(quarantined[["Name", "reject_reason"]])

con = duckdb.connect(DB_PATH)
write_quarantine(con, quarantined)
con.close()
print("\nWritten to the real quarantine table.")
