"""Starter tab: Load (risk signal)."""

import streamlit as st

from tab_athena import DEFAULT_WINDOW_DAYS, empty_cohort, load_metrics, load_tab_frame
from tab_pages import skip_or_continue

st.set_page_config(page_title="Load", layout="wide")
st.title("Load")
if skip_or_continue("load", "Load"):
    st.stop()

try:
    frame, qid = load_tab_frame("load", DEFAULT_WINDOW_DAYS)
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.stop()

metrics = load_metrics(frame, DEFAULT_WINDOW_DAYS)
st.caption(
    f"QueryExecutionId `{qid}` · n={metrics['n']} · weekend_share={metrics['weekend_share']} "
    f"· long_day_share={metrics['long_day_share']}"
)
st.warning("Risk signal, not a performance score. " + str(metrics.get("unit")))
if metrics["n"] == 0:
    st.info(empty_cohort("load", DEFAULT_WINDOW_DAYS))
    st.stop()
st.dataframe(metrics["authors_under_load"].head(20), use_container_width=True, hide_index=True)
