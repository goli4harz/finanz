-- ============================================================================
-- Paket 5 (Phase 10b der fachlichen Ueberarbeitung): Markt-/Session-Referenzdaten
-- ============================================================================
-- Schafft statische Referenzdaten fuer Markt/Zeitzone/Handelszeiten, OHNE heute
-- schon eine Verhaltensaenderung zu erzwingen. Kein Workflow-Node wird in diesem
-- Paket geaendert.
--
-- Einordnung (nicht in der urspruenglichen Bestandsaufnahme so benannt): die
-- aktuelle Watchlist (sql/002_seed_stock_instruments.sql) besteht ausschliesslich
-- aus .DE-Tickern (XETRA, schliesst 17:30 CET). Der Orchestrator laeuft 17:50 CET -
-- das im Auftrag beschriebene Risiko "US-Markt evtl. noch offen um 17:50 Uhr" ist
-- fuer den HEUTIGEN Bestand nicht aktiv, sondern reine Vorwaertsabsicherung fuer
-- kuenftige nicht-europaeische Ticker.

CREATE TABLE IF NOT EXISTS trading.market_reference (
    market_code         TEXT PRIMARY KEY,
    exchange_timezone    TEXT NOT NULL,
    session_open_local   TIME,
    session_close_local  TIME,
    trading_days_iso     SMALLINT[] NOT NULL DEFAULT '{1,2,3,4,5}',
    notes                TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE trading.market_reference IS
    'Statische Markt-/Session-Referenzdaten (Zeitzone, Handelszeiten). Aktuell von '
    'keinem Workflow gelesen - Vorwaertsabsicherung fuer kuenftige nicht-europaeische '
    'Ticker, siehe Kommentar oben.';

INSERT INTO trading.market_reference (market_code, exchange_timezone, session_open_local, session_close_local, trading_days_iso, notes)
VALUES
    ('XETRA', 'Europe/Berlin',    '09:00', '17:30', '{1,2,3,4,5}', 'Deutsche Boerse XETRA - aktueller Bestand, alle 15 Watchlist-Ticker'),
    ('NASDAQ', 'America/New_York','09:30', '16:00', '{1,2,3,4,5}', 'Referenzindex in 02b, aktuell kein Watchlist-Ticker dort gelistet'),
    ('NYSE',   'America/New_York','09:30', '16:00', '{1,2,3,4,5}', 'Referenzindex in 02b, aktuell kein Watchlist-Ticker dort gelistet')
ON CONFLICT (market_code) DO NOTHING;

-- stock_instruments.exchange ist fuer alle 15 Bestandsticker aktuell NULL (kein
-- Consumer liest die Spalte aktiv, Backfill ist damit inert/sicher).
UPDATE trading.stock_instruments SET exchange = 'XETRA' WHERE exchange IS NULL;

-- Schema-only, von keinem Workflow in diesem Paket befuellt - gleiches Muster wie
-- confirmation_status in Migration 012 (Feld vorbereitet, Wiring separat).
ALTER TABLE trading.pipeline_runs ADD COLUMN IF NOT EXISTS market_session_snapshot JSONB;

COMMENT ON COLUMN trading.pipeline_runs.market_session_snapshot IS
    'Vorbereitet fuer eine kuenftige Momentaufnahme (welche Maerkte zum Laufzeitpunkt '
    'noch offen waren). Aktuell schema-only, kein Workflow befuellt dieses Feld.';
