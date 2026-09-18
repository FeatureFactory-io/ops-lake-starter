"""Unit tests for impact arithmetic, dE/dK/dI routes, and tab skip-when."""

import pytest

from story_data import (
    compute_stage_metrics,
    route_for_tag,
    scored_stages,
    tab_is_skipped,
)
from story_visuals import cycle_figure, quadrant_figure, tag_incidence_figure


def test_compute_stage_metrics_matches_sample_sec() -> None:
    # people_in_role=1, touch=2, downstream=8, wait=48 → effort=2, wall=50, impact=386
    metrics = compute_stage_metrics(1, 2, 8, 48)
    assert metrics["effort"] == 2.0
    assert metrics["wall_clock"] == 50.0
    assert metrics["impact"] == 386.0


def test_compute_stage_metrics_rejects_negative() -> None:
    with pytest.raises(ValueError):
        compute_stage_metrics(1, -1, 1, 1)


def test_route_de_automate_is_ai_sdlc() -> None:
    assert route_for_tag("dE", "automate") == "ai_sdlc"


def test_route_de_eliminate_is_drop() -> None:
    assert route_for_tag("dE", "eliminate") == "drop"


def test_route_de_process_is_not_ai_sdlc() -> None:
    assert route_for_tag("dE", "process_tooling") == "process_tooling"


def test_route_dk_is_team_upskill_engine() -> None:
    assert route_for_tag("dK", "automate") == "team_upskill_engine"


def test_route_di_is_staffing() -> None:
    assert route_for_tag("dI", "delegate") == "staffing"


def test_route_unknown_tag_raises() -> None:
    with pytest.raises(ValueError):
        route_for_tag("dX", "eliminate")


def test_tab_commits_skipped_without_commit_view() -> None:
    assert tab_is_skipped("commits", ["github_issues"]) is True


def test_tab_commits_kept_with_github_commits() -> None:
    assert tab_is_skipped("commits", ["github_commits"]) is False


def test_tab_sprints_skipped_on_github_only_contract() -> None:
    views = [
        "github_commits",
        "github_pull_requests",
        "github_issues",
        "github_workflow_runs",
        "github_project_items",
    ]
    assert tab_is_skipped("sprints", views) is True
    assert tab_is_skipped("defects", views) is True
    assert tab_is_skipped("changes", views) is False


def test_scored_stages_marks_sec_as_toc_one() -> None:
    cards = scored_stages()
    by_id = {card["stage_id"]: card for card in cards}
    assert by_id["sec"]["toc_rank_1"] is True
    assert by_id["sec"]["impact"] == 386.0


def test_cycle_and_quadrant_figures_smoke() -> None:
    cycle = cycle_figure()
    quad = quadrant_figure()
    tags = tag_incidence_figure()
    assert cycle.data
    assert quad.data
    assert tags.data
