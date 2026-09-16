"""Unit tests for Glue catalog listing used by the Streamlit mart."""

from unittest.mock import MagicMock

from glue_catalog import list_glue_table_names


def test_list_glue_table_names_paginates_all_pages() -> None:
    client = MagicMock()
    paginator = MagicMock()
    client.get_paginator.return_value = paginator
    paginator.paginate.return_value = [
        {"TableList": [{"Name": "github_issues"}, {"Name": "github_commits"}]},
        {"TableList": [{"Name": "github_pull_requests"}]},
    ]

    names = list_glue_table_names("ops_catalog", region="us-east-1", client=client)

    assert names == ["github_commits", "github_issues", "github_pull_requests"]
    paginator.paginate.assert_called_once_with(DatabaseName="ops_catalog")
