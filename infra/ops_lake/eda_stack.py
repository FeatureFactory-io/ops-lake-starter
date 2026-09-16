"""ECS Fargate + ALB Streamlit data mart (Activity 250 on AWS)."""

from aws_cdk import CfnOutput, Duration, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_ecs_patterns as ecs_patterns
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from constructs import Construct

from ops_lake.scope import load_scope_contract


class EdaStack(Stack):
    """Streamlit mart on ECS Fargate behind ALB (WebSocket-capable)."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        curated_bucket: s3.IBucket,
        athena_results_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        contract = load_scope_contract()
        image = self._build_image()
        task_role = self._make_task_role(curated_bucket, athena_results_bucket)
        service = self._make_service(image, task_role, contract)
        CfnOutput(
            self,
            "StreamlitMartUrl",
            value=f"http://{service.load_balancer.load_balancer_dns_name}",
            export_name="OpsLakeStreamlitMartUrl",
        )

    def _build_image(self) -> ecr_assets.DockerImageAsset:
        return ecr_assets.DockerImageAsset(
            self,
            "StreamlitImage",
            directory="streamlit",
            file="Dockerfile",
            platform=ecr_assets.Platform.LINUX_AMD64,
        )

    def _make_task_role(
        self,
        curated_bucket: s3.IBucket,
        athena_results_bucket: s3.IBucket,
    ) -> iam.Role:
        role = iam.Role(
            self,
            "StreamlitTaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "athena:StartQueryExecution",
                    "athena:GetQueryExecution",
                    "athena:GetQueryResults",
                    "athena:StopQueryExecution",
                    "athena:GetWorkGroup",
                    "athena:ListWorkGroups",
                ],
                resources=["*"],
            )
        )
        role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "glue:GetDatabase",
                    "glue:GetDatabases",
                    "glue:GetTable",
                    "glue:GetTables",
                    "glue:GetPartition",
                    "glue:GetPartitions",
                ],
                resources=["*"],
            )
        )
        curated_bucket.grant_read(role)
        athena_results_bucket.grant_read_write(role)
        return role

    def _make_service(
        self,
        image: ecr_assets.DockerImageAsset,
        task_role: iam.Role,
        contract: dict,
    ) -> ecs_patterns.ApplicationLoadBalancedFargateService:
        vpc = ec2.Vpc(
            self,
            "StreamlitVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
            ],
        )
        service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            "StreamlitMartService",
            vpc=vpc,
            assign_public_ip=True,
            public_load_balancer=True,
            cpu=1024,
            memory_limit_mib=2048,
            desired_count=1,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_docker_image_asset(image),
                container_port=8501,
                task_role=task_role,
                environment={
                    "AWS_REGION": contract["aws_region"],
                    "ATHENA_DATABASE": contract["athena_database"],
                    "ATHENA_WORKGROUP": contract["athena_workgroup"],
                },
            ),
            health_check_grace_period=Duration.seconds(120),
            listener_port=80,
        )
        service.target_group.configure_health_check(
            path="/_stcore/health",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=5,
        )
        return service
