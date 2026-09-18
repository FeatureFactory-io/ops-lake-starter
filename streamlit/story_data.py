"""Load TSY YAML and compute wall-clock, effort, impact, and dE/dK/dI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DATA_DIR = Path(__file__).resolve().parent / "data"

TAB_REQUIRED_VIEWS: dict[str, tuple[str, ...]] = {
    "commits": ("github_commits", "gitlab_commits"),
    "work_items": ("github_issues", "jira_issues"),
    "changes": ("github_pull_requests", "gitlab_merge_requests"),
    "pipelines": ("github_workflow_runs", "gitlab_pipelines"),
    "load": ("github_commits", "gitlab_commits"),
    "defects": ("jira_issues",),
    "sprints": ("jira_sprints",),
}

GAIN_RANK = {"S": 1, "M": 2, "L": 3, "XL": 4}
EFFORT_RANK = {"S": 1, "M": 2, "L": 3, "XL": 4}


def data_path(name: str) -> Path:
    """
    Resolve a YAML file under streamlit/data.

    :param name: file name as str. Example: "cost_of_delay.yaml"
    :return: Path. Example: Path(".../streamlit/data/cost_of_delay.yaml")
    :raises FileNotFoundError: if missing
    """
    path = DATA_DIR / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def load_yaml(name: str) -> Any:
    """
    Parse a data YAML file.

    :param name: file name as str. Example: "action_register.yaml"
    :return: loaded object. Example: {"rows": []}
    """
    with data_path(name).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def compute_stage_metrics(
    people_in_role: float,
    touch_time: float,
    people_downstream: float,
    wait_time: float,
) -> dict[str, float]:
    """
    Compute wall-clock, effort, and impact for one stage.

    :param people_in_role: headcount in the role as float. Example: 2.0
    :param touch_time: active hours as float. Example: 8.0
    :param people_downstream: waiting headcount as float. Example: 8.0
    :param wait_time: idle hours as float. Example: 40.0
    :return: metrics dict. Example: {"wall_clock": 48.0, "effort": 16.0, "impact": 336.0}
    :raises ValueError: if any input is negative
    """
    values = (people_in_role, touch_time, people_downstream, wait_time)
    if any(item < 0 for item in values):
        raise ValueError("capacity and duration must be non-negative")
    effort = people_in_role * touch_time
    wall_clock = touch_time + wait_time
    impact = effort + (people_downstream * wait_time)
    return {"wall_clock": wall_clock, "effort": effort, "impact": impact}


def route_for_tag(tag: str, decision: str) -> str:
    """
    Map one cause tag plus EAD decision to a receiving playbook/owner.

    :param tag: dE, dK, or dI as str. Example: "dE"
    :param decision: eliminate, automate, or delegate as str. Example: "automate"
    :return: route id as str. Example: "ai_sdlc"
    :raises ValueError: if tag or decision is unknown
    """
    normalized_tag = tag.strip().lower()
    normalized_decision = decision.strip().lower()
    if normalized_tag == "dk":
        return "team_upskill_engine"
    if normalized_tag == "di":
        return "staffing"
    if normalized_tag != "de":
        raise ValueError(f"unknown cause tag: {tag}")
    if normalized_decision == "eliminate":
        return "drop"
    if normalized_decision in {"automate", "delegate"}:
        return "ai_sdlc"
    if normalized_decision in {"process", "tooling", "process_tooling"}:
        return "process_tooling"
    raise ValueError(f"unknown decision: {decision}")


def tab_is_skipped(tab: str, views: list[str]) -> bool:
    """
    Skip a starter mart tab when none of its required views exist.

    :param tab: tab id as str. Example: "commits"
    :param views: contract views as list[str]. Example: ["github_issues"]
    :return: True when the tab must be omitted. Example: True
    :raises KeyError: if tab is unknown
    """
    required = TAB_REQUIRED_VIEWS[tab]
    view_set = set(views)
    return not any(name in view_set for name in required)


def scored_stages() -> list[dict[str, Any]]:
    """
    Join value stream, capacity, and cost-of-delay into scored stage cards.

    :return: list of stage dicts with metrics. Example: [{"stage_id": "sec", "impact": 386.0}]
    """
    stream = {row["id"]: row for row in load_yaml("value_stream.yaml")["stages"]}
    capacity = {row["stage_id"]: row for row in load_yaml("role_capacity.yaml")["roles"]}
    delay = load_yaml("cost_of_delay.yaml")
    scored: list[dict[str, Any]] = []
    for row in delay["stages"]:
        stage_id = row["stage_id"]
        cap = capacity[stage_id]
        metrics = compute_stage_metrics(
            float(cap["people_in_role"]),
            float(row["touch_time"]),
            float(cap["people_downstream"]),
            float(row["wait_time"]),
        )
        card = {**stream[stage_id], **cap, **row, **metrics, "unit": delay["unit"]}
        scored.append(card)
    return scored


def load_contract_views(contract_path: Path) -> list[str]:
    """
    Read Scope Contract views.

    :param contract_path: YAML path as Path. Example: Path("docs/lake-scope-contract.yaml")
    :return: view names. Example: ["github_issues"]
    """
    with contract_path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    return list(payload.get("views") or [])
