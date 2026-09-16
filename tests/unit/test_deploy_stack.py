"""Unit tests for DeployStack synth."""

from aws_cdk import App
from aws_cdk.assertions import Template

from ops_lake.deploy_stack import DeployStack


def test_deploy_stack_creates_oidc_provider_and_role() -> None:
    template = Template.from_stack(DeployStack(App(), "TestDeploy"))
    template.has_resource_properties(
        "AWS::IAM::Role",
        {"RoleName": "ops-lake-github-oidc-deploy"},
    )
    roles = template.find_resources("AWS::IAM::Role")
    assert any("token.actions.githubusercontent.com" in str(r) for r in roles.values())
