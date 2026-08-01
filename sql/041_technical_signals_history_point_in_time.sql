-- ============================================================================
-- 041 (Fehleranalyse B8, mittel, Haertungsauftrag 2026-08-02): echte
-- Point-in-Time-Semantik fuer trading.technical_signals_history
-- ============================================================================
-- Identisches Muster wie sql/022 (fundamentals_history) und sql/025
-- (stock_price_history): "INSERT ... ON CONFLICT (ticker, snapshot_date) DO
-- UPDATE" ueberschreibt bei einem zweiten "02"-Lauf am selben Tag die
-- technischen Signale des ersten Laufs ersatzlos - Verlust der
-- Revisionshistorie. Neues Modell: jede Schreibung fuer (ticker,
-- snapshot_date) legt eine neue Revision an statt die alte zu ueberschreiben.

ALTER TABLE trading.technical_signals_history
  ADD COLUMN IF NOT EXISTS known_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS revision_number INTEGER;

-- Backfill bestehender Zeilen: jede existierende Zeile ist bislang die einzige
-- (und damit aktuelle) Revision fuer ihren (ticker, snapshot_date).
UPDATE trading.technical_signals_history
SET known_at = fetched_at,
    valid_from = fetched_at,
    valid_to = NULL,
    revision_number = 1
WHERE revision_number IS NULL;

ALTER TABLE trading.technical_signals_history
  ALTER COLUMN known_at SET NOT NULL,
  ALTER COLUMN valid_from SET NOT NULL,
  ALTER COLUMN revision_number SET NOT NULL,
  ALTER COLUMN revision_number SET DEFAULT 1;

-- Alter Unique-Constraint (ticker, snapshot_date) erlaubte per Definition nur
-- eine Zeile - muss weg, bevor mehrere Revisionen moeglich sind.
ALTER TABLE trading.technical_signals_history
  DROP CONSTRAINT IF EXISTS uq_technical_signals_history_ticker_date;

ALTER TABLE trading.technical_signals_history
  ADD CONSTRAINT uq_technical_signals_history_ticker_date_revision UNIQUE (ticker, snapshot_date, revision_number);

-- Harte DB-Garantie: hoechstens eine "aktuelle" (valid_to IS NULL) Revision
-- je (ticker, snapshot_date).
CREATE UNIQUE INDEX IF NOT EXISTS uq_technical_signals_history_current
  ON trading.technical_signals_history (ticker, snapshot_date)
  WHERE valid_to IS NULL;

COMMENT ON COLUMN trading.technical_signals_history.known_at IS 'Zeitpunkt, ab dem dieser Wert dem System tatsaechlich bekannt war (identisches Konzept wie fundamentals_history.known_at, sql/022).';
COMMENT ON COLUMN trading.technical_signals_history.valid_from IS 'Beginn des Gueltigkeitszeitraums dieser Revision (i.d.R. == known_at bei dieser Tabelle).';
COMMENT ON COLUMN trading.technical_signals_history.valid_to IS 'Ende des Gueltigkeitszeitraums - NULL bedeutet "aktuell gueltig". Wird beim Anlegen der naechsten Revision fuer denselben (ticker, snapshot_date) gesetzt.';
COMMENT ON COLUMN trading.technical_signals_history.revision_number IS 'Fortlaufend je (ticker, snapshot_date), beginnend bei 1. Ersetzt das bisherige Ueberschreiben durch echte Historisierung.';

-- Wichtig fuer alle Konsumenten (06/07/10/13): nach dieser Migration koennen
-- mehrere Zeilen je (ticker, snapshot_date) existieren. Bestehende Queries
-- MUESSEN "AND valid_to IS NULL" ergaenzen, um weiterhin genau eine (die
-- aktuelle) Zeile je Tag zu erhalten - im selben Haertungsauftrag (B8) bereits
-- in allen vier lesenden Workflows nachgezogen.
