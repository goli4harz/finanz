-- ============================================================================
-- Welle 1, Arbeitspaket 2+3: Kerzenqualitaet + echte Mindest-Zeitraeume
-- ============================================================================
-- Ausgangsbefund (live gegen den FastAPI-Kursdienst geprueft, 2026-07-31):
-- "02 - Technische Signale taeglich" rief den Kursdienst bisher mit
-- period=3mo auf und filterte close/high/low/volume-Arrays UNABHAENGIG
-- voneinander (vier getrennte .filter()-Aufrufe) - beides real bestaetigte
-- Risiken aus dem Auftrag: (a) ein "52-Wochen-Hoch" konnte aus nur ~63
-- Handelstagen stammen, (b) fehlt an Tag X z.B. nur "high", verschieben sich
-- alle nachfolgenden Tage in high[] um eine Position gegenueber close[].
-- Meta-Feld fiftyTwoWeekHigh/-Low ist beim FastAPI-Dienst vorhanden (siehe
-- docs/DATENQUALITAET_UND_SESSIONS.md) und wird vom Code bereits bevorzugt -
-- das Risiko betrifft den Fallback-Pfad, wenn dieses Feld fehlt.
--
-- Diese Migration legt die Serien-Ebene der Datenqualitaet ab (war die
-- gesamte abgerufene Kurshistorie fuer diesen Ticker heute gut genug fuer
-- RSI/MACD/BB/ATR/Breakout?). Die Zeilen-Ebene (einzelne Kerze gueltig/
-- ungueltig) liegt bereits auf trading.stock_price_history (sql/025).

ALTER TABLE trading.technical_signals_history
  ADD COLUMN IF NOT EXISTS data_quality_status TEXT,
  ADD COLUMN IF NOT EXISTS data_quality_score  NUMERIC(5,2)
    CONSTRAINT chk_technical_signals_history_dq_score CHECK (data_quality_score IS NULL OR data_quality_score BETWEEN 0 AND 100),
  ADD COLUMN IF NOT EXISTS data_quality_issues_json JSONB,
  ADD COLUMN IF NOT EXISTS history_length_days INTEGER,
  ADD COLUMN IF NOT EXISTS breakout_history_ausreichend BOOLEAN,
  ADD COLUMN IF NOT EXISTS volatility_history_ausreichend BOOLEAN,
  ADD COLUMN IF NOT EXISTS kurzfrist_history_ausreichend BOOLEAN,
  ADD COLUMN IF NOT EXISTS session_status TEXT;

COMMENT ON COLUMN trading.technical_signals_history.data_quality_status IS 'Serien-Ebene (AP2), einer von: valid, limited, invalid, stale, session_incomplete. Ein hoher data_quality_score darf dieses harte Statusfeld NICHT ueberstimmen (Auftragsvorgabe) - Consumer muessen zuerst den Status pruefen.';
COMMENT ON COLUMN trading.technical_signals_history.data_quality_score IS 'Nachvollziehbarer 0-100-Score (informativ, ergaenzt aber ersetzt nicht data_quality_status).';
COMMENT ON COLUMN trading.technical_signals_history.data_quality_issues_json IS 'Array gefundener Probleme, z.B. ["abweichende_arraylaenge","negatives_volumen"] - Begruendung fuer den Status, keine freie KI-Bewertung.';
COMMENT ON COLUMN trading.technical_signals_history.history_length_days IS 'Anzahl der nach Zeilen-Pruefung als gueltig eingestuften Handelstage in dieser Kerzenserie (AP2).';
COMMENT ON COLUMN trading.technical_signals_history.breakout_history_ausreichend IS 'AP3: TRUE nur wenn >=252 gueltige Handelstage vorliegen. Ein Dreimonatsmaximum darf sonst nicht als 52-Wochen-Hoch/-Tief gelten - bei FALSE muss das Breakout-Signal dies als Grund benennen statt einen Ersatzwert als echtes 52-Wochen-Hoch auszugeben.';
COMMENT ON COLUMN trading.technical_signals_history.volatility_history_ausreichend IS 'AP3: TRUE nur wenn >=60 gueltige Handelstage vorliegen (fuer realized_vol_60d etc.).';
COMMENT ON COLUMN trading.technical_signals_history.kurzfrist_history_ausreichend IS 'AP3: TRUE nur wenn >=20 gueltige Handelstage vorliegen (RSI/MACD/kurzfristige Kennzahlen).';
COMMENT ON COLUMN trading.technical_signals_history.session_status IS 'AP4: Momentaufnahme aus trading.v_market_session_status (sql/027) zum Lauf-Zeitpunkt - closed_complete/open_intraday/holiday/unknown/stale.';
