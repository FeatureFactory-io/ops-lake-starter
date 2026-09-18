"""Starter tab: Sprints."""

import streamlit as st

from tab_pages import skip_or_continue

st.set_page_config(page_title="Sprints", layout="wide")
st.title("Sprints")
if skip_or_continue("sprints", "Sprints"):
    st.stop()
st.error("Sprint snapshots are scoped — implement committed vs delivered from those rows.")
