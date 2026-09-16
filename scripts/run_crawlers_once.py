#!/usr/bin/env python3
"""Start all Glue crawlers once (post-backfill)."""

import logging
import sys
import time
from pathlib import Path

import boto3
import yaml

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "docs" / "lake-scope-contract.yaml"


def main() -> int:
    contract = load_contract()
    glue = boto3.client("glue", region_name=contract["aws_region"])
    for view in contract["views"]:
        name = f"{view}_crawler"
        logger.info("Starting crawler %s", name)
        glue.start_crawler(Name=name)
    for view in contract["views"]:
        name = f"{view}_crawler"
        while True:
            state = glue.get_crawler(Name=name)["Crawler"]["State"]
            if state == "READY":
                break
            logger.info("crawler=%s state=%s", name, state)
            time.sleep(10)
    logger.info("All crawlers READY")
    return 0


def load_contract() -> dict:
    with CONTRACT_PATH.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


if __name__ == "__main__":
    sys.exit(main())
