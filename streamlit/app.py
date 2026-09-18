"""Streamlit data mart on ECS Fargate — Ops Lake analytics."""

import os

import streamlit as st

st.set_page_config(page_title="Ops Lake Mart", layout="wide", initial_sidebar_state="expanded")

DATABASE = os.environ.get("ATHENA_DATABASE", "ops_catalog")
WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "ops-lake-analysts")
REGION = os.environ.get("AWS_REGION", "us-east-1")

st.title("Operations Lake")
st.caption(f"Athena {DATABASE} · workgroup {WORKGROUP} · region {REGION}")

st.markdown(
    """
Story (in order):

1. **Delivery cycle** — effort, wall-clock, impact on every stage
2. **Opportunity quadrant** — gain vs effort (opportunity names, not agents)
3. **Deficiency register** — dE / dK / dI + routes
4. **Stage detail** — only promoted EDA
5. **Tabs** — Commits, Work items, Changes, Pipelines, Load, Defects, Sprints (skip if views missing)

Look-until-trusted workspace (not the opening): Feature Cycle Time, Lake Explorer.
"""
)
st.info("Start with **Delivery cycle**, then the quadrant. Do not lead with Feature Cycle Time or Commits.")
