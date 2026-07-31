-- ============================================================================
-- Welle 1, Arbeitspaket 7: These und Zeitstop
-- ============================================================================
-- thesis_expires_at und expected_holding_days existieren bereits (sql/017,
-- schema-only) und werden hier wiederverwendet (expected_holding_days =
-- expected_horizon_days aus dem Auftrag - keine doppelte Spalte). Neu:
-- strategy/trade_thesis/thesis_created_at/time_stop_at/invalidation_conditions
-- sowie eine Versionskennung fuer die deterministischen Zeitstop-Regeln je
-- Strategie (mean_reversion/trend_following/breakout/news_event).

ALTER TABLE trading.recommendations
  ADD COLUMN IF NOT EXISTS strategy                     TEXT,
  ADD COLUMN IF NOT EXISTS trade_thesis                  TEXT,
  ADD COLUMN IF NOT EXISTS thesis_created_at             TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS time_stop_at                  TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS invalidation_conditions_json  JSONB,
  ADD COLUMN IF NOT EXISTS thesis_rule_version           TEXT;

COMMENT ON COLUMN trading.recommendations.strategy IS 'Welche der Phase-6-Strategiefamilien (mean_reversion/trend_following/breakout) bzw. news_event den Trade ausgeloest hat - deterministisch aus dominant_strategy/News-Kombination abgeleitet, nicht von einer KI frei gewaehlt.';
COMMENT ON COLUMN trading.recommendations.trade_thesis IS 'Kurzer, aus realen Werten (Ticker, Richtung, Ausloeser-Evidenz) zusammengesetzter Text - kein KI-generierter freier Text.';
COMMENT ON COLUMN trading.recommendations.thesis_created_at IS 'Zeitpunkt der Eroeffnung, Basis fuer time_stop_at.';
COMMENT ON COLUMN trading.recommendations.time_stop_at IS 'thesis_created_at + deterministischer, strategie-abhaengiger Horizont (siehe docs/HARTE_VETOS.md und thesis_rule_version) - danach gilt die These automatisch als abgelaufen (thesis_expires_at wird auf denselben Wert gesetzt).';
COMMENT ON COLUMN trading.recommendations.invalidation_conditions_json IS 'Strukturierte, aus dem Signal abgeleitete Ungueltigkeits-Bedingungen (z.B. RSI-Rueckkehr in neutrale Zone bei Mean-Reversion), kein Freitext.';
COMMENT ON COLUMN trading.recommendations.thesis_rule_version IS 'Versionskennung der deterministischen Zeitstop-Regeln (aktuell "welle1-v1").';
