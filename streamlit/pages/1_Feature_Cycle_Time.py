"""Feature issue cycle time dashboard — BPE phase breakdown, WoW trend."""

import os

import pandas as pd
import streamlit as st

from cycle_time import (
    BPE_PHASES,
    PROJECTS,
    WEEKS_LOOKBACK,
    build_milestones_sql,
    enrich_with_phases,
    filter_feature_issues,
    weekly_phase_summary,
)

DATABASE = os.environ.get("ATHENA_DATABASE", "ops_catalog")
WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "ops-lake-analysts")
REGION = os.environ.get("AWS_REGION", "us-east-1")


@st.cache_data(ttl=3600)
def query_athena(sql: str) -> pd.DataFrame:
    import awswrangler as wr

    return wr.athena.read_sql_query(
        sql=sql,
        database=DATABASE,
        workgroup=WORKGROUP,
        ctas_approach=False,
    )


def _format_week(value: object) -> str:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return ""
    return ts.strftime("%Y-%m-%d")


def render() -> None:
    st.header("Feature cycle time")
    st.caption(
        "Median hours to complete feature-type issues, split into BPE/MIN phases "
        f"(Plan → Build → Test → Finalize). Last {WEEKS_LOOKBACK} weeks."
    )

    project = st.selectbox(
        "Project",
        options=list(PROJECTS.keys()),
        index=0,
        help="Master Roadmap spans all scoped repos until Projects v2 items are fully ingested.",
    )
    repos = PROJECTS[project]

    sql = build_milestones_sql(DATABASE, repos=repos)
    with st.expander("Athena SQL", expanded=False):
        st.code(sql, language="sql")

    try:
        milestones = query_athena(sql)
    except Exception as exc:
        st.error(f"Athena query failed: {exc}")
        return

    features = filter_feature_issues(milestones)
    if features.empty:
        st.info(
            "No completed feature-type issues for this filter. "
            "Requires closed issues in the lake (backfill uses state=all) "
            "with enhancement/status-done labels or workflow titles (W27:, BPE-01, [mimir:mcp])."
        )
        if not milestones.empty:
            st.caption(f"{len(milestones)} completed non-feature issues hidden by filter.")
        return

    enriched = enrich_with_phases(features)
    if enriched.empty:
        st.warning("Completed issues found but phase milestones could not be inferred.")
        st.dataframe(milestones, use_container_width=True)
        return

    weekly = weekly_phase_summary(enriched)
    latest = weekly.iloc[-1] if not weekly.empty else None
    prior = weekly.iloc[-2] if len(weekly) >= 2 else None

    st.subheader("Big picture")
    cols = st.columns(3)
    cols[0].metric(
        "Median total cycle (latest week)",
        f"{latest['total_hours']:.1f} h" if latest is not None else "—",
    )
    wow = latest["wow_total_pct"] if latest is not None and pd.notna(latest["wow_total_pct"]) else None
    cols[1].metric(
        "Week-over-week change",
        f"{wow:+.1f}%" if wow is not None else "—",
    )
    cols[2].metric(
        "Features completed (latest week)",
        int(latest["completed_features"]) if latest is not None else 0,
    )

    st.subheader("Total cycle time over time")
    chart_frame = weekly.copy()
    chart_frame["week_label"] = chart_frame["completion_week"].map(_format_week)
    st.line_chart(chart_frame.set_index("week_label")["total_hours"])

    st.subheader("Phase breakdown by week")
    phase_cols = [f"phase_{p.lower()}_hours" for p in BPE_PHASES]
    stacked = chart_frame.set_index("week_label")[phase_cols]
    stacked.columns = list(BPE_PHASES)
    st.bar_chart(stacked)

    st.subheader("Week-over-week detail (last 12 weeks)")
    display = weekly.copy()
    display["completion_week"] = display["completion_week"].map(_format_week)
    display["wow_total_pct"] = display["wow_total_pct"].map(
        lambda v: f"{v:+.1f}%" if pd.notna(v) else "—"
    )
    display = display.rename(
        columns={
            "completion_week": "Week starting",
            "total_hours": "Median total (h)",
            "completed_features": "Features done",
            "wow_total_pct": "WoW Δ total",
            **{f"phase_{p.lower()}_hours": f"Median {p} (h)" for p in BPE_PHASES},
        }
    )
    st.dataframe(display, use_container_width=True, hide_index=True)

    with st.expander("Completed features (detail)"):
        detail = enriched[
            ["repo", "issue_number", "title", "total_hours"]
            + [f"phase_{p.lower()}_hours" for p in BPE_PHASES]
            + ["opened_at", "completed_at"]
        ].copy()
        st.dataframe(detail, use_container_width=True, hide_index=True)


render()
