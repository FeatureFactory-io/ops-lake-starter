"""Feature issue cycle time — BPE/MIN phase inference from lake views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    pass

# BPE construction workflow + MIN sprint gate (value-stream aligned).
BPE_PHASES: tuple[str, ...] = ("Plan", "Build", "Test", "Finalize")

PROJECTS: dict[str, list[str]] = {
    "All scoped repos": [
        "example-repo",
    ],
}

WEEKS_LOOKBACK = 12


@dataclass(frozen=True)
class PhaseHours:
    """Hours spent in each BPE phase for one completed feature issue."""

    plan: float
    build: float
    test: float
    finalize: float

    @property
    def total(self) -> float:
        return self.plan + self.build + self.test + self.finalize

    def as_dict(self) -> dict[str, float]:
        return {"Plan": self.plan, "Build": self.build, "Test": self.test, "Finalize": self.finalize}


def _parse_label_names(labels_json: str) -> set[str]:
    import json

    try:
        parsed = json.loads(labels_json or "[]")
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed, list):
        return set()
    return {
        str(item.get("name", "")).lower()
        for item in parsed
        if isinstance(item, dict) and item.get("name")
    }


def _title_signals_feature_work(title: str) -> bool:
    import re

    text = (title or "").strip()
    if not text:
        return False
    if "feature request" in text.lower():
        return True
    patterns = (
        r"^[A-Z]{2,}\d+(\.\d+)?:",  # LOG1.1:
        r"^W\d+:",  # W27: yggdrasil workflow issues
        r"^DIAGRAM W\d+:",
        r"^\[[^\]]+:[^\]]+\]",  # [mimir:mcp]
        r"\b(BPE|MIN|DSP|DTA|ESM|EST|BSP|TFK)-\d+\b",
    )
    return any(re.search(p, text) for p in patterns)


def is_feature_issue(title: str, labels_json: str) -> bool:
    """
    Classify issue as feature-type delivery work (BPE/MIN), not defect-only.

    :param title: issue title as str. Example: "W27: Diagram-scoped Munin chat"
    :param labels_json: GitHub labels array JSON. Example: '[{"name":"enhancement"}]'
    :return: True when feature-type. Example: True
    """
    names = _parse_label_names(labels_json)
    if names & {"feature", "enhancement", "status-done"}:
        return True
    if _title_signals_feature_work(title):
        return True
    if "bug" in names:
        return False
    return False


def compute_phase_hours(row: pd.Series) -> PhaseHours | None:
    """
    Infer BPE phase durations from milestone timestamps on one issue row.

    Plan (BPE-01): opened → first PR or first commit
    Build (BPE-02/03): dev start → last commit before CI
    Test (BPE-04/05, MIN-04): first CI → first CI success
    Finalize (BPE-06/07, MIN-07): CI success → closed/merged

    :param row: Series with opened_at, completed_at, first_pr_at, first_commit_at,
        last_commit_at, first_ci_at, first_ci_success_at
    :return: PhaseHours or None when completion timestamp missing
    """
    opened = _to_ts(row.get("opened_at"))
    completed = _to_ts(row.get("completed_at"))
    if opened is None or completed is None or completed <= opened:
        return None

    first_pr = _to_ts(row.get("first_pr_at"))
    first_commit = _to_ts(row.get("first_commit_at"))
    last_commit = _to_ts(row.get("last_commit_at"))
    first_ci = _to_ts(row.get("first_ci_at"))
    first_ci_ok = _to_ts(row.get("first_ci_success_at"))

    dev_start = _earliest(first_pr, first_commit) or opened
    build_end = _latest(last_commit, first_ci) or dev_start
    test_end = first_ci_ok or completed

    plan = max(0.0, _hours(opened, dev_start))
    build = max(0.0, _hours(dev_start, build_end))
    test = max(0.0, _hours(first_ci or build_end, test_end))
    finalize = max(0.0, _hours(test_end, completed))

    if plan + build + test + finalize <= 0:
        return None
    return PhaseHours(plan=plan, build=build, test=test, finalize=finalize)


def filter_feature_issues(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Keep only feature-type issues using label and title heuristics.

    :param frame: milestone rows from Athena
    :return: filtered frame
    """
    if frame.empty:
        return frame
    mask = frame.apply(
        lambda row: is_feature_issue(str(row.get("title", "")), str(row.get("labels_json", ""))),
        axis=1,
    )
    return frame.loc[mask].copy()


