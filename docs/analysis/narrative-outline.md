# Big-picture-to-detail narrative outline (activity 253)

Presentation skill: Streamlit (or Jupyter: `notebooks/published-findings.ipynb`).

1. **Delivery cycle** — all stages, effort / wall-clock / impact (`streamlit/data/cost_of_delay.yaml`).
2. **Opportunity quadrant** — `streamlit/data/ai_opportunities.yaml`.
3. **Deficiency register** — copy `action_register.yaml`; do not re-tag dE/dK/dI.
4. **Stage sections** (flow order): one finding + Action Register decision (or no action). Promoted EDA ids: none until 398 fills `promoted_eda.yaml`.
5. **Starter tabs** (after the story; skip if views absent):
   - Commits — instantiate if `github_commits`
   - Work items — instantiate if issue view (Jira `jira_issues` else skip GitHub-issues-only volume)
   - Changes — instantiate if `github_pull_requests`
   - Pipelines — instantiate if `github_workflow_runs`
   - Load — instantiate if commit timestamps
   - Defects — skip unless defect types exist
   - Sprints — skip unless sprint snapshots exist
