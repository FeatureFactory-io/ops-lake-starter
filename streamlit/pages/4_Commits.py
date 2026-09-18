"""Starter tab: Commits (drill-down, never the opening)."""

import streamlit as st
import plotly.express as px

from tab_athena import (
    DEFAULT_WINDOW_DAYS,
    commits_metrics,
    daily_bar,
    empty_cohort,
    load_tab_frame,
)
from tab_pages import skip_or_continue

st.set_page_config(page_title="Commits", layout="wide")
st.title("Commits")
if skip_or_continue("commits", "Commits"):
    st.stop()

try:
    frame, qid = load_tab_frame("commits", DEFAULT_WINDOW_DAYS)
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.stop()

metrics = commits_metrics(frame, DEFAULT_WINDOW_DAYS)
st.caption(f"QueryExecutionId `{qid}` · n={metrics['n']} · {DEFAULT_WINDOW_DAYS}d · role=author")
if metrics["n"] == 0:
    st.info(empty_cohort("commits", DEFAULT_WINDOW_DAYS))
    st.stop()
st.plotly_chart(daily_bar(metrics["daily"], "day", "commits", "Commits / day"), use_container_width=True)
st.plotly_chart(
    px.bar(metrics["author_share"].head(20), x="author", y="commits", title="Author commit count"),
    use_container_width=True,
)
st.plotly_chart(
    px.bar(metrics["type_mix"], x="type", y="commits", title="Conventional-commit mix"),
    use_container_width=True,
)
