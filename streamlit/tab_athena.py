"""Athena extract + skill-115 metrics for starter mart tabs (notebook and Streamlit)."""

from __future__ import annotations

import logging
import os
import re
from datetime import date, timedelta
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from story_data import tab_is_skipped

logger = logging.getLogger(__name__)

DEFAULT_WINDOW_DAYS = 30
LONG_DAY_HOURS = 10.0
CONVENTIONAL_PREFIX = re.compile(
    r"^(feat|fix|docs|style|refactor|test|chore|perf|ci|build|revert)(\(.+\))?:",
    re.I,
)


def database_name() -> str:
    """
    Glue/Athena database from env (contract default).

    :return: database as str. Example: "ops_catalog"
    """
    return os.environ.get("ATHENA_DATABASE", "ops_catalog")


def workgroup_name() -> str:
    """
    Athena workgroup from env (contract default).

    :return: workgroup as str. Example: "ops-lake-analysts"
    """
    return os.environ.get("ATHENA_WORKGROUP", "ops-lake-analysts")


def query_athena(sql: str) -> tuple[pd.DataFrame, str]:
    """
    Run SQL in the contract workgroup and return rows plus QueryExecutionId.

    :param sql: Athena SQL as str. Example: "SELECT 1 AS n"
    :return: (frame, query_execution_id). Example: (DataFrame(), "abc-123")
    :raises RuntimeError: if Athena does not SUCCEEDED
    """
    import awswrangler as wr

    logger.info("Athena start database=%s workgroup=%s", database_name(), workgroup_name())
    query_id = wr.athena.start_query_execution(
        sql=sql,
        database=database_name(),
        workgroup=workgroup_name(),
    )
    wr.athena.wait_query(query_execution_id=query_id)
    frame = wr.athena.get_query_results(query_execution_id=query_id)
    logger.info("Athena done qid=%s rows=%s", query_id, len(frame))
    return frame, str(query_id)


def empty_cohort(kind: str, window_days: int) -> str:
    """
    Empty-state sentence naming the cohort.

    :param kind: tab id as str. Example: "commits"
    :param window_days: lookback as int. Example: 30
    :return: caption as str. Example: "no commits in last 30 calendar days"
    """
    labels = {
        "commits": "no commits",
        "work_items": "no GitHub issues (non-PR)",
        "changes": "no pull requests",
        "pipelines": "no workflow runs",
        "load": "no commit timestamps",
    }
    noun = labels.get(kind, f"no {kind} rows")
    return f"{noun} in last {window_days} calendar days"


def skip_reason(tab: str, views: list[str]) -> str | None:
    """
    Human skip line, or None when the tab must query Athena.

    :param tab: tab id as str. Example: "sprints"
    :param views: contract views as list[str]. Example: ["github_issues"]
    :return: skip message or None. Example: "SKIP Sprints: no sprint snapshots"
    """
    if not tab_is_skipped(tab, views):
        return None
    messages = {
        "commits": "SKIP Commits: no commit view in contract",
        "work_items": "SKIP Work items: no issue view in contract",
        "changes": "SKIP Changes: no pull-request / merge-request view in contract",
        "pipelines": "SKIP Pipelines: no CI view in contract",
        "load": "SKIP Load: no commit timestamps in contract",
        "defects": "SKIP Defects: contract does not distinguish defect types (no jira_issues)",
        "sprints": "SKIP Sprints: no sprint snapshot extract (a board name is not enough)",
    }
    return messages[tab]


