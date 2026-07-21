-- ============================================================================
-- 005_workflow_errors.sql
--
-- Zentrale Fehlerprotokoll-Tabelle fuer den neuen zentralen Error-Handler
-- (Workflow "11 - Zentraler Error-Handler", n8n-nodes-base.errorTrigger).
-- Jede Zeile entspricht einer unhandled Node-Ausfuehrung, die ueber
-- settings.errorWorkflow an den zentralen Handler durchgereicht wurde.
--
-- Wiederholbar/idempotent: nutzt ausschliesslich CREATE ... IF NOT EXISTS.
-- Loescht oder veraendert KEINE bestehenden Tabellen/Daten.
--
-- Hinweis zur Nummerierung: 003/004 wurden bereits live gegen die
-- Produktionsdatenbank ausgefuehrt (trading.pipeline_config,
-- trading.stock_price_history), sind aber nicht im Git-Repo nachgefuehrt
-- (bekannte Doku-Luecke, siehe README.md). 005 ist die naechste freie
-- Nummer fuer neue, im Repo getrackte Migrationsdateien.
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.workflow_errors (
    id                BIGSERIAL PRIMARY KEY,
    workflow_name     TEXT NOT NULL,
    workflow_id       TEXT,
    execution_id      TEXT,
    execution_url     TEXT,
    failed_node_name  TEXT,
    failed_node_type  TEXT,
    error_message     TEXT,
    error_name        TEXT,
    error_stack       TEXT,
    execution_mode    TEXT,
    occurred_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw_payload_json  JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE INDEX IF NOT EXISTS ix_workflow_errors_workflow_name
    ON trading.workflow_errors (workflow_name);

CREATE INDEX IF NOT EXISTS ix_workflow_errors_occurred_at
    ON trading.workflow_errors (occurred_at);

COMMENT ON TABLE trading.workflow_errors IS
    'Protokoll aller unhandled Node-Fehler aus allen Produktiv-Workflows, eingespeist ueber settings.errorWorkflow -> "11 - Zentraler Error-Handler" (n8n errorTrigger).';
