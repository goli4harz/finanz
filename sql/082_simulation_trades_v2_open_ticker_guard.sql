-- ============================================================================
-- 082 - Notbremse gegen doppelt offene Positionen desselben Tickers, NUR fuer
-- historische-simulation-v2. WF17-v2-Reparatur (Sitzungsdiagnose 2026-09-06).
-- ============================================================================
-- Die Anwendungslogik (isOccupied() in "Verarbeite Tage-Paket") verhindert das
-- bereits VOR jeder Order-Erzeugung - dieser Index ist die letzte Notbremse auf
-- DB-Ebene, kein normaler Kontrollfluss. Ein Unique-Violation hier waere ein
-- Bug in der Anwendungslogik, kein erwarteter Zustand.
--
-- Bewusst per WHERE auf data_schema_version='historische-simulation-v2'
-- beschraenkt: alle bekannten v1-Laeufe (17/21/22/25, siehe Migration 081)
-- verletzen genau diese Invariante bereits real und bleiben unangetastet -
-- ein ungescopter Index wuerde diese Migration sofort mit einem
-- Unique-Violation-Fehler abbrechen lassen.
--
-- Vorher-Check (2026-09-06, gegen die Live-DB durchgefuehrt): 0 Zeilen mit
-- data_schema_version='historische-simulation-v2' existieren - die Migration
-- kann daher gefahrlos angewendet werden, sobald sie ausgefuehrt wird.
-- ============================================================================

BEGIN;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM trading.simulation_trades
    WHERE data_schema_version = 'historische-simulation-v2'
    GROUP BY simulation_run_id, ticker
    HAVING COUNT(*) FILTER (WHERE status = 'open') > 1
  ) THEN
    RAISE EXCEPTION 'Migration 082 abgebrochen: bereits vorhandene v2-Daten verletzen die neue Invariante (>1 offener Trade je Run+Ticker). Manuell pruefen vor erneutem Versuch.';
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS ux_simulation_trades_one_open_per_ticker_v2
  ON trading.simulation_trades (simulation_run_id, ticker)
  WHERE status = 'open' AND data_schema_version = 'historische-simulation-v2';

COMMENT ON INDEX trading.ux_simulation_trades_one_open_per_ticker_v2 IS
  'Notbremse (nicht der normale Kontrollfluss) - erzwingt fuer v2-Laeufe: maximal ein offener '
  'Trade je (simulation_run_id, ticker). Die Anwendungslogik (isOccupied()) muss dies bereits '
  'vor der Order-Erzeugung verhindern; ein Verstoss hier zeigt einen Bug in der Anwendung an. '
  'Bewusst NICHT auf v1-Daten angewendet (WHERE data_schema_version=...v2), da mehrere bekannte '
  'v1-Laeufe (siehe trading.simulation_run_validation) diese Invariante bereits real verletzen.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('082', 'Partieller Unique-Index gegen doppelt offene Positionen desselben Tickers, beschraenkt auf historische-simulation-v2 - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
