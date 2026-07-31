-- ============================================================================
-- Welle 3, Arbeitspaket 1: Paper-Trading-Ledger
-- ============================================================================
-- Vollstaendiges, ereignisbasiertes Ledger fuer theoretische Trades. Getrennt
-- von trading.recommendations (Welle 1/2, bleibt als "Kandidaten-/Signal-
-- Ebene" bestehen, kein Consumer geaendert) - paper_trades ist die
-- autoritative, portfoliorisiko-gepruefte Ausfuehrungsebene. KEINE Aenderung
-- ueberschreibt nur den aktuellen Stand: jede Statusaenderung erzeugt
-- zusaetzlich eine Zeile in paper_trade_events (Auftragsvorgabe).

CREATE TABLE IF NOT EXISTS trading.paper_trades (
  id                          BIGSERIAL PRIMARY KEY,
  trade_id                    TEXT NOT NULL UNIQUE,
  run_id                      TEXT,
  recommendation_id           BIGINT REFERENCES trading.recommendations(id),
  ticker                      TEXT NOT NULL,
  strategy                    TEXT NOT NULL,
  direction                   TEXT NOT NULL CHECK (direction IN ('long','short')),
  signal_created_at           TIMESTAMPTZ NOT NULL,
  decision_time               TIMESTAMPTZ NOT NULL,
  entry_rule                  TEXT NOT NULL,
  planned_entry_zone_low      NUMERIC(18,6),
  planned_entry_zone_high     NUMERIC(18,6),
  simulated_entry_time        TIMESTAMPTZ,
  simulated_entry_price       NUMERIC(18,6),
  stop_price_initial          NUMERIC(18,6) NOT NULL,
  target_price_initial        NUMERIC(18,6) NOT NULL,
  stop_price_current          NUMERIC(18,6),
  time_stop_at                TIMESTAMPTZ,
  thesis_expires_at           TIMESTAMPTZ,
  theoretical_quantity        NUMERIC(18,4),
  risk_amount                 NUMERIC(18,6),
  position_value              NUMERIC(18,6),
  market_regime_at_entry      TEXT,
  opportunity_score_at_entry  NUMERIC(6,4),
  risk_score_at_entry         NUMERIC(6,4),
  evidence_confidence_at_entry NUMERIC(6,4),
  configuration_version       TEXT,
  rule_version                TEXT,
  data_schema_version         TEXT NOT NULL DEFAULT 'welle3-v1',
  execution_model_version     TEXT,
  risk_model_version          TEXT,
  status                      TEXT NOT NULL DEFAULT 'proposed'
    CHECK (status IN ('proposed','blocked','awaiting_confirmation','open','closed','expired_unfilled','cancelled','data_error')),
  exit_time                   TIMESTAMPTZ,
  exit_price                  NUMERIC(18,6),
  exit_reason                 TEXT,
  exit_reasons_all_json       JSONB,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_paper_trades_ticker ON trading.paper_trades (ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_paper_trades_status ON trading.paper_trades (status);
CREATE INDEX IF NOT EXISTS ix_paper_trades_strategy ON trading.paper_trades (strategy, status);

COMMENT ON TABLE trading.paper_trades IS
  'Welle 3, AP1: autoritatives Paper-Trading-Ledger. Aktueller Stand je Trade - die '
  'vollstaendige Historie jeder Statusaenderung liegt zusaetzlich in paper_trade_events, '
  'diese Zeile wird NIE als einzige Quelle der Wahrheit behandelt.';
COMMENT ON COLUMN trading.paper_trades.trade_id IS 'Deterministisch aus ticker+business_date+strategy+revision gebildet (siehe Workflow 14) - erlaubt Wiederholungserkennung ohne doppelte Trades bei einem erneuten Lauf.';
COMMENT ON COLUMN trading.paper_trades.entry_rule IS 'Textuelle Beschreibung des AP2-Ausfuehrungsmodells, das fuer diesen Trade galt (siehe docs/AUSFUEHRUNGSMODELL.md).';

CREATE TABLE IF NOT EXISTS trading.paper_trade_events (
  id            BIGSERIAL PRIMARY KEY,
  trade_id      TEXT NOT NULL REFERENCES trading.paper_trades(trade_id),
  event_type    TEXT NOT NULL,
  event_time    TIMESTAMPTZ NOT NULL DEFAULT now(),
  old_status    TEXT,
  new_status    TEXT,
  details_json  JSONB NOT NULL DEFAULT '{}'::jsonb,
  rule_version  TEXT
);
CREATE INDEX IF NOT EXISTS ix_paper_trade_events_trade ON trading.paper_trade_events (trade_id, event_time);
COMMENT ON TABLE trading.paper_trade_events IS 'Welle 3, AP1: vollstaendige, unveraenderliche Ereignis-Historie jeder Statusaenderung eines Paper Trades.';

CREATE TABLE IF NOT EXISTS trading.paper_trade_valuations (
  id                          BIGSERIAL PRIMARY KEY,
  trade_id                    TEXT NOT NULL REFERENCES trading.paper_trades(trade_id),
  valuation_date               DATE NOT NULL,
  mark_price                   NUMERIC(18,6),
  unrealized_r_multiple        NUMERIC(10,4),
  maximum_favorable_excursion  NUMERIC(18,6),
  maximum_adverse_excursion    NUMERIC(18,6),
  data_quality_status          TEXT,
  created_at                   TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_paper_trade_valuations_trade_date UNIQUE (trade_id, valuation_date)
);
COMMENT ON TABLE trading.paper_trade_valuations IS 'Welle 3, AP4: taegliche Marktbewertung offener Trades (MFE/MAE-Verlauf), eine Zeile je Trade+Tag.';

CREATE TABLE IF NOT EXISTS trading.paper_trade_costs (
  id                    BIGSERIAL PRIMARY KEY,
  trade_id              TEXT NOT NULL REFERENCES trading.paper_trades(trade_id),
  cost_type             TEXT NOT NULL CHECK (cost_type IN ('entry_fee','exit_fee','entry_slippage','exit_slippage','financing')),
  amount                NUMERIC(18,6) NOT NULL,
  model_name            TEXT NOT NULL,
  model_config_json     JSONB,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_paper_trade_costs_trade ON trading.paper_trade_costs (trade_id);
COMMENT ON TABLE trading.paper_trade_costs IS 'Welle 3, AP2: jede Kostenkomponente einzeln, mit Modellname/-konfiguration fuer Reproduzierbarkeit.';

-- Zusammenfassende Trade-Kennzahlen (AP4) als View statt redundanter Tabelle -
-- immer aktuell, keine Synchronisationsgefahr.
CREATE OR REPLACE VIEW trading.v_paper_trade_metrics AS
SELECT
  pt.trade_id, pt.ticker, pt.strategy, pt.direction, pt.status,
  pt.simulated_entry_price, pt.exit_price, pt.exit_reason,
  pt.simulated_entry_time, pt.exit_time,
  EXTRACT(EPOCH FROM (pt.exit_time - pt.simulated_entry_time)) / 86400.0 AS holding_period_days,
  (COALESCE((SELECT SUM(c.amount) FROM trading.paper_trade_costs c WHERE c.trade_id = pt.trade_id AND c.cost_type IN ('entry_fee','exit_fee')), 0)) AS fees,
  (COALESCE((SELECT SUM(c.amount) FROM trading.paper_trade_costs c WHERE c.trade_id = pt.trade_id AND c.cost_type IN ('entry_slippage','exit_slippage')), 0)) AS slippage_cost,
  CASE WHEN pt.status = 'closed' AND pt.exit_price IS NOT NULL AND pt.simulated_entry_price IS NOT NULL THEN
    CASE WHEN pt.direction = 'long' THEN (pt.exit_price - pt.simulated_entry_price) * pt.theoretical_quantity
         ELSE (pt.simulated_entry_price - pt.exit_price) * pt.theoretical_quantity END
  ELSE NULL END AS gross_pnl,
  pt.risk_amount AS planned_risk
FROM trading.paper_trades pt;

COMMENT ON VIEW trading.v_paper_trade_metrics IS
  'Welle 3, AP4: Basis-Kennzahlen je Trade (gross_pnl, fees, slippage, holding_period). '
  'net_pnl/realized_r_multiple werden in Workflow 14 beim Schliessen direkt auf '
  'paper_trades geschrieben (deterministisch berechnet, nicht in der View dupliziert), '
  'siehe unten.';

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS gross_pnl              NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS net_pnl                NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS return_pct             NUMERIC(10,4),
  ADD COLUMN IF NOT EXISTS realized_r_multiple    NUMERIC(10,4),
  ADD COLUMN IF NOT EXISTS holding_period_days    NUMERIC(10,4),
  ADD COLUMN IF NOT EXISTS maximum_favorable_excursion NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS maximum_adverse_excursion   NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS ambiguous_execution    BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS data_quality_at_exit    TEXT;

COMMENT ON COLUMN trading.paper_trades.realized_r_multiple IS 'net_pnl / risk_amount - Definition exakt wie im Auftrag (Nettogewinn/-verlust geteilt durch urspruenglich geplantes Verlustrisiko).';
