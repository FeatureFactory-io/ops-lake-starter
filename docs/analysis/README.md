# Analysis files intern fills

Canonical YAML for the mart image lives in [`streamlit/data/`](../../streamlit/data/). Edit those files (CAS activities), then commit. The Streamlit Dockerfile copies `data/`.

| Activity | File | What to customize |
|---|---|---|
| 247 Map | `streamlit/data/value_stream.yaml` | Keep rows whose tables are in `docs/lake-scope-contract.yaml` → `views`. Uncomment gitlab/jira only if those sources exist. Paste Athena `query_execution_id` after `scripts/create_athena_views.py`. |
| 248 Score | `streamlit/data/role_capacity.yaml`, `cost_of_delay.yaml`, `ai_opportunities.yaml` | Headcount is **assumed** unless labeled measured. Do not `COUNT(DISTINCT author)`. |
| 249 Triage | `streamlit/data/action_register.yaml` | Decision first (eliminate → automate → delegate), then **dE / dK / dI** (multi-tag) and routes. |
| 398 Look | `streamlit/data/promoted_eda.yaml` | Empty until a check earns TSY. |
| 253 Outline | `docs/analysis/narrative-outline.md` | Cycle → quadrant → register → stages → which tabs to skip. |

SQL: [`sql/proof_views.sql`](../../sql/proof_views.sql), [`sql/stage_touch_wait.sql`](../../sql/stage_touch_wait.sql). Workgroup and database come from the contract (`athena_workgroup`, `athena_database`).

After first GHA deploy, fill [`docs/deploy-manifest.yaml`](../deploy-manifest.yaml) (`streamlit_mart_url`). Org webhook is a **human** GitHub org Settings step using stack output `GithubWebhookUrl`.
