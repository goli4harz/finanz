-- ============================================================================
-- Welle 3, Arbeitspaket 7+8: Backtesting-Schema + Wahrscheinlichkeits-/
-- Kalibrierungs-Schema
-- ============================================================================
-- Beide Mechanismen sind zum Zeitpunkt dieser Migration bewusst DORMANT -
-- das System ist erst rund 2 Wochen alt (siehe OFFENE_AUFGABEN.md), es gibt
-- noch keine ausreichende Historie fuer ein echtes Walk-Forward/Out-of-Sample-
-- Backtesting UND noch keine abgeschlossenen Paper Trades fuer eine
-- Kalibrierung. Schema + Berechnungsmechanismus sind vollstaendig
-- funktionsfaehig und werden mit wachsender Datenbasis organisch aktiv -
-- kein Platzhalter, kein zukuenftiger Umbau noetig (siehe
-- docs/BACKTESTING_UND_WALK_FORWARD.md, docs/WAHRSCHEINLICHKEITSKALIBRIERUNG.md).

CREATE TABLE IF NOT EXISTS trading.backtest_runs (
  id                     BIGSERIAL PRIMARY KEY,
  backtest_id            TEXT NOT NULL UNIQUE,
  run_type               TEXT NOT NULL CHECK (run_type IN ('walk_forward','out_of_sample','baseline_buy_hold','baseline_random','baseline_unfiltered_signal','baseline_old_logic','current_logic')),
  strategy_filter        TEXT,
  train_window_start     DATE,
  train_window_end       DATE,
  validation_window_start DATE,
  validation_window_end   DATE,
  test_window_start       DATE,
  test_window_end         DATE,
  configuration_version    TEXT NOT NULL,
  rule_version              TEXT NOT NULL,
  data_schema_version        TEXT NOT NULL DEFAULT 'welle3-v1',
  status                     TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','completed','failed','insufficient_data')),
  trade_count                 INTEGER,
  results_json                 JSONB,
  started_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at                   TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_backtest_runs_type ON trading.backtest_runs (run_type, started_at DESC);
COMMENT ON TABLE trading.backtest_runs IS
  'Welle 3, AP7: ein reproduzierbarer Backtest-Lauf. train/validation/test-Fenster sind '
  'fuer walk_forward/out_of_sample Pflicht (CHECK nicht erzwungen, da baseline-Laeufe '
  'sie nicht brauchen - Disziplin liegt beim aufrufenden Workflow, siehe '
  'docs/BACKTESTING_UND_WALK_FORWARD.md).';

CREATE TABLE IF NOT EXISTS trading.backtest_trades (
  id             BIGSERIAL PRIMARY KEY,
  backtest_id    TEXT NOT NULL REFERENCES trading.backtest_runs(backtest_id),
  ticker         TEXT NOT NULL,
  strategy       TEXT,
  entry_date     DATE NOT NULL,
  exit_date      DATE,
  entry_price    NUMERIC(18,6),
  exit_price     NUMERIC(18,6),
  net_pnl        NUMERIC(18,6),
  realized_r_multiple NUMERIC(10,4),
  exit_reason    TEXT,
  known_at_entry_json JSONB,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_backtest_trades_run ON trading.backtest_trades (backtest_id);
COMMENT ON COLUMN trading.backtest_trades.known_at_entry_json IS
  'Snapshot dessen, was zum simulierten Entscheidungszeitpunkt bekannt war (Signal, '
  'Regime, Fundamentalrevision, News) - Nachweis gegen Look-ahead-Bias, pro Trade.';

-- ============================================================================
-- Wahrscheinlichkeiten/Kalibrierung (AP8)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.probability_estimates (
  id                    BIGSERIAL PRIMARY KEY,
  segment_strategy      TEXT,
  segment_direction     TEXT,
  segment_market_regime TEXT,
  segment_risk_bucket   TEXT,
  segment_evidence_bucket TEXT,
  segment_time_horizon    TEXT,
  sample_size              INTEGER NOT NULL,
  p_win                     NUMERIC(6,4),
  p_positive_return          NUMERIC(6,4),
  p_target_before_stop        NUMERIC(6,4),
  expected_value_r             NUMERIC(10,4),
  probability_status            TEXT NOT NULL CHECK (probability_status IN ('estimated','insufficient_data')),
  min_sample_size_required        INTEGER NOT NULL,
  computed_at                       TIMESTAMPTZ NOT NULL DEFAULT now(),
  rule_version                       TEXT NOT NULL,
  UNIQUE (segment_strategy, segment_direction, segment_market_regime, segment_risk_bucket, segment_evidence_bucket, segment_time_horizon, rule_version)
);
COMMENT ON TABLE trading.probability_estimates IS
  'Welle 3, AP8: Wahrscheinlichkeitsfelder AUSSCHLIESSLICH aus historischen, '
  'vergleichbaren abgeschlossenen Paper Trades abgeleitet. probability_status=insufficient_data '
  'statt einer KI-Ersatzschaetzung, wenn sample_size < min_sample_size_required (Default 30, '
  'siehe trading.pipeline_config PROBABILITY_MIN_SAMPLE_SIZE).';

CREATE TABLE IF NOT EXISTS trading.calibration_checks (
  id                  BIGSERIAL PRIMARY KEY,
  probability_estimate_id BIGINT REFERENCES trading.probability_estimates(id),
  bucket_label         TEXT NOT NULL,
  predicted_probability  NUMERIC(6,4) NOT NULL,
  observed_frequency      NUMERIC(6,4),
  sample_size               INTEGER NOT NULL,
  brier_score                 NUMERIC(8,6),
  calibration_error             NUMERIC(8,6),
  confidence_interval_low        NUMERIC(6,4),
  confidence_interval_high        NUMERIC(6,4),
  computed_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE trading.calibration_checks IS
  'Welle 3, AP8: Kalibrierungskurve je Prognose-Bucket (beobachtete vs. vorhergesagte '
  'Trefferquote), Brier Score, Konfidenzintervall (Wilson-Score, siehe Workflow-Code).';

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('PROBABILITY_MIN_SAMPLE_SIZE', 30, 'Mindest-Fallzahl je Segment, unterhalb derer probability_status=insufficient_data bleibt statt einer Schaetzung.'),
  ('LEARNING_MIN_TRADE_SAMPLE_SIZE', 30, 'Mindest-Fallzahl abgeschlossener Paper Trades, bevor der Handelslernagent (09b) ueberhaupt einen Vorschlag fuer ein Segment erzeugen darf.'),
  ('BACKTEST_MIN_WINDOW_DAYS', 180, 'Mindestlaenge (Kalendertage) eines Test-/Validierungsfensters fuer einen als aussagekraeftig behandelten Backtest-Lauf.')
ON CONFLICT (config_key) DO NOTHING;
