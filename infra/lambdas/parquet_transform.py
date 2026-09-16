"""SQS-buffered Parquet transform — maps GitHub events onto Scope Contract tables."""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from io import BytesIO
from urllib.parse import unquote_plus

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

_s3 = None


def _s3_client():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3

EVENT_TO_TABLE = {
    "push": "github_commits",
    "pull_request": "github_pull_requests",
    "issues": "github_issues",
    "issue_comment": "github_issues",
    "workflow_run": "github_workflow_runs",
    "projects_v2_item": "github_project_items",
}


def handler(event: dict, _context: object) -> dict:
    """
    Drain SQS records of S3 ObjectCreated events and write Parquet to curated prefix.

    :param event: SQS batch. Example: {"Records": [{"body": "{}"}]}
    :return: {"ok": True, "written": 1}
    """
    logger.info("ParquetTransformFn records=%s", len(event.get("Records", [])))
    written = 0
    for record in event.get("Records", []):
        written += _handle_record(record)
    logger.info("ParquetTransformFn written=%s", written)
    return {"ok": True, "written": written}


def _handle_record(record: dict) -> int:
    body = json.loads(record.get("body") or "{}")
    if isinstance(body, str):
        body = json.loads(body)
    s3_records = body.get("Records", [])
    if not s3_records:
        logger.info("skip empty Records event_keys=%s", list(body.keys()))
        return 0
    for s3_record in s3_records:
        if s3_record.get("eventSource") != "aws:s3":
            continue
        src_bucket = s3_record["s3"]["bucket"]["name"]
        src_key = unquote_plus(s3_record["s3"]["object"]["key"])
        obj = _s3_client().get_object(Bucket=src_bucket, Key=src_key)
        raw_text = obj["Body"].read().decode("utf-8") or "{}"
        payload = json.loads(raw_text)
        table = _table_for(payload, src_key)
        row = _normalize_row(payload, table)
        now = datetime.now(timezone.utc)
        dest_key = (
            f"{table}/source=github/dt={now:%Y-%m-%d}/part-{uuid.uuid4()}.parquet"
        )
        dest_bucket = os.environ["CURATED_BUCKET"]
        parquet_bytes = _to_parquet_bytes([row])
        _s3_client().put_object(Bucket=dest_bucket, Key=dest_key, Body=parquet_bytes)
        logger.info(
            "wrote s3://%s/%s table=%s from s3://%s/%s",
            dest_bucket,
            dest_key,
            table,
            src_bucket,
            src_key,
        )
        return 1
    return 0


def _normalize_row(payload: dict, table: str) -> dict:
    inner = payload.get("payload", payload)
    # source is an S3 partition key (source=github/); omit from Parquet body.
    return {
        "table": table,
        "event_id": str(inner.get("id", inner.get("sha", inner.get("number", "unknown")))),
        "repo": inner.get("repository", {}).get("name") or payload.get("repo"),
        "created_at": inner.get("created_at") or inner.get("updated_at"),
        "raw_json": json.dumps(payload)[:8000],
    }


def _to_parquet_bytes(rows: list[dict]) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return json.dumps(rows).encode("utf-8")
    table = pa.Table.from_pylist(rows)
    buffer = BytesIO()
    pq.write_table(table, buffer, compression="snappy")
    return buffer.getvalue()


def _table_for(payload: dict, src_key: str) -> str:
    if payload.get("backfill"):
        kind = payload.get("kind", "issues")
        return {
            "issues": "github_issues",
            "pulls": "github_pull_requests",
            "commits": "github_commits",
            "workflow_runs": "github_workflow_runs",
        }.get(kind, "github_issues")
    if payload.get("source") == "github_projects_poll":
        return EVENT_TO_TABLE["projects_v2_item"]
    if payload.get("commits"):
        return EVENT_TO_TABLE["push"]
    if payload.get("pull_request"):
        return EVENT_TO_TABLE["pull_request"]
    if payload.get("issue") and not payload.get("pull_request"):
        return EVENT_TO_TABLE["issues"]
    if payload.get("workflow_run"):
        return EVENT_TO_TABLE["workflow_run"]
    if payload.get("projects_v2_item"):
        return EVENT_TO_TABLE["projects_v2_item"]
    logger.warning("unknown event key=%s; defaulting github_issues", src_key)
    return "github_issues"
