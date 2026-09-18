"""Starter tab: Work items."""

import streamlit as st

from tab_athena import DEFAULT_WINDOW_DAYS, daily_bar, empty_cohort, load_tab_frame, work_item_metrics
from tab_pages import skip_or_continue

st.set_page_config(page_title="Work items", layout="wide")
st.title("Work items")
if skip_or_continue("work_items", "Work items"):
    st.stop()

try:
    frame, qid = load_tab_frame("work_items", DEFAULT_WINDOW_DAYS)
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.stop()

metrics = work_item_metrics(frame, DEFAULT_WINDOW_DAYS)
st.caption(f"QueryExecutionId `{qid}` · n={metrics['n']}")
st.warning(metrics["clocks_reason"])
if metrics["n"] == 0:
    st.info(empty_cohort("work_items", DEFAULT_WINDOW_DAYS))
    st.stop()
st.plotly_chart(daily_bar(metrics["closed_daily"], "day", "closed", "Closed / day"), use_container_width=True)
st.plotly_chart(daily_bar(metrics["touched_daily"], "day", "touched", "Touched / day"), use_container_width=True)