def zero_fill_days(frame: pd.DataFrame, day_col: str, value_col: str, window_days: int) -> pd.DataFrame:
    """
    Reindex a daily count series onto every calendar day in the window.

    :param frame: aggregated counts as DataFrame. Example: DataFrame({"day": [...], "n": [1]})
    :param day_col: date column as str. Example: "day"
    :param value_col: count column as str. Example: "n"
    :param window_days: lookback as int. Example: 30
    :return: zero-filled frame. Example: DataFrame with window_days rows
    """
    end = date.today()
    start = end - timedelta(days=window_days - 1)
    index = pd.date_range(start, end, freq="D").date
    if frame.empty:
        return pd.DataFrame({day_col: index, value_col: [0] * len(index)})
    work = frame.copy()
    work[day_col] = pd.to_datetime(work[day_col], utc=True, errors="coerce").dt.date
    work = work.dropna(subset=[day_col]).groupby(day_col, as_index=False)[value_col].sum()
    filled = pd.DataFrame({day_col: index}).merge(work, how="left", on=day_col)
    filled[value_col] = filled[value_col].fillna(0).astype(int)
    return filled


def conventional_type(message: str | None) -> str:
    """
    Bucket a commit subject by conventional-commit type, or 'other'.

    :param message: commit message as str. Example: "feat(lake): add crawler"
    :return: type bucket as str. Example: "feat"
    """
    if not message:
        return "other"
    match = CONVENTIONAL_PREFIX.match(message.strip())
    if not match:
        return "other"
    return match.group(1).lower()


