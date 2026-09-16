"""Unit tests for GitHub backfill API URL construction."""

from lambdas.github_backfill import _list_url


def test_list_url_issues_requests_all_states() -> None:
    url = _list_url("repos/YOUR_ORG/example-repo/issues", "issues")
    assert "state=all" in url
    assert "per_page=100" in url


def test_list_url_pulls_requests_all_states() -> None:
    url = _list_url("repos/YOUR_ORG/example-repo/pulls", "pulls")
    assert "state=all" in url


def test_list_url_commits_has_no_state_filter() -> None:
    url = _list_url("repos/YOUR_ORG/example-repo/commits", "commits")
    assert "state=" not in url
    assert "per_page=100" in url
