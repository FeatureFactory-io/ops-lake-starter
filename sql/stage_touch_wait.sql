-- Activity 248. Substitute {database}, {view} from the value-stream map.
-- Backfill envelope: json_extract_scalar(raw_json, '$.payload.*') not top-level GitHub fields.
-- Join issue↔PR on Closes #N, never repo or timestamps alone.
-- Pin QueryExecutionId on cost_of_delay.yaml.

SELECT
  json_extract_scalar(raw_json, '$.payload.number') AS issue_number,
  json_extract_scalar(raw_json, '$.payload.state') AS state,
  json_extract_scalar(raw_json, '$.payload.created_at') AS created_at,
  json_extract_scalar(raw_json, '$.payload.closed_at') AS closed_at
FROM "{database}"."{view}"
WHERE source = 'github'
  AND json_extract_scalar(raw_json, '$.payload.state') = 'closed'
LIMIT 100;
