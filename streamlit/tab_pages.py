"""Shared skip-when banner for starter mart tabs."""

from __future__ import annotations

import streamlit as st

from story_data import load_yaml, tab_is_skipped


def contract_views() -> list[str]:
    """
    Views shipped in the mart image.

    :return: view names. Example: ["github_issues"]
    """
    return list(load_yaml("contract_views.yaml")["views"])


def skip_or_continue(tab_id: str, title: str) -> bool:
    """
    Render a skip banner and return True when the tab must not query.

    :param tab_id: tab key as str. Example: "sprints"
    :param title: heading as str. Example: "Sprints"
    :return: True if skipped. Example: True
    """
    views = contract_views()
    if tab_is_skipped(tab_id, views):
        st.warning(
            f"**{title}** skipped: none of the required contract views are listed. "
            "Do not invent joins. See skill Present Findings with Streamlit → Starter mart tabs."
        )
        st.caption(f"Current views: {', '.join(views)}")
        return True
    return False
