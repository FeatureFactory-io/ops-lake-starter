"""GitHub OIDC deploy role for CDK via GitHub Actions."""

from aws_cdk import CfnOutput, Stack, aws_iam as iam
from constructs import Construct

from ops_lake.scope import load_scope_contract


class DeployStack(Stack):
    """IAM role trusted by GitHub Actions OIDC for cdk deploy."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        contract = load_scope_contract()
        org = contract["org"]
        repo = contract.get("lake_repo", "ops-lake-starter")
        oidc_sub = contract.get(
            "oidc_sub",
            f"repo:{org}/{repo}:*",
        )
        # GitHub may emit legacy name-only subs or ID-qualified subs
        # (repo:org@ORG_ID/repo@REPO_ID:ref:refs/heads/main).
        oidc_sub_patterns = list(
            dict.fromkeys(
                [
                    oidc_sub,
                    f"repo:{org}/{repo}:*",
                    f"repo:{org}@*/{repo}@*:*",
                ]
            )
        )
        provider_arn = (
            f"arn:aws:iam::{self.account}:oidc-provider/token.actions.githubusercontent.com"
        )
        provider = iam.OpenIdConnectProvider.from_open_id_connect_provider_arn(
            self,
            "GithubOidcProvider",
            open_id_connect_provider_arn=provider_arn,
        )
        self.deploy_role = iam.Role(
            self,
            "GithubOidcDeployRole",
            role_name="ops-lake-github-oidc-deploy",
            assumed_by=iam.WebIdentityPrincipal(
                provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": oidc_sub_patterns,
                    },
                },
            ),
            description="GitHub Actions OIDC role for ops-lake CDK deploy",
        )
        self.deploy_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )
        CfnOutput(
            self,
            "DeployRoleArn",
            value=self.deploy_role.role_arn,
            export_name="OpsLakeDeployRoleArn",
        )
