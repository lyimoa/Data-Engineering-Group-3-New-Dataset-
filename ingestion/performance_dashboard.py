import streamlit as st
import pandas as pd
import altair as alt

RESULTS_PATH = "performance_results.csv"

st.set_page_config(page_title="Lab 9 — Performance Before/After", layout="wide", page_icon="⚡")

st.title("⚡ Pipeline Performance — Before vs After")
st.caption("Group 3 · DSAI 6226 · Lab 9 — Optimisation & Performance")

df = pd.read_csv(RESULTS_PATH)

# Average each step/phase across repeated runs (3 before, 3 after) — a single
# timing is noise (Unit 9: "Benchmarking once"); the average of several isn't.
summary = df.groupby(["step", "phase"], as_index=False)["duration_seconds"].mean()

step_order = ["fetch_source", "validate", "load_to_duckdb", "build_marts", "build_features"]
summary["step"] = pd.Categorical(summary["step"], categories=step_order, ordered=True)
summary = summary.sort_values("step")

bars = alt.Chart(summary).mark_bar().encode(
    x=alt.X("step:N", title="Pipeline Step", sort=step_order),
    y=alt.Y("duration_seconds:Q", title="Avg Duration (seconds)"),
    color=alt.Color("phase:N", title="Phase",
                     scale=alt.Scale(domain=["before", "after"], range=["#c0392b", "#1a7a4c"])),
    xOffset="phase:N",
    tooltip=["step", "phase", alt.Tooltip("duration_seconds:Q", format=".3f")]
)

labels = alt.Chart(summary).mark_text(dy=-8, fontSize=13, fontWeight="bold", color="black").encode(
    x=alt.X("step:N", sort=step_order),
    y=alt.Y("duration_seconds:Q"),
    xOffset="phase:N",
    text=alt.Text("duration_seconds:Q", format=".2f")
)

chart = (bars + labels).properties(height=420)

st.altair_chart(chart, use_container_width=True)

st.subheader("Numbers behind the chart")
pivot = summary.pivot(index="step", columns="phase", values="duration_seconds").reindex(step_order)
pivot["change"] = pivot["after"] - pivot["before"]
st.dataframe(pivot.style.format({
    "before": "{:.3f}s", "after": "{:.3f}s", "change": "{:+.3f}s"
}))

st.caption(
    "Each bar is the average of 3 repeated runs. Only build_features.py was changed "
    "(a row-by-row .apply() replaced with vectorized pd.cut()) — the other steps are "
    "shown flat on purpose, as evidence we fixed the step that was actually slow."
)
