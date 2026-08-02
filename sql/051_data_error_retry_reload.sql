-- ============================================================================
-- 051 (Haertung Welle 1-3, Phase 4, kritisch): data_error war eine dauerhafte
-- Sackgasse - die Ladequery kannte den Status nie, Fehleranalyse E8s
-- Retry-/Eskalationsmechanismus (2026-08-01) konnte dadurch nie tatsaechlich
-- auslösen (Zaehler kam nie ueber 1 hinaus). Live per Diagnose bestaetigt
-- (Phase 3, Haertungsauftrag 2026-08-02).
-- ============================================================================

BEGIN;

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS pre_data_error_status TEXT;

COMMENT ON COLUMN trading.paper_trades.pre_data_error_status IS
  'Status unmittelbar vor dem ersten data_error-Eintritt (open oder proposed) - wird bei Wiederherstellung zurueckgeschrieben, damit ein wiederhergestellter Trade nicht als neue Position missinterpretiert wird (Haertung Welle 1-3, Phase 4).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('051', 'pre_data_error_status auf paper_trades (Haertung Welle 1-3, Phase 4)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
