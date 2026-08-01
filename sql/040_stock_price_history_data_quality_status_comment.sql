-- 040: Dokumentations-Korrektur (C6, Haertungsauftrag 2026-08-01).
-- trading.stock_price_history.data_quality_status ist eine reine TEXT-Spalte
-- ohne CHECK-Constraint (siehe sql/025) - keine Schema-Aenderung noetig, nur
-- der Spaltenkommentar war seit sql/025 veraltet: er beschrieb ein 2-Zustands-
-- Feld (valid/invalid je Kerze), obwohl "02b" (seit C4/C5, 2026-08-01) und
-- jetzt auch "02" (seit C6, 2026-08-01) hier bereits den vollen 5-Zustands-
-- Seriencode (valid/limited/invalid/stale/session_incomplete) schreiben, damit
-- Konsumenten wie "14" (siehe C9) eine laufende Sitzung oder veraltete Kerze
-- erkennen koennen.
COMMENT ON COLUMN trading.stock_price_history.data_quality_status IS 'Seit C6/C9 (Haertungsauftrag 2026-08-01): voller Serien-Status je Kerze, einer von valid/limited/invalid/stale/session_incomplete (nicht mehr nur valid/invalid). Wird von "02"/"02b" beim Schreiben unveraendert durchgereicht (Quelle: technical_signal.dataQualityStatus). Konsumenten (u.a. "14") muessen alle fuenf Werte behandeln, nicht nur valid/invalid.';
