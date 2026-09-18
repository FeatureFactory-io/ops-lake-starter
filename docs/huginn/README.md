# Huginn refresh (activity 255)

There is no MCP connector for Huginn. Check a sibling clone `../huginn` for an existing Agent/Scenario before creating one.

1. Open the Huginn web UI for this org (URL is org-specific — record it in playbook notes).
2. Search Scenarios for lake / Athena / Streamlit.
3. Agent type follows the Present Findings surface:
   - Streamlit mart: HTTP GET against `streamlit_mart_url` in `docs/deploy-manifest.yaml`
   - Jupyter: usually defer — notebooks are not a live URL
   - Athena: only if an existing Agent already runs a query
4. Dry-run / Run now once. Record Agent name, schedule, and purpose here.
5. Flag as a future MCP-connector candidate.

Skip when the mart URL is empty — write a deferral instead of inventing an Agent.
