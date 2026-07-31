-- ============================================================================
-- Paket 18 (Phase 6 der fachlichen Ueberarbeitung): getrennte technische
-- Strategiesignale (Mean-Reversion, Trend-Following, Breakout)
-- ============================================================================
-- Additiv auf trading.technical_signals_history. Das bestehende kombinierte
-- Punktesystem (signal_punkte/signal_gruende/signal_staerke) bleibt
-- unveraendert bestehen (Rueckwaertskompatibilitaet) - die drei neuen JSONB-
-- Spalten machen zusaetzlich sichtbar, WELCHE Strategie-Familie mit welcher
-- Begruendung zu welchem Ergebnis kam, statt nur eines gemischten Gesamtscores.

ALTER TABLE trading.technical_signals_history
  ADD COLUMN IF NOT EXISTS mean_reversion_signal_json JSONB,
  ADD COLUMN IF NOT EXISTS trend_following_signal_json JSONB,
  ADD COLUMN IF NOT EXISTS breakout_signal_json JSONB,
  ADD COLUMN IF NOT EXISTS dominant_strategy TEXT;

COMMENT ON COLUMN trading.technical_signals_history.mean_reversion_signal_json IS 'Phase 6: {strategy, direction, raw_score, regime_fit, data_quality, expected_horizon_days, evidence[]}. Basis: RSI-Extremwerte + Bollinger-Band-Beruehrung + Abstand zu EMA20.';
COMMENT ON COLUMN trading.technical_signals_history.trend_following_signal_json IS 'Phase 6: gleiche Struktur. Basis: MACD-Kreuzung/Nulllinie/Histogramm-Richtung + EMA20-Trendbestaetigung.';
COMMENT ON COLUMN trading.technical_signals_history.breakout_signal_json IS 'Phase 6: gleiche Struktur. Basis: Naehe zum 52-Wochen-Hoch/-Tief + Volumenfaktor + Tagesbewegung.';
COMMENT ON COLUMN trading.technical_signals_history.dominant_strategy IS 'Welche der drei Strategien (mean_reversion/trend_following/breakout) den hoechsten raw_score hatte und damit als fuehrend fuer das kombinierte Signal gilt.';
