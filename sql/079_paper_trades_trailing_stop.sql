-- ============================================================================
-- WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): Trailing-Stop-Felder
-- auf trading.paper_trades - bisher nur auf simulation_trades (sql/059) vorhanden.
-- ============================================================================
-- Ohne diese Spalten kann der Trailing-Stop sein "Gedaechtnis" nicht ueber
-- mehrere Tage hinweg speichern (jeder Job-B-Lauf wuerde bei Null anfangen).
-- Gleiche Bedeutung wie bei simulation_trades: extreme_price_since_entry wird
-- fuer JEDE Strategie mitgefuehrt und persistiert, trail_distance wird beim
-- Fill einmalig aus |entry_price - stop_price_current| abgeleitet und danach
-- nie mehr veraendert (siehe execution.py::fill_order()/update_trailing_stop()).
--
-- Beide Spalten sind NULLABLE: der alte Job-B-Pfad (Flag FALSE) kennt sie
-- nicht und schreibt sie nie - kein Verhaltensunterschied fuer bereits
-- bestehende/zukuenftige Trades ueber den alten Pfad.

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS extreme_price_since_entry NUMERIC,
  ADD COLUMN IF NOT EXISTS trail_distance NUMERIC;

COMMENT ON COLUMN trading.paper_trades.extreme_price_since_entry IS
  'Meistguenstigster Kurs seit Entry (long: Hoechststand, short: Tiefststand) - '
  'wird fuer JEDE Strategie mitgefuehrt/persistiert, unabhaengig davon ob der Stop '
  'tatsaechlich nachgezogen wird (siehe trading_engine/execution.py::update_trailing_stop, '
  'nur trend_following/breakout ziehen den Stop tatsaechlich nach). NULL = Trade wurde '
  'nie ueber den Engine-Pfad (TRADING_ENGINE_EXECUTION_ENABLED=TRUE) verarbeitet.';
COMMENT ON COLUMN trading.paper_trades.trail_distance IS
  'Einmalig beim Fill abgeleitet aus |simulated_entry_price - stop_price_current| '
  '(nach Anwendung des 10%-Hard-Stop-Caps) - bleibt danach fuer die Laufzeit des '
  'Trades konstant. NULL = Trade wurde nie ueber den Engine-Pfad verarbeitet.';

-- Einmaliger Backfill fuer bereits bestehende offene/vorgeschlagene Trades, damit der
-- Engine-Pfad beim ersten Einschalten des Flags nicht bei NULL/0 startet (der neue
-- Engine-Node hat zusaetzlich eine defensive Fallback-Ableitung fuer den Fall, dass
-- dieser Backfill je einen Trade uebersehen hat - siehe "Job B: Ausfuehrung/Exit
-- simulieren (Engine)").
UPDATE trading.paper_trades
SET
  extreme_price_since_entry = COALESCE(simulated_entry_price, planned_entry_zone_low),
  trail_distance = ABS(COALESCE(simulated_entry_price, planned_entry_zone_low) - stop_price_initial)
WHERE status IN ('open', 'proposed')
  AND extreme_price_since_entry IS NULL
  AND COALESCE(simulated_entry_price, planned_entry_zone_low) IS NOT NULL
  AND stop_price_initial IS NOT NULL;

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('079', 'extreme_price_since_entry + trail_distance auf paper_trades fuer Job-B-Trailing-Stop (WF14-Migration)')
ON CONFLICT (version) DO NOTHING;
