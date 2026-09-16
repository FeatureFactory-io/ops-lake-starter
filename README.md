# ops-lake-starter

GitHub **template** companion to Mimir playbook **Operations Datalake in AWS** (id=45, draft). Use this template, then fill the Scope Contract. Do not clone the live `opsdl` lake.

## Start here

1. **Use this template** (GitHub → Use this template) into your org. Rename `lake_repo` if the clone is not `ops-lake-starter`.
2. Fill [`docs/lake-scope-contract.yaml`](docs/lake-scope-contract.yaml): `org`, `repos`, `aws_account`, bucket names, `oidc_sub` (`repo:{org}/{lake_repo}:*`). `ci` is XOR: `github_actions` **or** `gitlab_ci`.
3. Laptop once: `cdk bootstrap` then `cdk deploy OpsLakeDeploy` (sandbox mint of the OIDC role). Put the role ARN in repo secret `AWS_DEPLOY_ROLE_ARN`.
4. Repo secret `OPSLAKE_GITHUB_PAT` (`repo`, `read:org`). **Never** name a secret `GITHUB_*`.
5. Push `main` → [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs `cdk deploy --all`.
6. Actions → **populate-lake** → Run workflow.

## Pins (do not relax)

- S3 SSE-KMS **and** `bucket_key_enabled=True` (S3 Bucket Keys).
- Streamlit mart on **ECS Fargate + ALB**, not App Runner (`linux/amd64`; Dockerfile COPY `*.py` and `pages/`).
- OIDC trust **both** `repo:{org}/{repo}:*` and `repo:{org}@*/{repo}@*:*`.

## Local tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/unit -q
```

Laptop `cdk deploy` after the OIDC role exists is not the shared-env path.
