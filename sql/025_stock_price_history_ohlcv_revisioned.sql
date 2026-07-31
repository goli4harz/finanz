-- ============================================================================
-- Welle 1, Arbeitspaket 1: vollstaendige OHLCV-Historie mit Revisionierung
-- ============================================================================
-- Ausgangsbefund (live gegen den FastAPI-Kursdienst und den echten Code
-- geprueft, 2026-07-31): trading.stock_price_history hatte bereits die Spalten
-- open/high/low/close/volume/currency (sql/004), aber "02 - Technische Signale
-- taeglich"s "Kurshistorie: SQL bauen" schrieb NUR close+source, "02b -
-- Marktumfeld taeglich" nur close+currency+source. open/high/low/volume waren
-- vorhanden im Schema, aber nie befuellt. Zusaetzlich: ON CONFLICT (symbol,
-- trading_date) DO UPDATE ueberschrieb den Vortageswert ohne jede Revision -
-- exakt das im Auftrag benannte Risiko ("keine Ueberschreibung ohne
-- nachvollziehbare Revision").
--
-- Loesung: additive Spalten (adjusted_close, exchange, source_timestamp,
-- revision_number, valid_from, valid_to, data_quality_status) plus Umstellung
-- von ON CONFLICT DO UPDATE auf das bereits fuer fundamentals_history bewaehrte
-- Muster (sql/022): aktuelle Revision schliessen (valid_to=now()), neue Zeile
-- anlegen. known_at/session_date/data_source aus dem Auftrag werden NICHT als
-- neue, redundante Spalten angelegt, sondern auf die bereits vorhandenen
-- Spalten fetched_at/trading_date/source abgebildet (siehe Spaltenkommentare) -
-- diese haben exakt dieselbe Bedeutung, ein Duplikat waere nur Verwirrung.

ALTER TABLE trading.stock_price_history
  ADD COLUMN IF NOT EXISTS adjusted_close   NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS exchange         TEXT,
  ADD COLUMN IF NOT EXISTS source_timestamp TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS revision_number  INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS valid_from       TIMESTAMPTZ NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS valid_to         TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS data_quality_status TEXT;

COMMENT ON COLUMN trading.stock_price_history.trading_date IS 'Entspricht "session_date" aus dem Auftrag: der Boersensitzungstag der Kerze (nicht der Abrufzeitpunkt).';
COMMENT ON COLUMN trading.stock_price_history.fetched_at IS 'Entspricht "known_at" aus dem Auftrag: Zeitpunkt, zu dem WIR diesen Wert erfahren haben (Abrufzeitpunkt), nicht der Handelszeitpunkt selbst.';
COMMENT ON COLUMN trading.stock_price_history.source IS 'Entspricht "data_source" aus dem Auftrag: schreibender Workflow/Herkunft (z.B. "technische-signale-02").';
COMMENT ON COLUMN trading.stock_price_history.adjusted_close IS 'Dividenden-/Split-bereinigter Schlusskurs, NULL wenn die Quelle (lokaler FastAPI-Kursdienst) ihn nicht liefert (aktuell der Fall, siehe docs/DATENQUALITAET_UND_SESSIONS.md) - kein Ersatzwert, keine Naeherung.';
COMMENT ON COLUMN trading.stock_price_history.exchange IS 'Boersenkuerzel (z.B. XETRA) aus trading.stock_instruments.exchange zum Schreibzeitpunkt, NICHT von der Kursquelle geliefert. NULL fuer Nicht-Aktien-Symbole aus 02b (Indizes/FX), die keinen stock_instruments-Eintrag haben.';
COMMENT ON COLUMN trading.stock_price_history.source_timestamp IS 'Der von der Kursquelle fuer diese Kerze gemeldete Zeitstempel (Sitzungsende), zur Unterscheidung von fetched_at (wann WIR es abgerufen haben).';
COMMENT ON COLUMN trading.stock_price_history.revision_number IS 'Point-in-Time-Revisionierung wie fundamentals_history (sql/022): jede erneute Schreibung fuer denselben Handelstag schliesst die vorherige Revision statt sie zu ueberschreiben.';
COMMENT ON COLUMN trading.stock_price_history.data_quality_status IS 'Zeilen-Ebene (AP2): valid/invalid je Kerze, aus den Row-Checks (High<Low, Open/Close ausserhalb High/Low, negatives Volumen, fehlender Close). Die Serien-Ebene (genug Historie fuer Breakout/Vola) steht auf trading.technical_signals_history, siehe sql/026.';

-- Bestehende Zeilen als Revision 1 abschliessen/markieren: sie hatten nur
-- close (kein open/high/low), sind also im neuen Sinn 'limited', nicht 'valid'.
UPDATE trading.stock_price_history
   SET revision_number = 1,
       valid_from = fetched_at,
       valid_to = NULL,
       data_quality_status = 'limited'
 WHERE revision_number IS NULL OR data_quality_status IS NULL;

-- Alte Eindeutigkeit (symbol, trading_date) ersetzen durch eine, die mehrere
-- Revisionen desselben Tages zulaesst, aber weiterhin genau eine "aktuelle"
-- Revision je Tag erzwingt (identisches Muster zu sql/022).
ALTER TABLE trading.stock_price_history
  DROP CONSTRAINT IF EXISTS uq_stock_price_history_symbol_date;

ALTER TABLE trading.stock_price_history
  ADD CONSTRAINT uq_stock_price_history_symbol_date_revision
    UNIQUE (symbol, trading_date, revision_number);

CREATE UNIQUE INDEX IF NOT EXISTS uq_stock_price_history_current
  ON trading.stock_price_history (symbol, trading_date)
  WHERE valid_to IS NULL;

-- Bestehende Leser (08 - News-Wirkungsanalyse, 07 - Status-Uebersicht) muessen
-- nach dieser Migration "AND valid_to IS NULL" ergaenzen, sonst sehen sie ab
-- der ersten echten Revision doppelte Zeilen pro Tag - wird im selben Paket
-- am Code der beiden Workflows nachgezogen (nicht Teil dieser SQL-Datei).
