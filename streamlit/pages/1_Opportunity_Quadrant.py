"""Opportunity quadrant (TSY floor visual 2)."""

import streamlit as st

from story_visuals import quadrant_figure

st.set_page_config(page_title="Opportunity quadrant", layout="wide")
st.title("Opportunity quadrant")
st.caption(
    "Y = expected efficiency gain. X = implementation effort S–XL. "
    "Low hanging fruit = high impact AND AI-yes AND low effort. Same ids as the cycle badges."
)
st.plotly_chart(quadrant_figure(), use_container_width=True)
