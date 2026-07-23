-- Zentrale, nicht geheime Laufzeitkonfiguration der Pipeline.
-- Idempotent und ohne Änderungen an bestehenden Werten.

CREATE SCHEMA IF NOT EXISTS trading;

CREATE TABLE IF NOT EXISTS trading.pipeline_config (
    config_key    TEXT PRIMARY KEY,
    value_bool    BOOLEAN,
    value_text    TEXT,
    value_numeric NUMERIC,
    description   TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO trading.pipeline_config
    (config_key, value_bool, description)
VALUES
    ('DRY_RUN', FALSE, 'Unterdrückt produktive Empfehlungs-Schreibvorgänge und Versand.'),
    ('REQUIRE_CONFIRMATION', TRUE, 'Erfordert eine Bestätigung vor dem Öffnen oder Schließen von Empfehlungen.')
ON CONFLICT (config_key) DO NOTHING;
