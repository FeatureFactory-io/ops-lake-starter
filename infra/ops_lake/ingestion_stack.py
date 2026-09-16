from aws_cdk import (
    BundlingOptions,
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_sqs as sqs,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as apigwv2_integrations,
    aws_events as events,
    aws_events_targets as targets,
    aws_s3_notifications as s3n,
    aws_secretsmanager as secretsmanager,
)
from constructs import Construct

from ops_lake.scope import load_scope_contract


class IngestionStack(Stack):
    """Raw/curated buckets, GitHub webhook, SQS buffer, Parquet transform."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._contract = load_scope_contract()
        self.raw_bucket = self._make_bucket("Raw", self._contract["buckets"]["raw"])
        self.curated_bucket = self._make_bucket(
            "Curated", self._contract["buckets"]["curated"]
        )
        self.athena_results_bucket = self._make_results_bucket()
        self._queue = self._make_buffer_queue()
        self._cursors = self._make_cursor_table()
        self._webhook_secret, self._github_token_secret = self._make_secrets()
        self.http_api = self._add_github_ingestion()
        self._add_backfill_lambda()
        self._add_parquet_transform()

    def _make_bucket(self, id_prefix: str, bucket_name: str) -> s3.Bucket:
        return s3.Bucket(
            self,
            f"{id_prefix}Bucket",
            bucket_name=bucket_name,
            encryption=s3.BucketEncryption.KMS_MANAGED,
            bucket_key_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            versioned=True,
            removal_policy=RemovalPolicy.RETAIN,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id=f"{id_prefix}ToIA",
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(90),
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(365),
                        ),
                    ],
                )
            ],
        )

    def _make_results_bucket(self) -> s3.Bucket:
        return s3.Bucket(
            self,
            "AthenaResultsBucket",
            bucket_name=self._contract["buckets"]["athena_results"],
            encryption=s3.BucketEncryption.KMS_MANAGED,
            bucket_key_enabled=True,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            lifecycle_rules=[
                s3.LifecycleRule(id="ExpireResults", expiration=Duration.days(7))
            ],
        )

    def _make_buffer_queue(self) -> sqs.Queue:
        queue = sqs.Queue(
            self,
            "ParquetBuffer",
            visibility_timeout=Duration.minutes(6),
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )
        queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="AllowS3RawBucketSend",
                principals=[iam.ServicePrincipal("s3.amazonaws.com")],
                actions=["sqs:SendMessage"],
                resources=[queue.queue_arn],
                conditions={
                    "ArnEquals": {"aws:SourceArn": self.raw_bucket.bucket_arn},
                },
            )
        )
        return queue

    def _make_cursor_table(self) -> dynamodb.Table:
        return dynamodb.Table(
            self,
            "IngestionCursors",
            table_name="ops-lake-ingestion-cursors",
            partition_key=dynamodb.Attribute(
                name="source", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _make_secrets(self) -> tuple[secretsmanager.Secret, secretsmanager.Secret]:
        webhook = secretsmanager.Secret(
            self,
            "GithubWebhookSecretResource",
            secret_name=self._contract.get("secrets", {}).get(
                "github_webhook", "ops-lake/github-webhook-secret"
            ),
            description="GitHub webhook HMAC secret — update after org webhook created",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                exclude_punctuation=True,
                password_length=32,
            ),
        )
        api_token = secretsmanager.Secret(
            self,
            "GithubApiTokenSecret",
            secret_name=self._contract.get("secrets", {}).get(
                "github_api_token", "ops-lake/github-api-token"
            ),
            description="GitHub PAT for backfill/poll — set value manually",
        )
        return webhook, api_token

    def _lambda_code(self) -> lambda_.Code:
        if self.node.try_get_context("skip_bundling"):
            return lambda_.Code.from_asset("infra/lambdas")
        return lambda_.Code.from_asset(
            "infra/lambdas",
            bundling=BundlingOptions(
                image=lambda_.Runtime.PYTHON_3_12.bundling_image,
                command=[
                    "bash",
                    "-c",
                    "pip install -r requirements.txt -t /asset-output "
                    "&& cp -au . /asset-output",
                ],
            ),
        )

    def _add_github_ingestion(self) -> apigwv2.HttpApi | None:
        if "github" not in self._contract["sources"]:
            return None
        fn = lambda_.Function(
            self,
            "GithubWebhookFn",
            function_name="GithubWebhookFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="github_webhook.handler",
            code=self._lambda_code(),
            timeout=Duration.seconds(30),
            environment={
                "RAW_BUCKET": self.raw_bucket.bucket_name,
                "WEBHOOK_SECRET_ARN": self._webhook_secret.secret_arn,
            },
        )
        self.raw_bucket.grant_put(fn)
        self._webhook_secret.grant_read(fn)
        integration = apigwv2_integrations.HttpLambdaIntegration(
            "GithubWebhookIntegration", fn
        )
        api = apigwv2.HttpApi(self, "IngestionHttpApi")
        api.add_routes(
            path="/webhooks/github",
            methods=[apigwv2.HttpMethod.POST],
            integration=integration,
        )
        if "github_project_items" in self._contract["views"]:
            self._add_projects_poller()
        CfnOutput(
            self,
            "GithubWebhookUrl",
            value=f"{api.url}webhooks/github",
            export_name="OpsLakeGithubWebhookUrl",
        )
        return api

    def _add_backfill_lambda(self) -> None:
        if "github" not in self._contract["sources"]:
            return
        import json as _json

        fn = lambda_.Function(
            self,
            "GithubBackfillFn",
            function_name="GithubBackfillFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="github_backfill.handler",
            code=self._lambda_code(),
            timeout=Duration.minutes(10),
            memory_size=1024,
            environment={
                "RAW_BUCKET": self.raw_bucket.bucket_name,
                "GITHUB_TOKEN_SECRET_ARN": self._github_token_secret.secret_arn,
                "GITHUB_ORG": self._contract["org"],
                "REPOS_JSON": _json.dumps(self._contract.get("repos", [])),
            },
        )
        self.raw_bucket.grant_put(fn)
        self._github_token_secret.grant_read(fn)

    def _add_projects_poller(self) -> None:
        fn = lambda_.Function(
            self,
            "GithubProjectsPollFn",
            function_name="GithubProjectsPollFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="github_projects_poll.handler",
            code=self._lambda_code(),
            timeout=Duration.minutes(2),
            environment={
                "RAW_BUCKET": self.raw_bucket.bucket_name,
                "CURSOR_TABLE": self._cursors.table_name,
                "GITHUB_TOKEN_SECRET_ARN": self._github_token_secret.secret_arn,
                "GITHUB_ORG": self._contract["org"],
            },
        )
        self.raw_bucket.grant_put(fn)
        self._cursors.grant_read_write_data(fn)
        self._github_token_secret.grant_read(fn)
        events.Rule(
            self,
            "GithubProjectsPollSchedule",
            schedule=events.Schedule.rate(Duration.minutes(15)),
            targets=[targets.LambdaFunction(fn)],
        )

    def _add_parquet_transform(self) -> None:
        fn = lambda_.Function(
            self,
            "ParquetTransformFn",
            function_name="ParquetTransformFn",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="parquet_transform.handler",
            code=self._lambda_code(),
            timeout=Duration.minutes(5),
            environment={
                "RAW_BUCKET": self.raw_bucket.bucket_name,
                "CURATED_BUCKET": self.curated_bucket.bucket_name,
                "BUFFER_QUEUE_URL": self._queue.queue_url,
            },
        )
        self.raw_bucket.grant_read(fn)
        self.curated_bucket.grant_put(fn)
        self._queue.grant_send_messages(fn)
        self._queue.grant_consume_messages(fn)
        self.raw_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.SqsDestination(self._queue),
        )
        fn.add_event_source_mapping(
            "ParquetBufferMapping",
            event_source_arn=self._queue.queue_arn,
            batch_size=100,
            max_batching_window=Duration.seconds(30),
        )
        fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"],
                resources=[self._queue.queue_arn],
            )
        )
