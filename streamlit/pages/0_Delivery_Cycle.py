"""Story home — reconstructed delivery cycle (TSY floor visual 1)."""

import streamlit as st

from story_data import load_yaml, scored_stages
from story_visuals import cycle_figure

st.set_page_config(page_title="Delivery cycle", layout="wide")
st.title("Delivery cycle")
st.caption(
    "Effort = people_in_role × touch_time. Wall-clock = touch + wait. "
    "Impact = effort + (people_downstream × wait_time). Sample YAML until CAS is filled."
)

cards = scored_stages()
st.plotly_chart(cycle_figure(cards), use_container_width=True)

opps = load_yaml("ai_opportunities.yaml")["opportunities"]
st.subheader("Opportunities on this cycle")
st.write(
    "Numbered badges are opportunity names, not agents. Gray (ai_can_help=no) stays unlabeled."
)
for row in opps:
    if row["ai_can_help"] == "yes":
        st.markdown(f"**{row['id']}.** {row['name']} ({row['stage_id']})")

cols = st.columns(len(cards))
for column, card in zip(cols, cards, strict=True):
    badge = "ToC #1" if card.get("toc_rank_1") else card.get("label", "")
    column.metric(
        f"{card['name']} impact",
        f"{card['impact']:.0f}",
        help=f"effort {card['effort']:.0f} · wall-clock {card['wall_clock']:.0f} · {badge}",
    )
    column.caption(
        f"effort {card['effort']:.0f} · wall-clock {card['wall_clock']:.0f} {card['unit']}"
    )
