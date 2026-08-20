SELECT agent_name, status, started_at, error_message
FROM trading.agent_runs
WHERE agent_name IN ('news-recherche-agent','pruef-agent')
ORDER BY started_at DESC LIMIT 6;

SELECT workflow_name, stage_name, status, finished_at, error_message
FROM trading.pipeline_runs
WHERE workflow_name LIKE '%Report%' OR stage_name = 'report_pruef_agent' OR stage_name = 'orchestrator_ende'
ORDER BY finished_at DESC LIMIT 6;
