-- ============================================================================
-- Paket 13 (Phase 5, Schritt 2 von 2): echte Point-in-Time-Semantik fuer
-- trading.fundamentals_history
-- ============================================================================
-- Schritt 1 (sql/021) hat die Rohwert/Anzeigeformat-Trennung gebracht, aber die
-- Tabelle war weiterhin ein reiner Tages-Cache: "INSERT ... ON CONFLICT
-- (ticker, snapshot_date) DO UPDATE" ueberschreibt bei jedem erneuten Lauf fuer
-- denselben Tag den vorherigen Wert ersatzlos - live bestaetigt (heutige
-- manuelle Testlaeufe haben denselben Tag mehrfach ueberschrieben). Verstoesst
-- direkt gegen die Auftragsvorgabe "Spaetere Korrekturen duerfen fruehere
-- Werte nicht ueberschreiben".
--
-- Neues Modell: jede Schreibung fuer (ticker, snapshot_date) legt eine neue
-- Revision an statt die alte zu ueberschreiben. known_at/valid_from markieren,
-- wann diese Revision galt; valid_to wird beim Anlegen der NAECHSTEN Revision
-- auf deren known_at gesetzt (vorherige Revision damit "geschlossen"). Genau
-- eine Revision je (ticker, snapshot_date) hat valid_to IS NULL ("aktuell").

ALTER TABLE trading.fundamentals_history
  ADD COLUMN IF NOT EXISTS known_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS valid_to TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS revision_number INTEGER;

-- Backfill bestehender Zeilen: jede existierende Zeile ist bislang die einzige
-- (und damit aktuelle) Revision fuer ihren (ticker, snapshot_date).
UPDATE trading.fundamentals_history
SET known_at = fetched_at,
    valid_from = fetched_at,
    valid_to = NULL,
    revision_number = 1
WHERE revision_number IS NULL;

ALTER TABLE trading.fundamentals_history
  ALTER COLUMN known_at SET NOT NULL,
  ALTER COLUMN valid_from SET NOT NULL,
  ALTER COLUMN revision_number SET NOT NULL,
  ALTER COLUMN revision_number SET DEFAULT 1;

-- Alter Unique-Constraint (ticker, snapshot_date) erlaubte per Definition nur
-- eine Zeile - muss weg, bevor mehrere Revisionen moeglich sind.
ALTER TABLE trading.fundamentals_history
  DROP CONSTRAINT IF EXISTS uq_fundamentals_history_ticker_date;

ALTER TABLE trading.fundamentals_history
  ADD CONSTRAINT uq_fundamentals_history_ticker_date_revision UNIQUE (ticker, snapshot_date, revision_number);

-- Harte DB-Garantie: hoechstens eine "aktuelle" (valid_to IS NULL) Revision
-- je (ticker, snapshot_date) - verhindert, dass ein fehlerhafter Schreibpfad
-- zwei gleichzeitig "gueltige" Werte fuer denselben Tag erzeugt.
CREATE UNIQUE INDEX IF NOT EXISTS uq_fundamentals_history_current
  ON trading.fundamentals_history (ticker, snapshot_date)
  WHERE valid_to IS NULL;

COMMENT ON COLUMN trading.fundamentals_history.known_at IS 'Zeitpunkt, ab dem dieser Wert dem System tatsaechlich bekannt war (Phase-5/12-Konzept "known_at != published_at").';
COMMENT ON COLUMN trading.fundamentals_history.valid_from IS 'Beginn des Gueltigkeitszeitraums dieser Revision (i.d.R. == known_at bei dieser Tabelle).';
COMMENT ON COLUMN trading.fundamentals_history.valid_to IS 'Ende des Gueltigkeitszeitraums - NULL bedeutet "aktuell gueltig". Wird beim Anlegen der naechsten Revision fuer denselben (ticker, snapshot_date) gesetzt.';
COMMENT ON COLUMN trading.fundamentals_history.revision_number IS 'Fortlaufend je (ticker, snapshot_date), beginnend bei 1. Ersetzt das bisherige Ueberschreiben durch echte Historisierung.';
