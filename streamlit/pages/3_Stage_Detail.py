"""Stage detail — only promoted Look-until-Trusted rows."""

import pandas as pd
import streamlit as st

from story_data import load_yaml

st.set_page_config(page_title="Stage detail", layout="wide")
st.title("Stage detail")
st.caption("Only rows in promoted_eda.yaml. Empty file = the opening two visuals stand.")

rows = load_yaml("promoted_eda.yaml").get("rows") or []
if not rows:
    st.info("No extra EDA promoted. Opening two visuals stand.")
else:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