def enrich_with_phases(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add phase hour columns and completion week to milestone rows.

    :param frame: Athena milestone rows
    :return: frame with phase columns and completion_week
    """
    if frame.empty:
        return frame

    working = frame.copy()
    phases = working.apply(compute_phase_hours, axis=1)
    working["total_hours"] = phases.map(lambda p: p.total if p else None)
    for phase in BPE_PHASES:
        col = f"phase_{phase.lower()}_hours"
        working[col] = phases.map(lambda p, ph=phase: p.as_dict()[ph] if p else None)

    completed = pd.to_datetime(working["completed_at"], utc=True, errors="coerce")
    working["completion_week"] = completed.dt.to_period("W-SUN").dt.start_time
    return working.dropna(subset=["total_hours"])


def weekly_phase_summary(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate median phase hours by completion week for the last N weeks.

    :param frame: enriched phase frame
    :return: weekly summary with total and phase medians
    """
    if frame.empty:
        return pd.DataFrame()

    working = frame.copy()
    working["completion_week"] = pd.to_datetime(working["completion_week"], utc=True)
    cutoff = working["completion_week"].max() - pd.Timedelta(weeks=WEEKS_LOOKBACK - 1)
    recent = working[working["completion_week"] >= cutoff]

    agg: dict[str, str] = {"total_hours": "median", "issue_number": "count"}
    for phase in BPE_PHASES:
        agg[f"phase_{phase.lower()}_hours"] = "median"

    summary = (
        recent.groupby("completion_week", as_index=False)
        .agg(agg)
        .rename(columns={"issue_number": "completed_features"})
        .sort_values("completion_week")
    )
    summary["wow_total_pct"] = summary["total_hours"].pct_change() * 100.0
    return summary


def build_milestones_sql(database: str, repos: list[str] | None = None) -> str:
    """
    Build Athena SQL returning milestone timestamps for completed feature issues.

    :param database: Glue database. Example: "ops_catalog"
    :param repos: optional repo filter. Example: ["mimir", "yggdrasil"]
    :return: SQL string
    """
    repo_clause = _repo_clause("repo", repos)

    return f"""
WITH issue_rows AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.number') AS issue_number,
    json_extract_scalar(raw_json, '$.payload.title') AS title,
    json_extract(raw_json, '$.payload.labels') AS labels_json,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS opened_at,
    CASE
      WHEN json_extract_scalar(raw_json, '$.payload.closed_at') IS NOT NULL
        AND json_extract_scalar(raw_json, '$.payload.closed_at') != ''
      THEN from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.closed_at'))
    END AS closed_at,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.number')
      ORDER BY
        CASE
          WHEN json_extract_scalar(raw_json, '$.payload.closed_at') IS NOT NULL
            AND json_extract_scalar(raw_json, '$.payload.closed_at') != ''
          THEN 0
          ELSE 1
        END,
        created_at DESC
    ) AS rn
  FROM {database}.github_issues
  WHERE source = 'github'
    AND json_extract_scalar(raw_json, '$.payload.pull_request') IS NULL
    {repo_clause}
),
issues AS (
  SELECT * FROM issue_rows WHERE rn = 1
),
pr_rows AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.number') AS pr_number,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS pr_created_at,
    CASE
      WHEN json_extract_scalar(raw_json, '$.payload.merged_at') IS NOT NULL
        AND json_extract_scalar(raw_json, '$.payload.merged_at') != ''
      THEN from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.merged_at'))
    END AS merged_at,
    json_extract_scalar(raw_json, '$.payload.body') AS body,
    json_extract_scalar(raw_json, '$.payload.head.sha') AS head_sha,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.number')
      ORDER BY created_at DESC
    ) AS rn
  FROM {database}.github_pull_requests
  WHERE source = 'github'
    {repo_clause}
),
prs AS (
  SELECT * FROM pr_rows WHERE rn = 1
),
issue_pr_links AS (
  SELECT
    i.repo,
    i.issue_number,
    i.title,
    i.labels_json,
    i.opened_at,
    coalesce(i.closed_at, max(p.merged_at)) AS completed_at,
    min(p.pr_created_at) AS first_pr_at,
    max(p.merged_at) AS merged_at,
    arbitrary(p.head_sha) AS head_sha
  FROM issues i
  LEFT JOIN prs p
    ON i.repo = p.repo
   AND (
     regexp_extract(p.body, '(?i)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\\s+#([0-9]+)', 1) = i.issue_number
     OR regexp_extract(p.body, '#([0-9]+)', 1) = i.issue_number
   )
  GROUP BY i.repo, i.issue_number, i.title, i.labels_json, i.opened_at, i.closed_at
),
completed AS (
  SELECT * FROM issue_pr_links
  WHERE completed_at IS NOT NULL
    AND completed_at > opened_at
),
commit_rows AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.sha') AS sha,
    from_iso8601_timestamp(
      json_extract_scalar(raw_json, '$.payload.commit.committer.date')
    ) AS committed_at,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.sha')
      ORDER BY created_at DESC
    ) AS rn
  FROM {database}.github_commits
  WHERE source = 'github'
    {repo_clause}
),
commits AS (
  SELECT * FROM commit_rows WHERE rn = 1
),
commit_bounds AS (
  SELECT
    c.repo,
    c.issue_number,
    min(cm.committed_at) AS first_commit_at,
    max(cm.committed_at) AS last_commit_at
  FROM completed c
  LEFT JOIN commits cm
    ON c.repo = cm.repo
   AND cm.committed_at >= c.opened_at
   AND cm.committed_at <= c.completed_at
  GROUP BY 1, 2
),
workflow_rows AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.head_sha') AS head_sha,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS run_at,
    json_extract_scalar(raw_json, '$.payload.conclusion') AS conclusion,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.id')
      ORDER BY created_at DESC
    ) AS rn
  FROM {database}.github_workflow_runs
  WHERE source = 'github'
    {repo_clause}
),
workflows AS (
  SELECT * FROM workflow_rows WHERE rn = 1
),
ci_bounds AS (
  SELECT
    c.repo,
    c.issue_number,
    min(w.run_at) AS first_ci_at,
    min(CASE WHEN w.conclusion = 'success' THEN w.run_at END) AS first_ci_success_at
  FROM completed c
  LEFT JOIN workflows w
    ON c.repo = w.repo
   AND (
     (c.head_sha IS NOT NULL AND w.head_sha = c.head_sha)
     OR w.run_at BETWEEN c.opened_at AND c.completed_at
   )
  GROUP BY 1, 2
)
SELECT
  c.repo,
  c.issue_number,
  c.title,
  c.labels_json,
  c.opened_at,
  c.completed_at,
  c.first_pr_at,
  cb.first_commit_at,
  cb.last_commit_at,
  ci.first_ci_at,
  ci.first_ci_success_at
FROM completed c
LEFT JOIN commit_bounds cb ON c.repo = cb.repo AND c.issue_number = cb.issue_number
LEFT JOIN ci_bounds ci ON c.repo = ci.repo AND c.issue_number = ci.issue_number
ORDER BY c.completed_at DESC
"""


def _repo_clause(column: str, repos: list[str] | None) -> str:
    if not repos:
        return ""
    quoted = ", ".join(f"'{repo}'" for repo in repos)
    return f"AND {column} IN ({quoted})"


def _to_ts(value: object) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts


def _hours(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return (end - start).total_seconds() / 3600.0


def _earliest(*values: pd.Timestamp | None) -> pd.Timestamp | None:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def _latest(*values: pd.Timestamp | None) -> pd.Timestamp | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None
