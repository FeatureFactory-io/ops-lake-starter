"""Plotly figures for TSY floor visuals (cycle swimlane and opportunity quadrant)."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from story_data import EFFORT_RANK, GAIN_RANK, load_yaml, scored_stages


def cycle_figure(stages: list[dict[str, Any]] | None = None) -> go.Figure:
    """
    SDLC columns with effort, wall-clock, and impact per stage.

    :param stages: scored stage dicts or None to load YAML. Example: None
    :return: Plotly figure. Example: go.Figure()
    """
    cards = stages if stages is not None else scored_stages()
    frame = pd.DataFrame(cards)
    melted = frame.melt(
        id_vars=["name", "toc_rank_1"],
        value_vars=["effort", "wall_clock", "impact"],
        var_name="metric",
        value_name="value",
    )
    figure = px.bar(
        melted,
        x="name",
        y="value",
        color="metric",
        barmode="group",
        title="Delivery cycle — effort, wall-clock, impact",
        labels={"name": "Stage", "value": "Hours (sample unit)"},
    )
    rank_one = frame.loc[frame["toc_rank_1"] == True, "name"]  # noqa: E712
    if not rank_one.empty:
        figure.add_annotation(
            text=f"ToC #1: {rank_one.iloc[0]}",
            xref="paper",
            yref="paper",
            x=1,
            y=1.12,
            showarrow=False,
        )
    return figure


def quadrant_figure(opportunities: list[dict[str, Any]] | None = None) -> go.Figure:
    """
    Expected efficiency gain vs implementation effort.

    :param opportunities: opportunity rows or None to load YAML. Example: None
    :return: Plotly figure. Example: go.Figure()
    """
    rows = opportunities if opportunities is not None else load_yaml("ai_opportunities.yaml")["opportunities"]
    frame = pd.DataFrame(rows)
    frame["effort_n"] = frame["effort"].map(EFFORT_RANK)
    frame["gain_n"] = frame["expected_gain"].map(GAIN_RANK)
    figure = px.scatter(
        frame,
        x="effort_n",
        y="gain_n",
        text="id",
        color="ai_can_help",
        hover_name="name",
        title="Opportunity quadrant — gain vs effort (names, not agents)",
        labels={"effort_n": "Implementation effort (S→XL)", "gain_n": "Expected efficiency gain"},
    )
    figure.update_traces(textposition="top center", marker={"size": 16})
    figure.update_xaxes(tickmode="array", tickvals=[1, 2, 3, 4], ticktext=["S", "M", "L", "XL"])
    figure.update_yaxes(tickmode="array", tickvals=[1, 2, 3, 4], ticktext=["S", "M", "L", "XL"])
    figure.add_shape(
        type="rect",
        x0=0.5,
        x1=2.5,
        y0=2.5,
        y1=4.5,
        line={"dash": "dash"},
        fillcolor="rgba(0,128,0,0.06)",
    )
    figure.add_annotation(x=1.5, y=4.3, text="Low hanging fruit", showarrow=False)
    return figure


def tag_incidence_figure(rows: list[dict[str, Any]] | None = None) -> go.Figure:
    """
    Overlapping dE/dK/dI counts (not an exclusive pie).

    :param rows: action register rows or None to load YAML. Example: None
    :return: Plotly figure. Example: go.Figure()
    """
    payload = rows if rows is not None else load_yaml("action_register.yaml")["rows"]
    counts = {"dE": 0, "dK": 0, "dI": 0}
    for row in payload:
        for tag in row.get("cause_tags") or []:
            if tag in counts:
                counts[tag] += 1
    figure = px.bar(
        x=list(counts.keys()),
        y=list(counts.values()),
        title="Cause tags (a row may carry more than one)",
        labels={"x": "Tag", "y": "Rows tagged"},
    )
    return figure
