-- ============================================================================
-- Paket 16 (Phase 7 der fachlichen Ueberarbeitung): ATR, realisierte
-- Volatilitaet, durchschnittliche Tagesrange + ATR-basierte Stop/Ziel-Werte
-- ============================================================================
-- Additiv auf trading.technical_signals_history (sql/018). Bestehende
-- ziel_kurs/stop_kurs ("legacy") bleiben unveraendert bestehen - siehe
-- legacy_stop_numeric/legacy_target_numeric als reine Numerik-Spiegelung
-- derselben Werte, plus die neuen ATR-basierten Alternativwerte daneben.

ALTER TABLE trading.technical_signals_history
  ADD COLUMN IF NOT EXISTS atr_14_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS realized_vol_20d_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS realized_vol_60d_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS avg_daily_range_14_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS legacy_stop_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS legacy_target_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS atr_stop_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS atr_target_numeric NUMERIC;

COMMENT ON COLUMN trading.technical_signals_history.atr_14_numeric IS 'Average True Range, 14 Tage, Wilder-Glaettung. NULL bei unzureichender Historie (< 15 Tage High/Low/Close), nie geraten.';
COMMENT ON COLUMN trading.technical_signals_history.realized_vol_20d_numeric IS 'Annualisierte realisierte Volatilitaet aus taeglichen Log-Returns, 20-Tage-Fenster.';
COMMENT ON COLUMN trading.technical_signals_history.realized_vol_60d_numeric IS 'Annualisierte realisierte Volatilitaet aus taeglichen Log-Returns, 60-Tage-Fenster.';
COMMENT ON COLUMN trading.technical_signals_history.avg_daily_range_14_numeric IS 'Durchschnittliche Tagesrange (High-Low, kein True Range), 14-Tage-Fenster.';
COMMENT ON COLUMN trading.technical_signals_history.legacy_stop_numeric IS 'Numerische Spiegelung des bestehenden stop_kurs (EMA20/Bollinger-basiert) - kein neuer Wert, nur Rohwert-Form des bereits vorhandenen Textfelds.';
COMMENT ON COLUMN trading.technical_signals_history.legacy_target_numeric IS 'Numerische Spiegelung des bestehenden ziel_kurs - kein neuer Wert, nur Rohwert-Form.';
COMMENT ON COLUMN trading.technical_signals_history.atr_stop_numeric IS 'ATR-basierter Stop: Einstieg -/+ 1.5x ATR-14 (long/short). NULL wenn atr_14_numeric NULL oder richtung neutral.';
COMMENT ON COLUMN trading.technical_signals_history.atr_target_numeric IS 'ATR-basiertes Ziel: Einstieg +/- 2.5x ATR-14 (long/short). NULL wenn atr_14_numeric NULL oder richtung neutral.';
