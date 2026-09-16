"""Lake Scope Contract — starter template placeholders."""

from pathlib import Path

import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "lake-scope-contract.yaml"


def _load() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_scope_contract_exists_and_names_views() -> None:
    contract = _load()
    assert contract["org"] == "YOUR_ORG"
    assert contract["host"] == "github"
    assert contract["sources"] == ["github"]
    assert contract["ci"] == "github_actions"
    assert contract["views"] == [
        "github_commits",
        "github_pull_requests",
        "github_issues",
        "github_workflow_runs",
        "github_project_items",
    ]


def test_scope_contract_does_not_invent_gitlab_or_jira() -> None:
    contract = _load()
    joined = " ".join(contract["views"])
    assert "gitlab" not in joined
    assert "jira" not in joined
    assert "gitlab" not in contract["sources"]
    assert "jira" not in contract["sources"]


def test_scope_contract_ci_is_xor() -> None:
    contract = _load()
    assert contract["ci"] in {"github_actions", "gitlab_ci"}
    assert contract["ci"] != "both"


def test_scope_contract_has_lake_repo_and_oidc() -> None:
    contract = _load()
    assert contract["lake_repo"] == "ops-lake-starter"
    assert contract["oidc_sub"] == "repo:YOUR_ORG/ops-lake-starter:*"
    assert contract["secrets"]["github_api_token"] == "ops-lake/github-api-token"
