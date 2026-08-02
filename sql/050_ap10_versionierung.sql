-- ============================================================================
-- 050 (Welle-3-Abgleich 2026-08-02, Fund 4/5): Versionierungsfelder auf
-- strategy_signals und learning_rule_proposals
-- ============================================================================
-- AP10 verlangt rule_version/configuration_version/data_schema_version/
-- execution_model_version/risk_model_version/learning_model_version "bei
-- jedem Trade, Signal, Backtest und Lernvorschlag". Nur paper_trades hatte
-- bisher alle relevanten Felder. Bewusste Einschraenkung: execution_model_
-- version/risk_model_version werden NICHT auf strategy_signals/
-- learning_rule_proposals ergaenzt - ein rohes Strategiesignal wird nicht
-- ausgefuehrt und ein Lernvorschlag trifft keine Risikoentscheidung, beide
-- Felder waeren dort inhaltsleer. Die tatsaechlich zutreffenden Felder
-- werden ergaenzt.

BEGIN;

ALTER TABLE trading.strategy_signals
  ADD COLUMN IF NOT EXISTS configuration_version TEXT,
  ADD COLUMN IF NOT EXISTS data_schema_version TEXT;

COMMENT ON COLUMN trading.strategy_signals.configuration_version IS
  'Welle-3-Abgleich AP10: Version der Signal-Berechnungskonfiguration (aktuell ueberwiegend Code-Konstanten, kein dynamisches pipeline_config-Modell fuer Signalschwellen).';
COMMENT ON COLUMN trading.strategy_signals.data_schema_version IS
  'Welle-3-Abgleich AP10: Version des strategy_signals-Tabellenschemas (sql/031 = v1).';

ALTER TABLE trading.learning_rule_proposals
  ADD COLUMN IF NOT EXISTS rule_version TEXT,
  ADD COLUMN IF NOT EXISTS configuration_version TEXT,
  ADD COLUMN IF NOT EXISTS data_schema_version TEXT,
  ADD COLUMN IF NOT EXISTS learning_model_version TEXT;

COMMENT ON COLUMN trading.learning_rule_proposals.learning_model_version IS
  'Welle-3-Abgleich AP10: Version der Lernagenten-Logik, die diesen Vorschlag erzeugt hat (09 vs. 09b unterscheidbar).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('050', 'Versionierungsfelder auf strategy_signals + learning_rule_proposals (Welle-3-Abgleich Fund 4/5)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
