"""Unit tests for Parquet event-to-table mapping."""

from lambdas import parquet_transform as pt


def test_table_for_push_event() -> None:
    payload = {"commits": [{"id": "abc"}]}
    assert pt._table_for(payload, "github/2026/01/01/x.json") == "github_commits"


def test_table_for_backfill_issues() -> None:
    payload = {"backfill": True, "kind": "issues", "repo": "mimir"}
    assert pt._table_for(payload, "key") == "github_issues"


def test_table_for_backfill_pulls() -> None:
    payload = {"backfill": True, "kind": "pulls", "repo": "mimir"}
    assert pt._table_for(payload, "key") == "github_pull_requests"


def test_table_for_backfill_commits() -> None:
    payload = {"backfill": True, "kind": "commits", "repo": "mimir"}
    assert pt._table_for(payload, "key") == "github_commits"


def test_normalize_row_omits_source_partition_column() -> None:
    row = pt._normalize_row({"payload": {"id": 1, "number": 42}}, "github_issues")
    assert "source" not in row
    assert row["table"] == "github_issues"
