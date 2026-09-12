-- ============================================================================
-- 090 - trading.simulation_shadow_trades: dedizierte, run-gescopte Persistenzschicht
-- fuer den AVAILABLE_DATA_LIVE_REPLAY Multi-Day Shadow-Portfolio/Execution-State
-- (LIVE_PARITY Schritt 4O.3A, 2026-09-12).
-- ============================================================================
-- Vorgeschichte: Schritt 4O.3 versuchte den Multi-Day Shadow-State rein in einer
-- JavaScript-Variable innerhalb "Verarbeite Tage-Paket" zu halten. Das scheiterte
-- strukturell: WF17 verarbeitet einen Lauf in Paketen (_package_size Business Days,
-- Default 20, config-getrieben ueber SIMULATION_DEFAULT_PACKAGE_SIZE), jedes Paket
-- als vollstaendig separate n8n-Workflow-Ausfuehrung (Schedule-Trigger alle 30
-- Sekunden, "DB: Naechstes Tage-Paket laden" claimt das naechste Paket per
-- FOR UPDATE SKIP LOCKED). Ein In-Memory-JS-Objekt ueberlebt diese Grenze nicht -
-- jede Ausfuehrung startet mit einem komplett frischen V8-Kontext. Diese Tabelle
-- ist die dafuer notwendige Persistenzschicht.
--
-- BEWUSST GETRENNT von allen bestehenden Tabellen:
--   trading.paper_trades           - echtes Live-Paper-Trading (WF14), nie referenziert
--   trading.simulation_orders/fills/trades/positions - Research-Backtest-Ausfuehrung
--   trading.simulation_decision_log - bleibt AUDIT-/Entscheidungs-Trail, wird NICHT
--                                      zum State-Store umfunktioniert (Nutzerentscheidung
--                                      4O.3A: keine State-Rekonstruktion aus dem Decision
--                                      Log pro Paket - das waere fachlich vermischend und
--                                      teuer bei jedem Paket-Start).
--
-- KEIN Cash-Ledger: cash/total_equity/peak_equity werden bewusst NICHT gefuehrt (4M/4N
-- zeigten, dass die aktive WF14/Engine-Portfolio-Pruefung nur MODEL_PORTFOLIO_VALUE
-- (statische Config) + drawdown_pct (aus geschlossenen Trades rekonstruierbar) braucht -
-- ein Shadow-Cash-Ledger waere fachlich unbegruendeter Mehraufwand, siehe 4M Phase 24/4N).
--
-- shadow_trade_id ist deterministisch aus ticker+decision_date+strategy abgeleitet
-- (analog zu WF06s tradeId = ticker+heute+strategy) - identischer logischer Kandidat
-- innerhalb desselben Laufs erzeugt immer dieselbe ID, UPSERT auf (simulation_run_id,
-- shadow_trade_id) ist damit die zentrale Idempotenz-Garantie (kein Doppel-Proposal,
-- keine Doppel-Fills/Closes bei wiederholter Paket-Verarbeitung).
-- ============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS trading.simulation_shadow_trades (
  id                      BIGSERIAL PRIMARY KEY,
  simulation_run_id       BIGINT NOT NULL REFERENCES trading.backtest_runs(id) ON DELETE CASCADE,
  shadow_trade_id         TEXT NOT NULL,

  ticker                  TEXT NOT NULL,
  strategy                TEXT NOT NULL,
  direction               TEXT NOT NULL CHECK (direction IN ('long','short')),
  decision_date           DATE NOT NULL,
  status                  TEXT NOT NULL
    CHECK (status IN ('proposed','open','closed','expired_unfilled','data_error','data_error_final')),

  quantity                NUMERIC(18,4),
  zone_low                NUMERIC(18,6),
  zone_high               NUMERIC(18,6),

  entry_price             NUMERIC(18,6),
  entry_date              DATE,
  stop_price              NUMERIC(18,6),
  target_price            NUMERIC(18,6),

  time_stop_at            TIMESTAMPTZ,
  thesis_expires_at       TIMESTAMPTZ,

  risk_amount             NUMERIC(18,6),
  position_value          NUMERIC(18,6),

  sector                  TEXT,
  region                  TEXT,
  currency                TEXT,

  entry_fee               NUMERIC(18,4),
  entry_slippage          NUMERIC(18,4),

  exit_price              NUMERIC(18,6),
  exit_date               DATE,
  exit_reason             TEXT,

  gross_pnl               NUMERIC(18,4),
  net_pnl                 NUMERIC(18,4),
  return_pct              NUMERIC(10,4),
  r_multiple              NUMERIC(10,4),

  data_error_count        INTEGER NOT NULL DEFAULT 0 CHECK (data_error_count >= 0),
  pre_data_error_status   TEXT,
  ambiguous_execution     BOOLEAN NOT NULL DEFAULT false,

  -- Immer 'CURRENT_POLICY_REPLAY' (pipeline_config ist unversioniert, siehe 4M/4N/4O) -
  -- als Spalte statt Konstante gefuehrt, damit ein spaeterer echter PIT-Modus (falls
  -- Config je historisiert wird) ohne Schemaaenderung unterscheidbar waere.
  policy_mode             TEXT NOT NULL DEFAULT 'CURRENT_POLICY_REPLAY',

  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT uq_simulation_shadow_trades_run_trade UNIQUE (simulation_run_id, shadow_trade_id)
);

CREATE INDEX IF NOT EXISTS ix_simulation_shadow_trades_run_status
  ON trading.simulation_shadow_trades (simulation_run_id, status);

COMMENT ON TABLE trading.simulation_shadow_trades IS
  'LIVE_PARITY 4O.3A: run-gescopter Multi-Day Shadow-Portfolio/Execution-State fuer AVAILABLE_DATA_LIVE_REPLAY. '
  'Vollstaendig getrennt von trading.paper_trades (echtes Live-Paper-Trading) und den Research-Tabellen '
  '(simulation_orders/fills/trades/positions). simulation_decision_log bleibt der Audit-/Entscheidungs-Trail, '
  'diese Tabelle ist NICHT dessen Ersatz, sondern der tatsaechliche fortlaufende Zustand (proposed/open/closed/'
  'expired_unfilled/data_error/data_error_final), der zwischen den paketweisen WF17-Ausfuehrungen ueberleben muss.';

COMMENT ON COLUMN trading.simulation_shadow_trades.shadow_trade_id IS
  'Deterministisch aus ticker+decision_date+strategy (analog WF06 tradeId) - identischer logischer Kandidat '
  'innerhalb desselben Laufs erzeugt immer dieselbe ID. UPSERT auf (simulation_run_id, shadow_trade_id) ist die '
  'zentrale Idempotenz-Garantie gegen Doppel-Proposals/-Fills/-Closes bei wiederholter Paket-Verarbeitung.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('090', 'trading.simulation_shadow_trades: dedizierte run-gescopte Persistenz fuer den Multi-Day AVAILABLE_DATA_LIVE_REPLAY Shadow-Portfolio/Execution-State (LIVE_PARITY 4O.3A) - loest den an der 30s-Paketgrenze gescheiterten In-Memory-Ansatz aus 4O.3 ab')
ON CONFLICT (version) DO NOTHING;

COMMIT;
