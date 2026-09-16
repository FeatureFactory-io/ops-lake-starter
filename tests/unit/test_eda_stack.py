"""Unit tests for EdaStack (ECS Fargate Streamlit mart)."""

from aws_cdk import App
from aws_cdk.assertions import Template

from ops_lake.eda_stack import EdaStack
from ops_lake.ingestion_stack import IngestionStack


def test_eda_stack_creates_fargate_service_and_alb() -> None:
    app = App(context={"skip_bundling": True})
    ingestion = IngestionStack(app, "IngestionForEda")
    template = Template.from_stack(
        EdaStack(
            app,
            "TestEda",
            curated_bucket=ingestion.curated_bucket,
            athena_results_bucket=ingestion.athena_results_bucket,
        )
    )
    template.resource_count_is("AWS::ECS::Service", 1)
    template.resource_count_is("AWS::ElasticLoadBalancingV2::LoadBalancer", 1)
    policies = str(template.find_resources("AWS::IAM::Policy"))
    assert "s3:List*" in policies
    assert "CuratedBucket" in policies
