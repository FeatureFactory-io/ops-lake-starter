"""Raw lake view explorer — sample rows from contract views."""

import os

import streamlit as st

from glue_catalog import list_glue_table_names

DATABASE = os.environ.get("ATHENA_DATABASE", "ops_catalog")
WORKGROUP = os.environ.get("ATHENA_WORKGROUP", "ops-lake-analysts")
REGION = os.environ.get("AWS_REGION", "us-east-1")

CONTRACT_VIEWS = [
    "github_issues",
    "github_pull_requests",
    "github_workflow_runs",
    "github_commits",
    "github_project_items",
]


@st.cache_data(ttl=60)
def list_catalog_tables() -> list[str]:
    return list_glue_table_names(DATABASE, region=REGION)


@st.cache_data(ttl=3600)
def query_athena(sql: str) -> "object":
    import awswrangler as wr

    return wr.athena.read_sql_query(
        sql=sql,
        database=DATABASE,
        workgroup=WORKGROUP,
        ctas_approach=False,
    )


st.header("Lake explorer")
st.caption(f"Athena {DATABASE} · workgroup {WORKGROUP} · region {REGION}")

available = [view for view in CONTRACT_VIEWS if view in list_catalog_tables()]
missing = [view for view in CONTRACT_VIEWS if view not in available]
if missing:
    st.warning(
        "Not yet in Glue catalog (run populate-lake or wait for ingest): "
        + ", ".join(missing)
    )
if not available:
    st.error("No contract views are queryable yet. Run the populate-lake workflow.")
    st.stop()

view = st.selectbox("View", available, index=0)
sql = f'SELECT * FROM "{DATABASE}"."{view}" WHERE source = \'github\' LIMIT 200'
st.code(sql, language="sql")
try:
    frame = query_athena(sql)
    st.metric("Rows (sample)", len(frame))
    st.dataframe(frame, use_container_width=True)
    if view == "github_issues" and not frame.empty:
        st.subheader("Throughput proxy")
        st.bar_chart(frame.groupby("repo").size())
except Exception as exc:
    st.error(f"Athena query failed: {exc}")
    st.info("Re-run populate-lake in GitHub Actions if this view should have data.")
