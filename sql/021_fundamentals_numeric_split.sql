-- ============================================================================
-- Paket 13 (Phase 5 der fachlichen Ueberarbeitung, Schritt 1 von 2):
-- Rohwert/Anzeigeformat-Trennung fuer trading.fundamentals_history
-- ============================================================================
-- docs/PHASENWEISER_ABGLEICH_2026-07-31.md hatte Phase 5 als groessten
-- Einzelbefund markiert: fundamentals_history (sql/018) speichert bislang
-- ausschliesslich formatierte Anzeige-Strings ("16.3", "16.3 Mrd.", "16.3%"),
-- obwohl der lokale FastAPI-Dienst (siehe "01 - Fundamentaldaten taeglich",
-- Node "Fundamentaldaten aufbereiten & speichern") die Werte bereits sauber
-- numerisch liefert - die Formatierung/Rundung passiert erst beim Schreiben.
--
-- Additiv, rueckwaertskompatibel: alle bisherigen TEXT-Spalten bleiben
-- unveraendert (Data Table + bestehende Consumer unberuehrt). Numerik-Spalten
-- speichern den Rohwert exakt so, wie ihn FastAPI liefert - OHNE die spaeter
-- angewandte Anzeige-Transformation (z.B. eigenkapitalrendite/gewinnmarge als
-- Dezimalbruch 0.163 statt der Anzeige "16.3%"; marktkapitalisierung als
-- vollstaendige Zahl statt durch 1e9 geteilter "Mrd."-Wert).
--
-- Bewusst NICHT Teil dieses Schritts (folgt als Schritt 2, eigene
-- Nutzerentscheidung noetig): known_at/valid_from/valid_to/revision_number
-- und eine Aenderung der bestehenden ON-CONFLICT-Ueberschreib-Logik.

ALTER TABLE trading.fundamentals_history
  ADD COLUMN IF NOT EXISTS currency TEXT,
  ADD COLUMN IF NOT EXISTS kgv_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS kgv_forward_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS kbv_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS dividende_rendite_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS dividende_je_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS beta_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS marktkapitalisierung_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS verschuldungsgrad_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS eigenkapitalrendite_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS gewinnmarge_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS kursziel_numeric NUMERIC,
  ADD COLUMN IF NOT EXISTS regular_market_price_numeric NUMERIC;

COMMENT ON COLUMN trading.fundamentals_history.currency IS 'Waehrung des Tickers laut FastAPI (raw.currency), z.B. EUR/USD - gilt fuer alle *_numeric-Waehrungsfelder dieser Zeile (dividende_je_numeric, kursziel_numeric, regular_market_price_numeric).';
COMMENT ON COLUMN trading.fundamentals_history.dividende_rendite_numeric IS 'Rohwert wie von FastAPI geliefert, bereits in Prozentpunkten (z.B. 1.65 = 1.65%), NICHT als Dezimalbruch.';
COMMENT ON COLUMN trading.fundamentals_history.eigenkapitalrendite_numeric IS 'Rohwert wie von FastAPI geliefert, als Dezimalbruch (z.B. 0.163 = 16.3%) - Anzeigeformat multipliziert mit 100 fuer Prozentdarstellung.';
COMMENT ON COLUMN trading.fundamentals_history.gewinnmarge_numeric IS 'Rohwert wie von FastAPI geliefert, als Dezimalbruch (z.B. 0.195 = 19.5%) - Anzeigeformat multipliziert mit 100 fuer Prozentdarstellung.';
COMMENT ON COLUMN trading.fundamentals_history.verschuldungsgrad_numeric IS 'Rohwert wie von FastAPI geliefert, bereits in Prozentpunkten (z.B. 17.3 = 17.3%), NICHT als Dezimalbruch.';
COMMENT ON COLUMN trading.fundamentals_history.marktkapitalisierung_numeric IS 'Vollstaendiger Rohwert in Basiswaehrungseinheiten (z.B. 45300000000), NICHT durch 1e9 geteilt wie das Anzeigeformat "45.3 Mrd.".';
