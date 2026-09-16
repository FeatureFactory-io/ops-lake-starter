#!/usr/bin/env python3
"""Ops lake CDK app — Deploy, Ingestion, Catalog, and Eda stacks from the Lake Scope Contract."""

import aws_cdk as cdk

from ops_lake.catalog_stack import CatalogStack
from ops_lake.deploy_stack import DeployStack
from ops_lake.eda_stack import EdaStack
from ops_lake.ingestion_stack import IngestionStack

app = cdk.App()
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1",
)
DeployStack(app, "OpsLakeDeploy", env=env)
ingestion = IngestionStack(app, "OpsLakeIngestion", env=env)
CatalogStack(
    app,
    "OpsLakeCatalog",
    curated_bucket=ingestion.curated_bucket,
    athena_results_bucket=ingestion.athena_results_bucket,
    env=env,
)
EdaStack(
    app,
    "OpsLakeEda",
    curated_bucket=ingestion.curated_bucket,
    athena_results_bucket=ingestion.athena_results_bucket,
    env=env,
)
app.synth()
