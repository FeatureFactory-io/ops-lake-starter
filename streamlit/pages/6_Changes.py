"""Starter tab: Changes (PR/MR)."""

import streamlit as st
import plotly.express as px

from tab_athena import DEFAULT_WINDOW_DAYS, change_metrics, daily_bar, empty_cohort, load_tab_frame
from tab_pages import skip_or_continue

st.set_page_config(page_title="Changes", layout="wide")
st.title("Changes")
if skip_or_continue("changes", "Changes"):
    st.stop()

try:
    frame, qid = load_tab_frame("changes", DEFAULT_WINDOW_DAYS)
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.stop()

metrics = change_metrics(frame, DEFAULT_WINDOW_DAYS)
st.caption(
    f"QueryExecutionId `{qid}` · opened n={metrics['n']} · merged n={metrics['n_merged']} "
    f"· median hours={metrics['median_hours']} (created→merged, not issue business days)"
)
if metrics["n"] == 0:
    st.info(empty_cohort("changes", DEFAULT_WINDOW_DAYS))
    st.stop()
st.plotly_chart(daily_bar(metrics["opened_daily"], "day", "opened", "Opened / day"), use_container_width=True)
st.plotly_chart(daily_bar(metrics["merged_daily"], "day", "merged", "Merged / day"), use_container_width=True)
st.plotly_chart(
    px.bar(
        metrics["integrators"].head(20),
        x="integrator",
        y="n",
        title="Integrators (merge actor, not assigned reviewer)",
    ),
    use_container_width=True,
)
