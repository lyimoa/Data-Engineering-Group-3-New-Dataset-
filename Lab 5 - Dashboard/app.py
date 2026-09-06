import streamlit as st
from google.cloud import bigquery
import pandas as pd
import altair as alt

st.set_page_config(page_title="Lab 5 - Healthcare Admissions", layout="wide")

PROJECT = "lab-5-healthcare"
DATASET = "healthcare_lab_5"

st.title("🏥 Healthcare Admissions Dashboard")
st.caption("Group 3 · DSAI 6226 · Data Engineering and Analytics · BigQuery sandbox")

client = bigquery.Client(project=PROJECT)

@st.cache_data(ttl=600)
def load_data():
    query = f"""
    SELECT
      Name, Age, Gender, `Blood Type`, `Medical Condition`,
      `Date of Admission`, Doctor, Hospital, `Insurance Provider`,
      `Billing Amount`, `Room Number`, `Admission Type`,
      `Discharge Date`, Medication, `Test Results`
    FROM `{PROJECT}.{DATASET}.Admissions_deduped`
    """
    return client.query(query).to_dataframe()

@st.cache_data(ttl=600)
def load_pipeline_counts():
    query = f"""
    SELECT
      (SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.Admissions`) AS raw_count,
      (SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.Admissions_validated`) AS validated_count,
      (SELECT COUNT(*) FROM `{PROJECT}.{DATASET}.Admissions_deduped`) AS deduped_count
    """
    return client.query(query).to_dataframe().iloc[0]

with st.spinner("Loading data from BigQuery..."):
    df = load_data()
    counts = load_pipeline_counts()

df["Date of Admission"] = pd.to_datetime(df["Date of Admission"])
df["Discharge Date"] = pd.to_datetime(df["Discharge Date"])
df["Length of Stay"] = (df["Discharge Date"] - df["Date of Admission"]).dt.days

# ---------------- SIDEBAR FILTERS ----------------
st.sidebar.header("Filters")

conditions = sorted(df["Medical Condition"].unique())
selected_conditions = st.sidebar.multiselect("Medical Condition", conditions, default=conditions)

genders = sorted(df["Gender"].unique())
selected_genders = st.sidebar.multiselect("Gender", genders, default=genders)

admission_types = sorted(df["Admission Type"].unique())
selected_types = st.sidebar.multiselect("Admission Type", admission_types, default=admission_types)

min_date = df["Date of Admission"].min()
max_date = df["Date of Admission"].max()
date_range = st.sidebar.date_input("Date of Admission range", [min_date, max_date])

age_range = st.sidebar.slider("Age range", int(df["Age"].min()), int(df["Age"].max()),
                               (int(df["Age"].min()), int(df["Age"].max())))

filtered = df[
    df["Medical Condition"].isin(selected_conditions) &
    df["Gender"].isin(selected_genders) &
    df["Admission Type"].isin(selected_types) &
    df["Age"].between(age_range[0], age_range[1])
]

if len(date_range) == 2:
    filtered = filtered[
        (filtered["Date of Admission"] >= pd.Timestamp(date_range[0])) &
        (filtered["Date of Admission"] <= pd.Timestamp(date_range[1]))
    ]

# ---------------- KPI ROW ----------------
st.subheader("Key Metrics")
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total Admissions", f"{len(filtered):,}")
k2.metric("Avg Billing", f"${filtered['Billing Amount'].mean():,.2f}" if len(filtered) else "N/A")
k3.metric("Total Billing", f"${filtered['Billing Amount'].sum():,.0f}" if len(filtered) else "N/A")
k4.metric("Avg Length of Stay", f"{filtered['Length of Stay'].mean():.1f} days" if len(filtered) else "N/A")
k5.metric("Avg Age", f"{filtered['Age'].mean():.0f}" if len(filtered) else "N/A")

st.divider()

# ---------------- CHARTS ----------------
col1, col2 = st.columns(2)

with col1:
    st.subheader("Average Billing by Medical Condition")
    billing_by_cond = filtered.groupby("Medical Condition")["Billing Amount"].mean().sort_values(ascending=False)
    st.bar_chart(billing_by_cond)

with col2:
    st.subheader("Admissions by Insurance Provider")
    by_insurance = filtered["Insurance Provider"].value_counts()
    st.bar_chart(by_insurance)

col3, col4 = st.columns(2)

with col3:
    st.subheader("Admission Type Breakdown")
    type_counts = filtered["Admission Type"].value_counts().reset_index()
    type_counts.columns = ["Admission Type", "Count"]
    donut = alt.Chart(type_counts).mark_arc(innerRadius=60).encode(
        theta="Count", color="Admission Type", tooltip=["Admission Type", "Count"]
    )
    st.altair_chart(donut, use_container_width=True)

with col4:
    st.subheader("Admissions Over Time (Monthly)")
    monthly = filtered.set_index("Date of Admission").resample("ME").size()
    st.line_chart(monthly)

st.subheader("Billing Amount Distribution by Condition")
box = alt.Chart(filtered).mark_boxplot().encode(
    x="Medical Condition:N", y="Billing Amount:Q", color="Medical Condition:N"
).properties(height=350)
st.altair_chart(box, use_container_width=True)

st.divider()

# ---------------- DATA QUALITY / PIPELINE SUMMARY ----------------
with st.expander("📋 Data Pipeline Summary (Lab 5)"):
    p1, p2, p3 = st.columns(3)
    p1.metric("Raw rows (Admissions)", f"{int(counts['raw_count']):,}")
    p2.metric("After validation", f"{int(counts['validated_count']):,}",
              delta=f"-{int(counts['raw_count']) - int(counts['validated_count'])} rejected")
    p3.metric("After deduplication (final)", f"{int(counts['deduped_count']):,}",
              delta=f"-{int(counts['validated_count']) - int(counts['deduped_count'])} duplicates")
    st.caption("This dashboard queries Admissions_deduped — the final, cleaned table produced by our BigQuery pipeline (validate → deduplicate), matching Lab 3's ingest.py logic exactly.")

# ---------------- RAW DATA TABLE ----------------
st.subheader("Underlying Data")
st.dataframe(filtered, use_container_width=True, height=300)

csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered data as CSV", csv, "filtered_admissions.csv", "text/csv")
