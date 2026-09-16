"""GitHub webhook ingestion — land raw JSON in the raw bucket."""

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")


def handler(event: dict, _context: object) -> dict:
    """
    Verify GitHub signature and put one JSON object per delivery id.

    :param event: API Gateway HTTP API payload. Example: {"headers": {}, "body": "{}"}
    :param _context: Lambda context (unused)
    :return: HTTP response dict. Example: {"statusCode": 200, "body": "{\"ok\": true}"}
    """
    logger.info("GithubWebhookFn start")
    if not _signature_ok(event):
        logger.warning("GithubWebhookFn rejected: bad signature")
        return {"statusCode": 401, "body": json.dumps({"ok": False})}
    body = event.get("body") or "{}"
    delivery = _header(event, "x-github-delivery") or "unknown"
    now = datetime.now(timezone.utc)
    key = f"github/{now:%Y}/{now:%m}/{now:%d}/{delivery}.json"
    bucket = os.environ["RAW_BUCKET"]
    s3.put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))
    logger.info("GithubWebhookFn wrote s3://%s/%s", bucket, key)
    return {"statusCode": 200, "body": json.dumps({"ok": True, "key": key})}


def _header(event: dict, name: str) -> str:
    headers = event.get("headers") or {}
    for key, value in headers.items():
        if key.lower() == name:
            return value
    return ""


def _signature_ok(event: dict) -> bool:
    secret_arn = os.environ["WEBHOOK_SECRET_ARN"]
    secret = secrets.get_secret_value(SecretId=secret_arn)["SecretString"]
    payload = (event.get("body") or "").encode("utf-8")
    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    given = _header(event, "x-hub-signature-256")
    return hmac.compare_digest(expected, given)
