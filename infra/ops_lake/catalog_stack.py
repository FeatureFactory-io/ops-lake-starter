from aws_cdk import (
    Stack,
    aws_athena as athena,
    aws_glue as glue,
    aws_iam as iam,
    aws_s3 as s3,
)
from constructs import Construct

from ops_lake.scope import load_scope_contract


class CatalogStack(Stack):
    """Glue database, one crawler per contract view, Athena workgroup."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        curated_bucket: s3.IBucket,
        athena_results_bucket: s3.IBucket,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._contract = load_scope_contract()
        self._curated = curated_bucket
        self._results = athena_results_bucket
        self._database = self._make_database()
        role = self._make_crawler_role()
        for view in self._contract["views"]:
            self._make_crawler(view, role)
        self._workgroup = self._make_workgroup()
        self._make_named_queries()

    def _make_database(self) -> glue.CfnDatabase:
        return glue.CfnDatabase(
            self,
            "OpsCatalog",
            catalog_id=self.account,
            database_input=glue.CfnDatabase.DatabaseInputProperty(
                name=self._contract["athena_database"],
                description="Operations data lake catalog (Scope Contract views)",
            ),
        )

    def _make_crawler_role(self) -> iam.Role:
        role = iam.Role(
            self,
            "GlueCrawlerRole",
            assumed_by=iam.ServicePrincipal("glue.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AWSGlueServiceRole"
                )
            ],
        )
        self._curated.grant_read(role)
        return role

    def _make_crawler(self, view: str, role: iam.Role) -> glue.CfnCrawler:
        crawler = glue.CfnCrawler(
            self,
            f"{_id(view)}Crawler",
            name=f"{view}_crawler",
            role=role.role_arn,
            database_name=self._contract["athena_database"],
            targets=glue.CfnCrawler.TargetsProperty(
                s3_targets=[
                    glue.CfnCrawler.S3TargetProperty(
                        path=f"s3://{self._curated.bucket_name}/{view}/"
                    )
                ]
            ),
            schema_change_policy=glue.CfnCrawler.SchemaChangePolicyProperty(
                update_behavior="UPDATE_IN_DATABASE",
                delete_behavior="LOG",
            ),
            schedule={"scheduleExpression": "cron(0 6 * * ? *)"},
        )
        crawler.add_dependency(self._database)
        return crawler

    def _make_workgroup(self) -> athena.CfnWorkGroup:
        return athena.CfnWorkGroup(
            self,
            "AnalystsWorkGroup",
            name=self._contract["athena_workgroup"],
            work_group_configuration=athena.CfnWorkGroup.WorkGroupConfigurationProperty(
                enforce_work_group_configuration=True,
                bytes_scanned_cutoff_per_query=5 * 1024 * 1024 * 1024,
                result_configuration=athena.CfnWorkGroup.ResultConfigurationProperty(
                    output_location=f"s3://{self._results.bucket_name}/",
                ),
            ),
        )

    def _make_named_queries(self) -> None:
        database = self._contract["athena_database"]
        for view in self._contract["views"]:
            query = athena.CfnNamedQuery(
                self,
                f"{_id(view)}NamedQuery",
                name=f"preview_{view}",
                database=database,
                work_group=self._contract["athena_workgroup"],
                query_string=(
                    f'SELECT * FROM "{database}"."{view}" '
                    f"WHERE source = 'github' LIMIT 10"
                ),
            )
            query.add_dependency(self._workgroup)


def _id(view: str) -> str:
    return "".join(part.title() for part in view.split("_"))
