"""Unit tests for skill-115 tab metrics (no Athena)."""

from datetime import datetime, timedelta, timezone

import pandas as pd

from tab_athena import (
    change_metrics,
    commits_metrics,
    conventional_type,
    empty_cohort,
    load_metrics,
    pipeline_metrics,
    skip_reason,
    work_item_metrics,
    zero_fill_days,
)


def test_conventional_type_feat_and_other() -> None:
    assert conventional_type("feat(lake): add crawler") == "feat"
    assert conventional_type("WIP stuff") == "other"


def test_zero_fill_days_covers_window() -> None:
    today = datetime.now(timezone.utc).date()
    frame = pd.DataFrame({"day": [today], "n": [3]})
    filled = zero_fill_days(frame, "day", "n", 7)
    assert len(filled) == 7
    assert int(filled.loc[filled["day"] == today, "n"].iloc[0]) == 3
    assert int(filled["n"].min()) == 0


def test_commits_metrics_author_share_and_n() -> None:
    now = datetime.now(timezone.utc)
    frame = pd.DataFrame(
        {
            "committed_at": [now, now, now - timedelta(days=1)],
            "author": ["ada@x", "ada@x", "linus@x"],
            "message": ["feat: a", "fix: b", "chore: c"],
        }
    )
    metrics = commits_metrics(frame, window_days=7)
    assert metrics["n"] == 3
    assert metrics["active_authors"] == 2
    share = metrics["author_share"].set_index("author")["share"]
    assert abs(float(share["ada@x"]) - (2 / 3)) < 1e-9


def test_work_item_metrics_omits_clocks() -> None:
    now = datetime.now(timezone.utc)
    frame = pd.DataFrame(
        {
            "created_at": [now - timedelta(days=2)],
            "closed_at": [now],
            "updated_at": [now],
        }
    )
    metrics = work_item_metrics(frame, window_days=7)
    assert metrics["clocks"] == "omitted"
    assert int(metrics["closed_daily"]["closed"].sum()) == 1


def test_change_metrics_median_hours() -> None:
    created = datetime(2026, 9, 1, tzinfo=timezone.utc)
    merged = datetime(2026, 9, 1, 4, tzinfo=timezone.utc)
    frame = pd.DataFrame(
        {
            "created_at": [created, created],
            "merged_at": [merged, pd.NaT],
            "author": ["a", "b"],
            "integrator": ["int", None],
        }
    )
    metrics = change_metrics(frame, window_days=30)
    assert metrics["n_merged"] == 1
    assert metrics["median_hours"] == 4.0


def test_pipeline_metrics_failure_rate() -> None:
    now = datetime.now(timezone.utc)
    frame = pd.DataFrame(
        {
            "run_at": [now, now, now],
            "conclusion": ["success", "failure", "cancelled"],
            "duration_s": [10, 20, 5],
            "workflow": ["ci", "ci", "ci"],
        }
    )
    metrics = pipeline_metrics(frame, window_days=7)
    assert metrics["n"] == 2
    assert metrics["n_failed"] == 1
    assert metrics["failure_rate"] == 0.5


def test_load_metrics_weekend_and_long_day() -> None:
    saturday = datetime(2026, 9, 12, 8, tzinfo=timezone.utc)  # Saturday
    same_day_late = datetime(2026, 9, 12, 20, tzinfo=timezone.utc)
    monday = datetime(2026, 9, 14, 10, tzinfo=timezone.utc)
    frame = pd.DataFrame(
        {
            "committed_at": [saturday, same_day_late, monday],
            "author": ["ada", "ada", "ada"],
        }
    )
    metrics = load_metrics(frame, window_days=14)
    assert metrics["n"] == 3
    assert metrics["weekend_share"] == 2 / 3
    assert metrics["long_day_share"] == 0.5  # one of two author-days spans 12h


def test_skip_reason_defects_and_sprints_on_github_only() -> None:
    views = ["github_commits", "github_issues", "github_pull_requests", "github_workflow_runs"]
    assert skip_reason("defects", views).startswith("SKIP Defects")
    assert skip_reason("sprints", views).startswith("SKIP Sprints")
    assert skip_reason("commits", views) is None


def test_empty_cohort_names_window() -> None:
    assert empty_cohort("commits", 30) == "no commits in last 30 calendar days"
