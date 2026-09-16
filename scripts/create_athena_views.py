#!/usr/bin/env python3
"""Proof Athena can SELECT from each contract view that has a Glue table."""

import logging
import sys
import time
from pathlib import Path

import boto3
import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "docs" / "lake-scope-contract.yaml"

PROOF_SQL = (
    'SELECT event_id, repo, created_at, source, "table", raw_json '
    'FROM "{database}"."{view}" WHERE source = \'github\' LIMIT 10'
)


def load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def glue_table_exists(glue: object, database: str, view: str) -> bool:
    from botocore.exceptions import ClientError

    try:
        glue.get_table(DatabaseName=database, Name=view)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "EntityNotFoundException":
            return False
        raise


def run_query(athena: object, sql: str, database: str, workgroup: str) -> str:
    response = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup,
    )
    execution_id = response["QueryExecutionId"]
    logger.info("Started query %s", execution_id)
    while True:
        status = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status["QueryExecution"]["Status"]["State"]
        if state in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(2)
    if state != "SUCCEEDED":
        reason = status["QueryExecution"]["Status"].get("StateChangeReason", state)
        raise RuntimeError(f"Athena query failed: {reason}")
    return execution_id


def main() -> int:
    contract = load_contract()
    database = contract["athena_database"]
    workgroup = contract["athena_workgroup"]
    region = contract["aws_region"]
    athena = boto3.client("athena", region_name=region)
    glue = boto3.client("glue", region_name=region)
    proved = 0
    skipped: list[str] = []
    for view in contract["views"]:
        if not glue_table_exists(glue, database, view):
            logger.warning("skip view=%s — no Glue table yet (no curated data)", view)
            skipped.append(view)
            continue
        proof = PROOF_SQL.format(database=database, view=view)
        proof_id = run_query(athena, proof, database, workgroup)
        logger.info("view=%s proof_id=%s", view, proof_id)
        proved += 1
    if proved == 0:
        raise RuntimeError("No contract views had Glue tables — run backfill and crawler first.")
    logger.info("proved=%s skipped=%s", proved, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
