-- ============================================================================
-- Experimentierplattform, Punkt 4: Point-in-Time-Semantik fuer
-- trading.market_context_history
-- ============================================================================
-- Identisches Muster wie sql/022 (fundamentals_history) und sql/041
-- (technical_signals_history) - die einzige der drei urspruenglichen
-- "History"-Tabellen aus sql/018, die bei der Revisions-Nachruestung 2025
-- ausgelassen wurde (siehe EXPERIMENT_PLATFORM_REVIEW.md, Risiko 4). Bisher:
-- "INSERT ... ON CONFLICT (symbol, snapshot_date) DO UPDATE" in Workflow 02b
-- ueberschreibt bei einem zweiten Lauf am selben Tag den Marktkontext des
-- ersten Laufs ersatzlos. Neues Modell: jede Schreibung fuer (symbol,
-- snapshot_date) legt eine neue Revision an statt die alte zu ueberschreiben.

ALTER TABLE trading.market_context_history
  ADD COLUMN IF NOT EXISTS known_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS revision_number INTEGER;

-- Backfill bestehender Zeilen: jede existierende Zeile ist bislang die einzige
-- (und damit aktuelle) Revision fuer ihren (symbol, snapshot_date).
UPDATE trading.market_context_history
SET known_at = fetched_at,
    valid_from = fetched_at,
    valid_to = NULL,
    revision_number = 1
WHERE revision_number IS NULL;

ALTER TABLE trading.market_context_history
  ALTER COLUMN known_at SET NOT NULL,
  ALTER COLUMN valid_from SET NOT NULL,
  ALTER COLUMN revision_number SET NOT NULL,
  ALTER COLUMN revision_number SET DEFAULT 1;

-- Alter Unique-Constraint (symbol, snapshot_date) erlaubte per Definition nur
-- eine Zeile - muss weg, bevor mehrere Revisionen moeglich sind.
ALTER TABLE trading.market_context_history
  DROP CONSTRAINT IF EXISTS uq_market_context_history_symbol_date;

ALTER TABLE trading.market_context_history
  ADD CONSTRAINT uq_market_context_history_symbol_date_revision UNIQUE (symbol, snapshot_date, revision_number);

-- Harte DB-Garantie: hoechstens eine "aktuelle" (valid_to IS NULL) Revision
-- je (symbol, snapshot_date).
CREATE UNIQUE INDEX IF NOT EXISTS uq_market_context_history_current
  ON trading.market_context_history (symbol, snapshot_date)
  WHERE valid_to IS NULL;

COMMENT ON COLUMN trading.market_context_history.known_at IS 'Zeitpunkt, ab dem dieser Wert dem System tatsaechlich bekannt war (identisches Konzept wie fundamentals_history.known_at, sql/022).';
COMMENT ON COLUMN trading.market_context_history.valid_from IS 'Beginn des Gueltigkeitszeitraums dieser Revision (i.d.R. == known_at bei dieser Tabelle).';
COMMENT ON COLUMN trading.market_context_history.valid_to IS 'Ende des Gueltigkeitszeitraums - NULL bedeutet "aktuell gueltig". Wird beim Anlegen der naechsten Revision fuer denselben (symbol, snapshot_date) gesetzt.';
COMMENT ON COLUMN trading.market_context_history.revision_number IS 'Fortlaufend je (symbol, snapshot_date), beginnend bei 1. Ersetzt das bisherige Ueberschreiben durch echte Historisierung.';

-- Wichtig fuer alle Konsumenten (06/07/10): nach dieser Migration koennen
-- mehrere Zeilen je (symbol, snapshot_date) existieren. Bestehende Queries
-- MUESSEN "AND valid_to IS NULL" ergaenzen, um weiterhin genau eine (die
-- aktuelle) Zeile je Tag zu erhalten - im selben Zug bereits in allen drei
-- lesenden Workflows nachgezogen (siehe Commit dieser Migration).
