"""Unit tests for CatalogStack synth against the starter Scope Contract."""

from aws_cdk import App
from aws_cdk.assertions import Template

from ops_lake.catalog_stack import CatalogStack
from ops_lake.ingestion_stack import IngestionStack


def _catalog_template() -> Template:
    app = App(context={"skip_bundling": True})
    ingestion = IngestionStack(app, "TestIngestion")
    catalog = CatalogStack(
        app,
        "TestCatalog",
        curated_bucket=ingestion.curated_bucket,
        athena_results_bucket=ingestion.athena_results_bucket,
    )
    return Template.from_stack(catalog)


def test_catalog_stack_has_glue_database() -> None:
    template = _catalog_template()
    template.has_resource_properties(
        "AWS::Glue::Database",
        {"DatabaseInput": {"Name": "ops_catalog"}},
    )


def test_catalog_stack_has_one_crawler_per_contract_view() -> None:
    template = _catalog_template()
    template.resource_count_is("AWS::Glue::Crawler", 5)
    crawlers = str(template.find_resources("AWS::Glue::Crawler"))
    for view in (
        "github_commits",
        "github_pull_requests",
        "github_issues",
        "github_workflow_runs",
        "github_project_items",
    ):
        assert view in crawlers


def test_catalog_stack_has_athena_workgroup() -> None:
    template = _catalog_template()
    template.has_resource_properties(
        "AWS::Athena::WorkGroup",
        {"Name": "ops-lake-analysts"},
    )


def test_catalog_crawlers_have_daily_schedule() -> None:
    template = _catalog_template()
    crawlers = template.find_resources("AWS::Glue::Crawler")
    for props in crawlers.values():
        schedule = props.get("Properties", {}).get("Schedule", {})
        assert schedule.get("ScheduleExpression") == "cron(0 6 * * ? *)"
