-- Activity 246 / 247. Substitute {database}, {view}, workgroup from
-- docs/lake-scope-contract.yaml (athena_database, views, athena_workgroup).
-- Prefer scripts/create_athena_views.py; this is the copy-this LIMIT 10.
-- Record QueryExecutionId on the value-stream row.

SELECT COUNT(*) AS n
FROM "{database}"."{view}"
WHERE source = 'github';

SELECT event_id, repo, created_at, source, "table", raw_json
FROM "{database}"."{view}"
WHERE source = 'github'
LIMIT 10;
