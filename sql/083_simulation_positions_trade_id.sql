-- ============================================================================
-- 083 - trading.simulation_positions: trade_id als fachlich korrekter
-- Konfliktschluessel statt (run_id, ticker, date). WF17-v2-Reparatur.
-- ============================================================================
-- PROBLEM: die bestehende UNIQUE(simulation_run_id, ticker, simulated_date)
-- kann mehrere gleichzeitig offene Lots desselben Tickers nicht abbilden - das
-- INSERT ... ON CONFLICT (run_id,ticker,date) DO UPDATE in "Baue SQL fuer
-- Paket-Ergebnisse" ueberschreibt in genau diesem Fall eine Positionszeile mit
-- der naechsten (bewiesen an Run 25/ALV.DE: zwei gleichzeitig offene Lots,
-- simulation_positions zeigt nur die zuletzt geschriebene Zeile).
--
-- VORHER dokumentierter Ist-Zustand (2026-09-06, gegen die Live-DB geprueft):
--   Spalten: id, simulation_run_id, ticker, simulated_date, quantity,
--            average_cost_basis, mark_price, unrealized_pnl,
--            corporate_action_adjustment_json, created_at
--            (kein trade_id, kein data_schema_version)
--   Indizes: simulation_positions_pkey (id),
--            simulation_positions_simulation_run_id_ticker_simulated_dat_key
--              UNIQUE (simulation_run_id, ticker, simulated_date),
--            ix_simulation_positions_run_date (simulation_run_id, simulated_date)
--   Constraints: PRIMARY KEY (id), UNIQUE (simulation_run_id, ticker, simulated_date),
--                FOREIGN KEY (simulation_run_id) REFERENCES backtest_runs(id)
--
-- NACHHER (durch diese Migration):
--   + Spalte trade_id (TEXT, nullable - v1-Altzeilen bleiben NULL wo nicht
--     eindeutig rekonstruierbar, siehe Backfill unten)
--   + Spalte data_schema_version (TEXT, nullable - Altzeilen auf
--     'historische-simulation-v1' zurueckdatiert, da alle vor dieser Migration
--     entstanden sind)
--   - alte UNIQUE(run_id,ticker,date) entfernt (DROP CONSTRAINT, KEINE
--     Datenloeschung - nur die Eindeutigkeitsregel wird geaendert)
--   + neue UNIQUE(run_id,trade_id,date) - mehrere NULL-trade_id-Zeilen pro
--     (run,date) bleiben gemaess SQL-Standard erlaubt (NULL gilt nicht als
--     Duplikat), betrifft nur nicht rekonstruierbare v1-Altzeilen
--   + CHECK: jede Zeile mit data_schema_version='historische-simulation-v2'
--     MUSS trade_id gesetzt haben - erzwingt fachlich korrekte v2-Zeilen auf
--     DB-Ebene, ohne v1-Zeilen zu beruehren (die bleiben auf 'v1' markiert und
--     sind von diesem CHECK nicht betroffen)
--
-- BACKFILL-PRINZIP: trade_id wird fuer bestehende Zeilen NUR gesetzt, wenn zu
-- (simulation_run_id, ticker, simulated_date) GENAU EIN offener Trade existiert,
-- dessen Zeitfenster den Tag abdeckt (simulated_entry_time::date <= simulated_date
-- AND (exit_time IS NULL OR exit_time::date >= simulated_date)). Mehrdeutige
-- Faelle (z.B. die bewiesene ALV.DE-Ueberlappung in Run 25) bleiben bewusst
-- NULL - keine erfundenen IDs, wie ausdruecklich gefordert.
-- ============================================================================

BEGIN;

ALTER TABLE trading.simulation_positions
  ADD COLUMN IF NOT EXISTS trade_id TEXT,
  ADD COLUMN IF NOT EXISTS data_schema_version TEXT;

UPDATE trading.simulation_positions
SET data_schema_version = 'historische-simulation-v1'
WHERE data_schema_version IS NULL;

-- Eindeutiges Backfill: nur wo GENAU EIN passender Trade existiert.
WITH candidates AS (
  SELECT
    sp.id AS position_id,
    t.trade_id AS candidate_trade_id,
    COUNT(*) OVER (PARTITION BY sp.id) AS match_count
  FROM trading.simulation_positions sp
  JOIN trading.simulation_trades t
    ON t.simulation_run_id = sp.simulation_run_id
   AND t.ticker = sp.ticker
   AND t.simulated_entry_time::date <= sp.simulated_date
   AND (t.exit_time IS NULL OR t.exit_time::date >= sp.simulated_date)
  WHERE sp.trade_id IS NULL
)
UPDATE trading.simulation_positions sp
SET trade_id = c.candidate_trade_id
FROM candidates c
WHERE c.position_id = sp.id
  AND c.match_count = 1;

ALTER TABLE trading.simulation_positions
  DROP CONSTRAINT IF EXISTS simulation_positions_simulation_run_id_ticker_simulated_dat_key;

ALTER TABLE trading.simulation_positions
  ADD CONSTRAINT ux_simulation_positions_run_trade_date UNIQUE (simulation_run_id, trade_id, simulated_date);

ALTER TABLE trading.simulation_positions
  ADD CONSTRAINT chk_simulation_positions_v2_trade_id
  CHECK (data_schema_version IS DISTINCT FROM 'historische-simulation-v2' OR trade_id IS NOT NULL);

COMMENT ON COLUMN trading.simulation_positions.trade_id IS
  'Fachlicher Schluessel je Lot/Position (entspricht simulation_trades.trade_id). NULL nur bei '
  'v1-Altzeilen, wo zu (run,ticker,date) nicht eindeutig genau ein Trade rekonstruierbar war '
  '(z.B. ueberlappende Positionen, siehe trading.simulation_run_validation). Fuer '
  'historische-simulation-v2 durch chk_simulation_positions_v2_trade_id verpflichtend.';
COMMENT ON CONSTRAINT ux_simulation_positions_run_trade_date ON trading.simulation_positions IS
  'Ersetzt die fachlich falsche alte UNIQUE(run_id,ticker,date) - eine Position/ein Lot ist durch '
  'trade_id eindeutig identifiziert, nicht durch ticker allein (ein Ticker kann fachlich mehrere '
  'gleichzeitig offene Lots haben, auch wenn v2 das ueber isOccupied() aktuell nicht zulaesst).';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('083', 'trading.simulation_positions: trade_id ergaenzt, alter Konfliktschluessel (run,ticker,date) durch fachlich korrekten (run,trade_id,date) ersetzt, v2-Zeilen muessen trade_id besitzen - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
