-- ============================================================================
-- 046 (Fehleranalyse F3, niedrig, Haertungsauftrag 2026-08-02): Mindestfallzahl
-- fuer 09 (Lernagent Newswirkung) aus pipeline_config statt hartkodiert
-- ============================================================================
-- 09b hat bereits LEARNING_MIN_TRADE_SAMPLE_SIZE (sql/037) fuer den
-- gleichwertigen Zweck beim Handelslernagenten - 09 (der aeltere News-
-- Lernagent) hatte die analoge Schwelle (30, niedrig/mittel-Grenze in
-- confidenceLevel()) weiterhin hartkodiert. Default identisch zum bisherigen
-- Wert, verhaltensneutral bis zur ersten Aenderung.

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
  ('LEARNING_MIN_NEWS_SAMPLE_SIZE', 30, 'Mindest-Fallzahl (Dimension x Wert x Horizont-Kombinationen) fuer eine "mittel" statt "niedrig" belastbare Einordnung im News-Lernagenten (09). Analog zu LEARNING_MIN_TRADE_SAMPLE_SIZE fuer 09b (Fehleranalyse F3).')
ON CONFLICT (config_key) DO NOTHING;
