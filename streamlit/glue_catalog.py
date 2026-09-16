"""Glue catalog helpers for the Streamlit mart."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_glue.client import GlueClient


def list_glue_table_names(
    database: str,
    *,
    region: str,
    client: "GlueClient | None" = None,
) -> list[str]:
    """
    List all table names in a Glue database using paginated GetTables.

    :param database: Glue database name. Example: "ops_catalog"
    :param region: AWS region. Example: "us-east-1"
    :param client: Optional Glue client (for tests). Example: None
    :return: Sorted table names. Example: ["github_commits", "github_issues"]
    """
    if not database:
        raise ValueError("database is required")

    glue = client
    if glue is None:
        import boto3

        glue = boto3.client("glue", region_name=region)

    names: list[str] = []
    paginator = glue.get_paginator("get_tables")
    for page in paginator.paginate(DatabaseName=database):
        names.extend(table["Name"] for table in page["TableList"])
    return sorted(names)
