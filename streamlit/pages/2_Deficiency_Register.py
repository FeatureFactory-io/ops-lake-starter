"""Deficiency register — Action Register with dE/dK/dI (not a starter tab)."""

import pandas as pd
import streamlit as st

from story_data import load_yaml, route_for_tag
from story_visuals import tag_incidence_figure

st.set_page_config(page_title="Deficiency register", layout="wide")
st.title("Deficiency register")
st.caption(
    "Copy CAS triage. Do not re-classify tags. dK is Team Upskill Engine input only. "
    "dE+automate/delegate → AI SDLC candidate; other dE → process/tooling or drop."
)

rows = load_yaml("action_register.yaml")["rows"]
st.plotly_chart(tag_incidence_figure(rows), use_container_width=True)

display_rows = []
for row in rows:
    for tag in row.get("cause_tags") or []:
        recorded = (row.get("routes") or {}).get(tag)
        derived = route_for_tag(tag, row["decision"])
        display_rows.append(
            {
                "rank": row["rank"],
                "stage": row["stage_id"],
                "finding": row["finding"],
                "decision": row["decision"],
                "tag": tag,
                "route": recorded or derived,
                "clock": row.get("clock"),
                "unit": row.get("unit"),
                "n": row.get("n"),
                "role": row.get("role"),
            }
        )
st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)