def commits_metrics(frame: pd.DataFrame, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """
    Commits/day, active authors, author share, conventional-commit mix.

    :param frame: commit rows with committed_at, author, message. Example: DataFrame()
    :param window_days: lookback as int. Example: 30
    :return: metric dict. Example: {"n": 0, "active_authors": 0}
    """
    if frame.empty:
        return {
            "n": 0,
            "active_authors": 0,
            "daily": zero_fill_days(pd.DataFrame(), "day", "commits", window_days),
            "author_share": pd.DataFrame(columns=["author", "commits", "share"]),
            "type_mix": pd.DataFrame(columns=["type", "commits"]),
        }
    work = frame.copy()
    work["committed_at"] = pd.to_datetime(work["committed_at"], utc=True, errors="coerce")
    work = work.dropna(subset=["committed_at"])
    work["day"] = work["committed_at"].dt.date
    work["author"] = work["author"].fillna("unknown")
    work["type"] = work["message"].map(conventional_type)
    daily = zero_fill_days(
        work.groupby("day", as_index=False).size().rename(columns={"size": "commits"}),
        "day",
        "commits",
        window_days,
    )
    author_counts = work.groupby("author", as_index=False).size().rename(columns={"size": "commits"})
    total = int(author_counts["commits"].sum()) or 1
    author_counts["share"] = author_counts["commits"] / total
    author_counts = author_counts.sort_values("commits", ascending=False)
    type_mix = work.groupby("type", as_index=False).size().rename(columns={"size": "commits"})
    return {
        "n": int(len(work)),
        "active_authors": int(work["author"].nunique()),
        "daily": daily,
        "author_share": author_counts,
        "type_mix": type_mix,
    }


def work_item_metrics(frame: pd.DataFrame, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """
    Closed/day and touched/day. Lead/cycle omitted without status segments.

    :param frame: issue rows with created_at, closed_at, updated_at. Example: DataFrame()
    :param window_days: lookback as int. Example: 30
    :return: metric dict. Example: {"n": 0, "clocks": "omitted"}
    """
    work = _prep_timestamps(frame, ("created_at", "closed_at", "updated_at"))
    closed = work.dropna(subset=["closed_at"]).copy()
    closed["day"] = closed["closed_at"].dt.date
    touched = work.dropna(subset=["updated_at"]).copy()
    touched["day"] = touched["updated_at"].dt.date
    return {
        "n": int(len(work)),
        "clocks": "omitted",
        "clocks_reason": "no jira_status_segments — GitHub volume only; do not mix with MR hours",
        "closed_daily": zero_fill_days(
            closed.groupby("day", as_index=False).size().rename(columns={"size": "closed"}),
            "day",
            "closed",
            window_days,
        ),
        "touched_daily": zero_fill_days(
            touched.groupby("day", as_index=False).size().rename(columns={"size": "touched"}),
            "day",
            "touched",
            window_days,
        ),
    }


def change_metrics(frame: pd.DataFrame, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """
    Opened/merged per day and MR cycle hours (median + n).

    :param frame: PR rows with created_at, merged_at, author, integrator. Example: DataFrame()
    :param window_days: lookback as int. Example: 30
    :return: metric dict. Example: {"n": 0, "median_hours": None}
    """
    work = _prep_timestamps(frame, ("created_at", "merged_at"))
    opened = work.dropna(subset=["created_at"]).copy()
    opened["day"] = opened["created_at"].dt.date
    merged = work.dropna(subset=["merged_at"]).copy()
    merged["day"] = merged["merged_at"].dt.date
    merged["hours"] = (merged["merged_at"] - merged["created_at"]).dt.total_seconds() / 3600.0
    merged = merged[merged["hours"] >= 0]
    n_merged = int(len(merged))
    return {
        "n": int(len(work)),
        "n_merged": n_merged,
        "median_hours": float(merged["hours"].median()) if n_merged else None,
        "mean_hours": float(merged["hours"].mean()) if n_merged else None,
        "min_hours": float(merged["hours"].min()) if n_merged else None,
        "max_hours": float(merged["hours"].max()) if n_merged else None,
        "opened_daily": zero_fill_days(
            opened.groupby("day", as_index=False).size().rename(columns={"size": "opened"}),
            "day",
            "opened",
            window_days,
        ),
        "merged_daily": zero_fill_days(
            merged.groupby("day", as_index=False).size().rename(columns={"size": "merged"}),
            "day",
            "merged",
            window_days,
        ),
        "integrators": _role_counts(merged, "integrator"),
        "authors": _role_counts(opened, "author"),
    }


def pipeline_metrics(frame: pd.DataFrame, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """
    Failure rate, status-by-day, duration median, top failing workflow names.

    :param frame: run rows with run_at, conclusion, duration_s, workflow. Example: DataFrame()
    :param window_days: lookback as int. Example: 30
    :return: metric dict. Example: {"n": 0, "failure_rate": None}
    """
    work = _prep_timestamps(frame, ("run_at",))
    terminal = work[work["conclusion"].notna() & (work["conclusion"] != "")].copy()
    terminal = terminal[terminal["conclusion"].str.lower() != "cancelled"]
    n_terminal = int(len(terminal))
    n_failed = int((terminal["conclusion"].str.lower() == "failure").sum()) if n_terminal else 0
    terminal["day"] = terminal["run_at"].dt.date
    status_daily = (
        terminal.groupby(["day", "conclusion"], as_index=False).size().rename(columns={"size": "runs"})
        if n_terminal
        else pd.DataFrame(columns=["day", "conclusion", "runs"])
    )
    duration = pd.to_numeric(terminal.get("duration_s"), errors="coerce") if n_terminal else pd.Series(dtype=float)
    failing = terminal[terminal["conclusion"].str.lower() == "failure"] if n_terminal else terminal
    top_fail = (
        failing.groupby("workflow", as_index=False).size().rename(columns={"size": "failures"})
        if n_terminal
        else pd.DataFrame(columns=["workflow", "failures"])
    )
    top_fail = top_fail.sort_values("failures", ascending=False).head(15)
    return {
        "n": n_terminal,
        "failure_rate": (n_failed / n_terminal) if n_terminal else None,
        "n_failed": n_failed,
        "median_duration_s": float(duration.median()) if n_terminal and duration.notna().any() else None,
        "status_daily": status_daily,
        "top_failing": top_fail,
    }


def load_metrics(frame: pd.DataFrame, window_days: int = DEFAULT_WINDOW_DAYS) -> dict[str, Any]:
    """
    Long-day and weekend share from commit timestamps (risk signal).

    :param frame: commits with committed_at, author. Example: DataFrame()
    :param window_days: lookback as int. Example: 30
    :return: metric dict. Example: {"weekend_share": 0.0, "long_day_share": 0.0}
    """
    work = _prep_timestamps(frame, ("committed_at",))
    if work.empty:
        return {
            "n": 0,
            "weekend_share": None,
            "long_day_share": None,
            "authors_under_load": pd.DataFrame(columns=["author", "long_days", "weekend_commits"]),
        }
    work["author"] = work["author"].fillna("unknown")
    work["weekday"] = work["committed_at"].dt.dayofweek
    work["is_weekend"] = work["weekday"] >= 5
    work["day"] = work["committed_at"].dt.date
    n = int(len(work))
    weekend_share = float(work["is_weekend"].mean())
    spans = work.groupby(["author", "day"])["committed_at"].agg(["min", "max", "size"])
    spans["span_hours"] = (spans["max"] - spans["min"]).dt.total_seconds() / 3600.0
    long_days = spans[spans["span_hours"] >= LONG_DAY_HOURS]
    author_days = int(len(spans)) or 1
    long_share = float(len(long_days) / author_days)
    load_authors = long_days.reset_index().groupby("author").size().rename("long_days").reset_index()
    weekend_authors = (
        work[work["is_weekend"]].groupby("author").size().rename("weekend_commits").reset_index()
    )
    authors = load_authors.merge(weekend_authors, on="author", how="outer").fillna(0)
    authors = authors.sort_values(["long_days", "weekend_commits"], ascending=False)
    return {
        "n": n,
        "weekend_share": weekend_share,
        "long_day_share": long_share,
        "authors_under_load": authors,
        "unit": "UTC calendar; long-day threshold 10h span on one author-day",
    }


def commits_sql(window_days: int = DEFAULT_WINDOW_DAYS) -> str:
    """SQL: latest commit row per sha in the window."""
    db = database_name()
    return f"""
WITH ranked AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.sha') AS sha,
    coalesce(
      json_extract_scalar(raw_json, '$.payload.commit.author.email'),
      json_extract_scalar(raw_json, '$.payload.author.login'),
      json_extract_scalar(raw_json, '$.payload.commit.author.name')
    ) AS author,
    json_extract_scalar(raw_json, '$.payload.commit.message') AS message,
    from_iso8601_timestamp(
      coalesce(
        json_extract_scalar(raw_json, '$.payload.commit.committer.date'),
        json_extract_scalar(raw_json, '$.payload.commit.author.date')
      )
    ) AS committed_at,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.sha')
      ORDER BY created_at DESC
    ) AS rn
  FROM {db}.github_commits
  WHERE source = 'github'
)
SELECT repo, sha, author, message, committed_at
FROM ranked
WHERE rn = 1
  AND committed_at >= date_add('day', -{int(window_days)}, current_timestamp)
"""


def issues_sql(window_days: int = DEFAULT_WINDOW_DAYS) -> str:
    """SQL: latest non-PR issue per number, touched in the window."""
    db = database_name()
    return f"""
WITH ranked AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.number') AS issue_number,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS created_at,
    CASE
      WHEN json_extract_scalar(raw_json, '$.payload.closed_at') IS NOT NULL
        AND json_extract_scalar(raw_json, '$.payload.closed_at') != ''
      THEN from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.closed_at'))
    END AS closed_at,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.updated_at')) AS updated_at,
    json_extract_scalar(raw_json, '$.payload.state') AS state,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.number')
      ORDER BY created_at DESC
    ) AS rn
  FROM {db}.github_issues
  WHERE source = 'github'
    AND json_extract_scalar(raw_json, '$.payload.pull_request') IS NULL
)
SELECT repo, issue_number, created_at, closed_at, updated_at, state
FROM ranked
WHERE rn = 1
  AND (
    updated_at >= date_add('day', -{int(window_days)}, current_timestamp)
    OR closed_at >= date_add('day', -{int(window_days)}, current_timestamp)
  )
"""


def pulls_sql(window_days: int = DEFAULT_WINDOW_DAYS) -> str:
    """SQL: latest PR per number opened or merged in the window."""
    db = database_name()
    return f"""
WITH ranked AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.number') AS pr_number,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS created_at,
    CASE
      WHEN json_extract_scalar(raw_json, '$.payload.merged_at') IS NOT NULL
        AND json_extract_scalar(raw_json, '$.payload.merged_at') != ''
      THEN from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.merged_at'))
    END AS merged_at,
    json_extract_scalar(raw_json, '$.payload.user.login') AS author,
    coalesce(
      json_extract_scalar(raw_json, '$.payload.merged_by.login'),
      json_extract_scalar(raw_json, '$.payload.merge_commit_sha')
    ) AS integrator,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.number')
      ORDER BY created_at DESC
    ) AS rn
  FROM {db}.github_pull_requests
  WHERE source = 'github'
)
SELECT repo, pr_number, created_at, merged_at, author, integrator
FROM ranked
WHERE rn = 1
  AND (
    created_at >= date_add('day', -{int(window_days)}, current_timestamp)
    OR merged_at >= date_add('day', -{int(window_days)}, current_timestamp)
  )
"""


def runs_sql(window_days: int = DEFAULT_WINDOW_DAYS) -> str:
    """SQL: latest workflow run per id in the window. Jobs are not extracted — rank by workflow name."""
    db = database_name()
    return f"""
WITH ranked AS (
  SELECT
    repo,
    json_extract_scalar(raw_json, '$.payload.id') AS run_id,
    json_extract_scalar(raw_json, '$.payload.name') AS workflow,
    json_extract_scalar(raw_json, '$.payload.conclusion') AS conclusion,
    json_extract_scalar(raw_json, '$.payload.status') AS status,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.created_at')) AS run_at,
    from_iso8601_timestamp(json_extract_scalar(raw_json, '$.payload.updated_at')) AS updated_at,
    row_number() OVER (
      PARTITION BY repo, json_extract_scalar(raw_json, '$.payload.id')
      ORDER BY created_at DESC
    ) AS rn
  FROM {db}.github_workflow_runs
  WHERE source = 'github'
)
SELECT
  repo, run_id, workflow, conclusion, status, run_at, updated_at,
  date_diff('second', run_at, updated_at) AS duration_s
FROM ranked
WHERE rn = 1
  AND run_at >= date_add('day', -{int(window_days)}, current_timestamp)
"""


def load_tab_frame(tab: str, window_days: int = DEFAULT_WINDOW_DAYS) -> tuple[pd.DataFrame, str]:
    """
    Query the lake for one instantiated tab.

    :param tab: tab id as str. Example: "commits"
    :param window_days: lookback as int. Example: 30
    :return: (frame, query_execution_id)
    :raises KeyError: if tab has no SQL (defects/sprints)
    """
    builders = {
        "commits": commits_sql,
        "work_items": issues_sql,
        "changes": pulls_sql,
        "pipelines": runs_sql,
        "load": commits_sql,
    }
    sql = builders[tab](window_days)
    logger.info("Loading tab=%s window_days=%s", tab, window_days)
    return query_athena(sql)


def daily_bar(frame: pd.DataFrame, x: str, y: str, title: str) -> go.Figure:
    """Bar chart for a zero-filled daily series."""
    return px.bar(frame, x=x, y=y, title=title)


def _prep_timestamps(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    for column in columns:
        if column in work.columns:
            work[column] = pd.to_datetime(work[column], utc=True, errors="coerce")
    return work


def _role_counts(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return pd.DataFrame(columns=[column, "n"])
    counts = frame.groupby(column, as_index=False).size().rename(columns={"size": "n"})
    return counts.sort_values("n", ascending=False)
