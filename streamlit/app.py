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
Use the sidebar to navigate:

- **Feature Cycle Time** — median hours to complete feature-type issues, split into
  BPE phases (Plan / Build / Test / Finalize), week-over-week for the last 12 weeks,
  with project filter.
- **Lake Explorer** — sample rows from curated contract views.
"""
)

st.info("Start with **Feature Cycle Time** for the end-to-end delivery picture.")
