-- ============================================================================
-- 084 - trading.simulation_decision_log: Audit-Trail fuer angenommene und
-- abgelehnte/blockierte Handelskandidaten. WF17-v2-Reparatur.
-- ============================================================================
-- Bisher verschwanden verworfene Kandidaten in "Verarbeite Tage-Paket" einfach
-- durch `continue` - nicht unterscheidbar von "kein Signal vorhanden". Ab v2
-- wird jede echte Kandidaten-Entscheidung protokolliert (ACCEPTED/REJECTED/
-- BLOCKED/NO_FILL), aber bewusst NICHT der Fall "kein Signal" (haette bei 76
-- Handelstagen x N Tickern taeglich Massen von wertlosen Zeilen erzeugt).
--
-- `reason` ist bewusst freies TEXT ohne CHECK-Constraint (statt eines starren
-- Enums) - die Werteliste ist lang und kann in kuenftigen Strategie-Erweiterungen
-- wachsen; ein CHECK wuerde bei einem vergessenen neuen Wert die ganze
-- Persistierung eines Tages zum Scheitern bringen. Bekannte Werte (Stand
-- 2026-09-06, siehe checkHardLimits/sizePosition/evaluateNewsForTicker in
-- "Verarbeite Tage-Paket"): ALREADY_OCCUPIED, MAX_OPEN_POSITIONS,
-- DIRECTIONAL_LIMIT, TOTAL_RISK_LIMIT, SECTOR_LIMIT, REGION_LIMIT,
-- SINGLE_POSITION_LIMIT, RRR_TOO_LOW, QUANTITY_TOO_SMALL,
-- UNECONOMICAL_AFTER_COSTS, STOP_WRONG_SIDE, STOP_TARGET_INVALID, NEWS_VETO,
-- PRICE_NOT_FILLED, OK (bei ACCEPTED).
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS trading.simulation_decision_log (
  id                    BIGSERIAL PRIMARY KEY,
  simulation_run_id     BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  simulated_date        DATE NOT NULL,
  ticker                TEXT NOT NULL,
  strategy              TEXT,
  direction             TEXT,
  decision              TEXT NOT NULL CHECK (decision IN ('ACCEPTED','REJECTED','BLOCKED','NO_FILL')),
  reason                TEXT NOT NULL,
  raw_score             NUMERIC(10,4),
  theoretical_quantity  NUMERIC(18,4),
  actual_quantity       NUMERIC(18,4),
  position_value        NUMERIC(18,6),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_simulation_decision_log_run_date
  ON trading.simulation_decision_log (simulation_run_id, simulated_date);
CREATE INDEX IF NOT EXISTS ix_simulation_decision_log_run_reason
  ON trading.simulation_decision_log (simulation_run_id, reason);

COMMENT ON TABLE trading.simulation_decision_log IS
  'Audit-Trail jeder ECHTEN Kandidaten-Entscheidung in Workflow 17 v2 (ein Signal existierte). '
  'Der Fall "kein Signal fuer diesen Ticker/Tag" wird bewusst NICHT geloggt (Volumenschutz).';
COMMENT ON COLUMN trading.simulation_decision_log.decision IS
  'ACCEPTED = Order wurde erzeugt. REJECTED = Kandidat fachlich ungueltig (Sizing-Veto, News-Veto). '
  'BLOCKED = Kandidat fachlich gueltig, aber durch ein Portfoliolimit oder ALREADY_OCCUPIED '
  'verhindert. NO_FILL = Order erzeugt, aber am Ausfuehrungstag nicht gefuellt.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('084', 'trading.simulation_decision_log: Audit-Trail fuer angenommene/abgelehnte/blockierte Handelskandidaten - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
