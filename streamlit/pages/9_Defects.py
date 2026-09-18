"""Starter tab: Defects."""

import streamlit as st

from tab_athena import skip_reason
from tab_pages import contract_views, skip_or_continue

st.set_page_config(page_title="Defects", layout="wide")
st.title("Defects")
if skip_or_continue("defects", "Defects"):
    st.stop()
st.error("Defect types are scoped — implement time-to-target from the contract, do not guess.")
st.caption(skip_reason("defects", contract_views()) or "")
