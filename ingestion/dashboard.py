import streamlit as st
import duckdb
import pandas as pd
from datetime import datetime, timezone
from build_marts import build_marts_admissions_daily, DB_PATH

STALE_THRESHOLD_HOURS = 24

st.set_page_config(page_title="Admissions Daily Mart", layout="wide", page_icon="🏥")

# ---------------- STYLING ----------------
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: 'Calibri', 'Segoe UI', sans-serif;
    background-color: #ffffff;
}

.main-header {
    background: linear-gradient(90deg, #1a2b4c 0%, #27406b 100%);
    padding: 2rem 2.5rem;
    border-radius: 10px;
    margin-bottom: 1.5rem;
    border-bottom: 4px solid #c9a227;
}
.main-header h1 {
    font-family: Georgia, serif;
    color: #ffffff;
    margin: 0;
    font-size: 2rem;
}
.main-header p {
    color: #d6dce8;
    margin: 0.3rem 0 0 0;
    font-size: 0.95rem;
}

.kpi-card {
    background-color: #f4f6f9;
    border-left: 5px solid #1a2b4c;
    border-radius: 8px;
    padding: 1.2rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}
.kpi-label {
    color: #4a5568;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 0.3rem;
}
.kpi-value {
    font-family: Georgia, serif;
    color: #1a2b4c;
    font-size: 1.8rem;
    font-weight: bold;
}

.chart-card {
    background-color: #ffffff;
    border: 1px solid #e5e9f0;
    border-radius: 10px;
    padding: 1.2rem 1.5rem 0.5rem 1.5rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    margin-bottom: 1.5rem;
}
.chart-card h4 {
    font-family: Georgia, serif;
    color: #1a2b4c;
    margin-top: 0;
}

.footer-note {
    color: #8a93a3;
    font-size: 0.8rem;
    text-align: center;
    margin-top: 2rem;
    border-top: 1px solid #e5e9f0;
    padding-top: 1rem;
}

section[data-testid="stSidebar"] {
    background-color: #f4f6f9;
    border-right: 1px solid #e5e9f0;
}
section[data-testid="stSidebar"] .block-container {
    padding-top: 1rem;
}
.sidebar-header {
    background: linear-gradient(90deg, #1a2b4c 0%, #27406b 100%);
    padding: 1rem 1.2rem;
    border-radius: 8px;
    border-bottom: 3px solid #c9a227;
    margin-bottom: 0.8rem;
}
.sidebar-header h3 {
    font-family: Georgia, serif;
    color: #ffffff;
    margin: 0;
    font-size: 1.1rem;
}
.sidebar-header p {
    color: #d6dce8;
    margin: 0.25rem 0 0 0;
    font-size: 0.8rem;
}
section[data-testid="stSidebar"] .stButton > button {
    background-color: #1a2b4c;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 0.6rem 1rem;
    font-size: 0.85rem;
    font-weight: 500;
    width: 100%;
    transition: background-color 0.2s ease;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #c9a227;
    color: #1a2b4c;
}
</style>
""", unsafe_allow_html=True)

# ---------------- HEADER ----------------
st.markdown("""
<div class="main-header">
    <h1>🏥 Admissions Daily Mart</h1>
    <p>Group 3 &nbsp;·&nbsp; DSAI 6226 &nbsp;·&nbsp; Lab 7 — Analytics From the Pipeline</p>
</div>
""", unsafe_allow_html=True)

# ---------------- SIDEBAR: LIVE FRESHNESS DEMO ----------------
st.sidebar.markdown("""
<div class="sidebar-header">
    <h3>⏱ Freshness Demo</h3>
    <p>Simulate a missed pipeline run, then restore it live.</p>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("⏪  Simulate missed refresh (backdate 30h)"):
    con = duckdb.connect(DB_PATH)
    con.execute("""
        UPDATE marts_admissions_daily
        SET refreshed_at = CURRENT_TIMESTAMP - INTERVAL '30 hours'
    """)
    con.close()
    st.rerun()

if st.sidebar.button("🔄  Run pipeline now (restore freshness)"):
    con = duckdb.connect(DB_PATH)
    build_marts_admissions_daily(con)
    con.close()
    st.rerun()

# ---------------- LOAD DATA ----------------
con = duckdb.connect(DB_PATH, read_only=True)
df = con.execute("SELECT * FROM marts_admissions_daily ORDER BY admission_date").fetchdf()
con.close()

df["admission_date"] = pd.to_datetime(df["admission_date"])

# ---------------- FRESHNESS BANNER ----------------
latest_refresh = df["refreshed_at"].max()
now = datetime.now(timezone.utc)
age_hours = (now - latest_refresh).total_seconds() / 3600

if age_hours <= STALE_THRESHOLD_HOURS:
    st.success(f"✅  **Data as of** {latest_refresh.strftime('%Y-%m-%d %H:%M:%S %Z')} "
               f"— refreshed {age_hours:.1f} hours ago")
else:
    st.error(f"⚠️  **STALE DATA** — last refreshed {latest_refresh.strftime('%Y-%m-%d %H:%M:%S %Z')} "
             f"({age_hours:.1f} hours ago), beyond the {STALE_THRESHOLD_HOURS}h freshness promise. "
             f"The pipeline refresh may have failed.")

st.write("")

# ---------------- KPI CARDS ----------------
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Total Admissions (All Days)</div>
        <div class="kpi-value">{df['total_admissions'].sum():,}</div>
    </div>
    """, unsafe_allow_html=True)
with col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">Avg Billing Amount (Overall)</div>
        <div class="kpi-value">${df['avg_billing_amount'].mean():,.2f}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# ---------------- CHARTS ----------------
st.markdown('<div class="chart-card"><h4>Total Admissions per Day</h4>', unsafe_allow_html=True)
st.line_chart(df.set_index("admission_date")["total_admissions"], color="#1a2b4c")
st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div class="chart-card"><h4>Average Billing Amount per Day</h4>', unsafe_allow_html=True)
st.line_chart(df.set_index("admission_date")["avg_billing_amount"], color="#c9a227")
st.markdown('</div>', unsafe_allow_html=True)

# ---------------- FOOTER ----------------
st.markdown("""
<div class="footer-note">
    Every number above is defined once in <code>metrics.md</code> and computed in <code>build_marts.py</code> —
    this dashboard only reads and displays, it never recalculates.
</div>
""", unsafe_allow_html=True)