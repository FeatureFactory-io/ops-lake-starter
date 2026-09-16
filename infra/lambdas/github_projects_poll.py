"""Poll GitHub Projects v2 into the raw landing zone. Cursor in DynamoDB."""

import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
dynamodb = boto3.client("dynamodb")


def handler(event: dict, _context: object) -> dict:
    """
    Placeholder poller: writes a heartbeat object so the schedule is testable.

    Full GraphQL pagination is STEP 2 once a GitHub token is in Secrets Manager.

    :param event: EventBridge payload. Example: {}
    :return: {"ok": True, "key": "github/.../heartbeat.json"}
    """
    logger.info("GithubProjectsPollFn start event_keys=%s", list(event.keys()))
    now = datetime.now(timezone.utc)
    key = f"github/{now:%Y}/{now:%m}/{now:%d}/projects-poll-{now:%H%M%S}.json"
    bucket = os.environ["RAW_BUCKET"]
    body = json.dumps({"source": "github_projects_poll", "ts": now.isoformat()})
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))
    logger.info("GithubProjectsPollFn wrote s3://%s/%s", bucket, key)
    return {"ok": True, "key": key}
