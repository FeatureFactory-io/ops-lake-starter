"""Unit tests for feature cycle time phase inference."""

import pandas as pd
import pytest

from cycle_time import (
    BPE_PHASES,
    build_milestones_sql,
    compute_phase_hours,
    enrich_with_phases,
    filter_feature_issues,
    is_feature_issue,
    weekly_phase_summary,
)


def test_is_feature_issue_with_feature_label() -> None:
    assert is_feature_issue("Anything", '[{"name": "Feature"}]') is True


def test_is_feature_issue_scenario_title_overrides_bug_label() -> None:
    assert is_feature_issue("LOG1.1: Modal", '[{"name": "bug"}]') is True


def test_is_feature_issue_accepts_scenario_title() -> None:
    assert is_feature_issue("LOG1.1: Add modal", "[]") is True


def test_is_feature_issue_accepts_yggdrasil_workflow_title() -> None:
    assert is_feature_issue("W27: Diagram-scoped Munin chat", "[]") is True


def test_is_feature_issue_accepts_enhancement_label() -> None:
    assert is_feature_issue("Any title", '[{"name": "enhancement"}]') is True


def test_is_feature_issue_accepts_mimir_area_prefix() -> None:
    assert is_feature_issue("[mimir:mcp] Title: DSP-05 emit rules", "[]") is True


def test_is_feature_issue_rejects_plain_bug() -> None:
    assert is_feature_issue("Fix crash on login", '[{"name": "bug"}]') is False


def test_compute_phase_hours_full_path() -> None:
    row = pd.Series(
        {
            "opened_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-11T00:00:00Z",
            "first_pr_at": "2026-01-02T00:00:00Z",
            "first_commit_at": "2026-01-03T00:00:00Z",
            "last_commit_at": "2026-01-05T00:00:00Z",
            "first_ci_at": "2026-01-06T00:00:00Z",
            "first_ci_success_at": "2026-01-08T00:00:00Z",
        }
    )
    phases = compute_phase_hours(row)
    assert phases is not None
    assert phases.plan == 24.0
    assert phases.total > 0
    assert len(phases.as_dict()) == len(BPE_PHASES)


def test_compute_phase_hours_requires_completion() -> None:
    row = pd.Series({"opened_at": "2026-01-01T00:00:00Z", "completed_at": None})
    assert compute_phase_hours(row) is None


def test_enrich_with_phases_adds_weekly_columns() -> None:
    frame = pd.DataFrame(
        [
            {
                "repo": "mimir",
                "issue_number": "1",
                "title": "LOG1.1: Test",
                "opened_at": "2026-01-01T00:00:00Z",
                "completed_at": "2026-01-08T00:00:00Z",
                "first_pr_at": "2026-01-02T00:00:00Z",
                "first_commit_at": "2026-01-3T00:00:00Z",
                "last_commit_at": "2026-01-04T00:00:00Z",
                "first_ci_at": "2026-01-05T00:00:00Z",
                "first_ci_success_at": "2026-01-06T00:00:00Z",
            }
        ]
    )
    enriched = enrich_with_phases(frame)
    assert "total_hours" in enriched.columns
    assert "completion_week" in enriched.columns
    assert enriched["total_hours"].notna().all()


def test_weekly_phase_summary_computes_wow() -> None:
    enriched = pd.DataFrame(
        [
            {
                "completion_week": pd.Timestamp("2026-01-05", tz="UTC"),
                "total_hours": 100.0,
                "phase_plan_hours": 10.0,
                "phase_build_hours": 40.0,
                "phase_test_hours": 30.0,
                "phase_finalize_hours": 20.0,
                "issue_number": "1",
            },
            {
                "completion_week": pd.Timestamp("2026-01-12", tz="UTC"),
                "total_hours": 80.0,
                "phase_plan_hours": 8.0,
                "phase_build_hours": 32.0,
                "phase_test_hours": 24.0,
                "phase_finalize_hours": 16.0,
                "issue_number": "2",
            },
        ]
    )
    summary = weekly_phase_summary(enriched)
    assert len(summary) == 2
    assert summary.iloc[-1]["wow_total_pct"] == pytest.approx(-20.0)


def test_filter_feature_issues() -> None:
    frame = pd.DataFrame(
        [
            {"title": "LOG1.1: Modal", "labels_json": "[]"},
            {"title": "Fix crash", "labels_json": '[{"name": "bug"}]'},
        ]
    )
    filtered = filter_feature_issues(frame)
    assert len(filtered) == 1
    assert filtered.iloc[0]["title"].startswith("LOG1.1")


def test_build_milestones_sql_includes_repo_filter() -> None:
    sql = build_milestones_sql("ops_catalog", repos=["mimir", "yggdrasil"])
    assert "ops_catalog.github_issues" in sql
    assert "'mimir'" in sql
    assert "'yggdrasil'" in sql
