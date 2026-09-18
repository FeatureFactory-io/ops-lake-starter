# ops-lake-starter

GitHub **template** companion to Mimir playbook **Operations Datalake in AWS** (id=45, draft). Use this template, then fill the Scope Contract. Do not clone the live `opsdl` lake.

## Start here

1. **Use this template** (GitHub → Use this template) into your org. Rename `lake_repo` if the clone is not `ops-lake-starter`.
2. Fill [`docs/lake-scope-contract.yaml`](docs/lake-scope-contract.yaml): `org`, `repos`, `aws_account`, bucket names, `oidc_sub` (`repo:{org}/{lake_repo}:*`). `ci` is XOR: `github_actions` **or** `gitlab_ci`.
3. Laptop once: `cdk bootstrap` then `cdk deploy OpsLakeDeploy` (sandbox mint of the OIDC role). Put the role ARN in repo secret `AWS_DEPLOY_ROLE_ARN`.
4. Repo secret `OPSLAKE_GITHUB_PAT` (`repo`, `read:org`). **Never** name a secret `GITHUB_*`.
5. Push `main` → [`.github/workflows/deploy.yml`](.github/workflows/deploy.yml) runs `cdk deploy --all`.
6. Actions → **populate-lake** → Run workflow.
7. Human: GitHub org **Settings → Webhooks** → payload URL = stack output `GithubWebhookUrl`, secret = Secrets Manager `ops-lake/github-webhook-secret`.
8. Fill analysis YAML under [`streamlit/data/`](streamlit/data/) (see [`docs/analysis/README.md`](docs/analysis/README.md)). Mart home is **Delivery cycle**, not Feature Cycle Time.

If `ci: gitlab_ci`, copy [`.gitlab-ci.yml.example`](.gitlab-ci.yml.example) to `.gitlab-ci.yml` — do not also run GitHub Actions deploy against the same account.

## Pins (do not relax)

- S3 SSE-KMS **and** `bucket_key_enabled=True` (S3 Bucket Keys).
- Streamlit mart on **ECS Fargate + ALB**, not App Runner (`linux/amd64`; Dockerfile COPY `*.py`, `pages/`, and `data/`).
- OIDC trust **both** `repo:{org}/{repo}:*` and `repo:{org}@*/{repo}@*:*`.

## Local tests

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/unit -q
```

Laptop `cdk deploy` after the OIDC role exists is not the shared-env path.

## Local notebooks

```bash
pip install -r requirements-eda.txt
python -m ipykernel install --user --name opsdl --display-name "Python (opsdl .venv)"
```

Open [`notebooks/published-findings.ipynb`](notebooks/published-findings.ipynb). Select kernel **Python (opsdl .venv)**. Notebook root is the lake repo so `streamlit/data/*.yaml` resolves. Then **Restart & Run All**. Look-until-Trusted is [`notebooks/look-until-trusted.ipynb`](notebooks/look-until-trusted.ipynb).

### AWS login refresh is not Athena AccessDenied

If Jupyter / `awswrangler` fails with `AccessDeniedException` on `CreateOAuth2Token`, then `LoginRefreshRequired` ("The refresh token has expired" / "Please reauthenticate using `aws login`"), wrangler never reached `StartQueryExecution`. That is **credential session expiry**, not a Glue/Athena ACL bug.

1. In a terminal: `aws login` (or this org's equivalent `aws sso login`).
2. Confirm `aws sts get-caller-identity` matches `docs/lake-scope-contract.yaml` `aws_account` (template placeholder `000000000000` until you fill the contract).
3. **Restart the Jupyter kernel**, then Restart & Run All — boto3 clients in a running kernel keep the dead token.
4. The login credential provider also needs `pip install 'botocore[crt]'` (`requirements-eda.txt`).
