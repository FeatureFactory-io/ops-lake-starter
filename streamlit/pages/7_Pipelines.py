"""Starter tab: Pipelines."""

import streamlit as st
import plotly.express as px

from tab_athena import DEFAULT_WINDOW_DAYS, empty_cohort, load_tab_frame, pipeline_metrics
from tab_pages import skip_or_continue

st.set_page_config(page_title="Pipelines", layout="wide")
st.title("Pipelines")
if skip_or_continue("pipelines", "Pipelines"):
    st.stop()

try:
    frame, qid = load_tab_frame("pipelines", DEFAULT_WINDOW_DAYS)
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.stop()

metrics = pipeline_metrics(frame, DEFAULT_WINDOW_DAYS)
st.caption(
    f"QueryExecutionId `{qid}` · n={metrics['n']} · failure_rate={metrics['failure_rate']} "
    f"· median duration s={metrics['median_duration_s']}"
)
st.caption("Top failing ranks workflow name. Job-level rows are not in this lake.")
if metrics["n"] == 0:
    st.info(empty_cohort("pipelines", DEFAULT_WINDOW_DAYS))
    st.stop()
st.plotly_chart(
    px.bar(metrics["status_daily"], x="day", y="runs", color="conclusion", title="Status by day"),
    use_container_width=True,
)
st.plotly_chart(
    px.bar(metrics["top_failing"], x="failures", y="workflow", orientation="h", title="Top failing workflows"),
    use_container_width=True,
)
