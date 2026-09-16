"""Unit tests for IngestionStack synth against the starter Scope Contract."""

from aws_cdk import App
from aws_cdk.assertions import Template

from ops_lake.ingestion_stack import IngestionStack


def _ingestion_template(stack_id: str = "TestIngestion") -> Template:
    app = App(context={"skip_bundling": True})
    return Template.from_stack(IngestionStack(app, stack_id))


def test_ingestion_stack_creates_three_buckets() -> None:
    template = _ingestion_template("IngestionBuckets")
    template.resource_count_is("AWS::S3::Bucket", 3)


def test_ingestion_stack_enables_s3_bucket_keys_on_all_buckets() -> None:
    template = _ingestion_template("IngestionBucketKeys")
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 3
    for logical_id, resource in buckets.items():
        rules = resource["Properties"]["BucketEncryption"][
            "ServerSideEncryptionConfiguration"
        ]
        default = rules[0]["ServerSideEncryptionByDefault"]
        assert default["SSEAlgorithm"] == "aws:kms", logical_id
        assert rules[0]["BucketKeyEnabled"] is True, logical_id


def test_ingestion_stack_has_github_webhook_only() -> None:
    template = _ingestion_template("IngestionGithub")
    functions = template.find_resources("AWS::Lambda::Function")
    joined = str(functions)
    assert "Gitlab" not in joined
    assert "Jira" not in joined
    assert "GithubWebhook" in joined
    assert "ParquetTransform" in joined


def test_ingestion_stack_has_http_api() -> None:
    template = _ingestion_template("IngestionApi")
    template.resource_count_is("AWS::ApiGatewayV2::Api", 1)


def test_ingestion_stack_has_backfill_and_secrets() -> None:
    template = _ingestion_template("IngestionBackfill")
    functions = str(template.find_resources("AWS::Lambda::Function"))
    assert "GithubBackfill" in functions
    template.resource_count_is("AWS::SecretsManager::Secret", 2)
