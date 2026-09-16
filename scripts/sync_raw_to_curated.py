#!/usr/bin/env python3
"""Invoke ParquetTransformFn for raw objects (post-backfill drain)."""

import json
import logging
import sys
from pathlib import Path

import boto3
import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "docs" / "lake-scope-contract.yaml"
FUNCTION_NAME = "ParquetTransformFn"
BATCH_SIZE = 50


def load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    contract = load_contract()
    raw_bucket = contract["buckets"]["raw"]
    region = contract["aws_region"]
    s3 = boto3.client("s3", region_name=region)
    lam = boto3.client("lambda", region_name=region)
    keys = list_raw_keys(s3, raw_bucket)
    if not keys:
        raise RuntimeError(f"No raw objects under s3://{raw_bucket}/github/")
    logger.info("Syncing %s raw objects to curated Parquet", len(keys))
    for offset in range(0, len(keys), BATCH_SIZE):
        chunk = keys[offset : offset + BATCH_SIZE]
        invoke_transform_batch(lam, chunk, raw_bucket)
    logger.info("Sync complete keys=%s", len(keys))
    return 0


def list_raw_keys(s3: object, raw_bucket: str) -> list[str]:
    paginator = s3.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=raw_bucket, Prefix="github/"):
        for item in page.get("Contents", []):
            keys.append(item["Key"])
    return keys


def invoke_transform_batch(lam: object, keys: list[str], raw_bucket: str) -> None:
    records = []
    for key in keys:
        body = {
            "Records": [
                {
                    "eventSource": "aws:s3",
                    "s3": {
                        "bucket": {"name": raw_bucket},
                        "object": {"key": key},
                    },
                }
            ]
        }
        records.append({"body": json.dumps(body)})
    payload = {"Records": records}
    response = lam.invoke(
        FunctionName=FUNCTION_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode("utf-8"),
    )
    result = json.loads(response["Payload"].read().decode("utf-8"))
    if response.get("FunctionError"):
        raise RuntimeError(f"ParquetTransformFn failed keys={len(keys)} result={result}")
    logger.info("transformed batch=%s result=%s", len(keys), result)


if __name__ == "__main__":
    sys.exit(main())
