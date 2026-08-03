-- ============================================================================
-- Historische Daten, Walk-Forward-Simulation und Web-Steuerzentrale (Phase 2)
-- ============================================================================
-- Siehe docs/HISTORISCHE_SIMULATION_KONZEPT.md fuer die vollstaendige Begruendung jeder
-- Entscheidung. Kurzfassung der wichtigsten Architekturentscheidungen:
--
--   1. trading.backtest_runs (sql/037, bisher dormant, 0 Zeilen) wird zur zentralen
--      Simulationssteuerung erweitert statt eine parallele simulation_runs-Tabelle
--      anzulegen - backtest_id uebernimmt die Rolle der geforderten simulation_id.
--   2. Historische Markt-/Nachrichtendaten (historical_price_data/historical_news) bleiben
--      STRUKTURELL GETRENNT von den Live-Tabellen (stock_price_history/news_items) - die
--      gesamte Live-Pipeline liest diese ohne Kategorie-Filter, ein Diskriminator-Feld waere
--      ein einziges vergessenes WHERE von einer echten Live-Datenkorruption entfernt.
--   3. Simulierte Trades/Orders bleiben ebenfalls strukturell getrennt von trading.paper_trades
--      (aktiv vom echten Paper-Trading-System 14 genutzt) - gleiche Begruendung wie Punkt 2.
--   4. historical_fundamentals ist Schema-only (Workflow 18 bewusst deferred, siehe Auftrag:
--      "darf erst produktiv eingesetzt werden, wenn Point-in-time-Verfuegbarkeit zuverlaessig
--      abgebildet werden kann").
--
-- Diese Migration ist idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS / ON CONFLICT DO
-- NOTHING durchgaengig) und wird NICHT automatisch ausgefuehrt - manueller Lauf ueber
-- "97 - Einmalig - Beliebige Query ausfuehren" wie bei allen bisherigen Migrationen.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. trading.backtest_runs erweitern (zentrale Simulationssteuerung)
-- ============================================================================

ALTER TABLE trading.backtest_runs
  ADD COLUMN IF NOT EXISTS data_category TEXT,
  ADD COLUMN IF NOT EXISTS name TEXT,
  ADD COLUMN IF NOT EXISTS description TEXT,
  ADD COLUMN IF NOT EXISTS start_date DATE,
  ADD COLUMN IF NOT EXISTS end_date DATE,
  ADD COLUMN IF NOT EXISTS current_simulation_date DATE,
  ADD COLUMN IF NOT EXISTS data_cutoff_time TIME,
  ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Europe/Berlin',
  ADD COLUMN IF NOT EXISTS instrument_selection_json JSONB,
  ADD COLUMN IF NOT EXISTS benchmark_selection_json JSONB,
  ADD COLUMN IF NOT EXISTS news_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS fundamentals_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS portfolio_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS learning_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS initial_capital NUMERIC(18,2),
  ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'EUR',
  ADD COLUMN IF NOT EXISTS commission_model_json JSONB,
  ADD COLUMN IF NOT EXISTS slippage_model_json JSONB,
  ADD COLUMN IF NOT EXISTS model_version TEXT,
  ADD COLUMN IF NOT EXISTS dataset_version TEXT,
  ADD COLUMN IF NOT EXISTS config_snapshot_json JSONB,
  ADD COLUMN IF NOT EXISTS paused_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS progress_total INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS progress_completed INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS progress_percent NUMERIC(5,2) NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS warning_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS error_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS last_error TEXT,
  ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS created_by TEXT NOT NULL DEFAULT 'simulation-steuerzentrale',
  ADD COLUMN IF NOT EXISTS version INTEGER NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS out_of_sample_locked BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN trading.backtest_runs.data_category IS
  'Lebenszyklus-Kategorie des Laufs: historical_replay/training/calibration/out_of_sample. '
  'Getrennt vom bestehenden run_type (das ist die Backtest-Methodik: walk_forward/baseline_*/...).';
COMMENT ON COLUMN trading.backtest_runs.out_of_sample_locked IS
  'TRUE sobald ein out_of_sample-Lauf abgeschlossen wurde. Eine spaetere Umklassifizierung zu '
  'data_category=training bleibt technisch moeglich, wird aber verpflichtend in '
  'trading.simulation_events protokolliert (siehe Auftrag: "verliert seine Kennzeichnung als '
  'unangetasteter Test").';
COMMENT ON COLUMN trading.backtest_runs.config_snapshot_json IS
  'Unveraenderlicher Snapshot von trading.pipeline_config zum Startzeitpunkt des Laufs - '
  'macht den Lauf reproduzierbar, auch wenn sich pipeline_config spaeter aendert.';

DO $$
BEGIN
  ALTER TABLE trading.backtest_runs DROP CONSTRAINT IF EXISTS backtest_runs_status_check;
  ALTER TABLE trading.backtest_runs ADD CONSTRAINT backtest_runs_status_check
    CHECK (status IN (
      'draft','queued','running','pausing','paused',
      'completed','completed_with_warnings','failed','cancelled','archived',
      'insufficient_data'
    ));
END $$;

DO $$
BEGIN
  ALTER TABLE trading.backtest_runs DROP CONSTRAINT IF EXISTS backtest_runs_data_category_check;
  ALTER TABLE trading.backtest_runs ADD CONSTRAINT backtest_runs_data_category_check
    CHECK (data_category IS NULL OR data_category IN (
      'historical_replay','training','calibration','out_of_sample'
    ));
END $$;

ALTER TABLE trading.backtest_runs ALTER COLUMN status SET DEFAULT 'draft';

CREATE INDEX IF NOT EXISTS ix_backtest_runs_status ON trading.backtest_runs (status);
CREATE INDEX IF NOT EXISTS ix_backtest_runs_data_category ON trading.backtest_runs (data_category);

-- ============================================================================
-- 2. Historisches Marktdaten-/Nachrichten-Archiv (strukturell von Live getrennt)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.historical_price_data (
  id                BIGSERIAL PRIMARY KEY,
  ticker            TEXT NOT NULL,
  trading_date      DATE NOT NULL,
  open              NUMERIC(18,6),
  high              NUMERIC(18,6),
  low               NUMERIC(18,6),
  close             NUMERIC(18,6) NOT NULL,
  adjusted_close    NUMERIC(18,6),
  volume            BIGINT,
  currency          TEXT,
  exchange          TEXT,
  provider          TEXT NOT NULL,
  import_job_id     TEXT,
  fetched_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ticker, trading_date, provider)
);
CREATE INDEX IF NOT EXISTS ix_historical_price_data_ticker_date
  ON trading.historical_price_data (ticker, trading_date);
CREATE INDEX IF NOT EXISTS ix_historical_price_data_job ON trading.historical_price_data (import_job_id);
COMMENT ON TABLE trading.historical_price_data IS
  'Bewusst GETRENNT von trading.stock_price_history (Live). Wird ausschliesslich von Workflow 15 '
  '(Import) geschrieben und von Workflow 17 (Simulation) gelesen - niemals von der Live-Pipeline.';

CREATE TABLE IF NOT EXISTS trading.historical_corporate_actions (
  id              BIGSERIAL PRIMARY KEY,
  ticker          TEXT NOT NULL,
  action_type     TEXT NOT NULL CHECK (action_type IN ('split','dividend')),
  ex_date         DATE NOT NULL,
  split_ratio     NUMERIC(18,8),
  dividend_amount NUMERIC(18,6),
  currency        TEXT,
  source          TEXT NOT NULL,
  import_job_id   TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ticker, action_type, ex_date, source)
);
CREATE INDEX IF NOT EXISTS ix_historical_corporate_actions_ticker
  ON trading.historical_corporate_actions (ticker, ex_date);

CREATE TABLE IF NOT EXISTS trading.historical_news (
  id                  BIGSERIAL PRIMARY KEY,
  news_key            TEXT NOT NULL,
  provider            TEXT NOT NULL,
  title               TEXT NOT NULL,
  url                 TEXT,
  source              TEXT,
  published_at        TIMESTAMPTZ,
  language            TEXT,
  raw_content         TEXT,
  linked_tickers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
  is_general_market    BOOLEAN NOT NULL DEFAULT FALSE,
  import_job_id        TEXT,
  fetched_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (news_key, provider)
);
CREATE INDEX IF NOT EXISTS ix_historical_news_published ON trading.historical_news (published_at);
CREATE INDEX IF NOT EXISTS ix_historical_news_job ON trading.historical_news (import_job_id);
COMMENT ON COLUMN trading.historical_news.published_at IS
  'Kann NULL sein, bis der Anbieter einen Zeitstempel liefert - siehe Datenqualitaets-Warnung '
  '"Nachrichten ohne Veroeffentlichungszeit" in der Steuerzentrale. Ein NULL-Wert blockiert die '
  'Verwendung in Workflow 17 (kein verlaesslicher Cutoff-Vergleich moeglich).';

-- Schema-only, Workflow 18 bewusst deferred (siehe Konzeptdokument Abschnitt 4.4).
CREATE TABLE IF NOT EXISTS trading.historical_fundamentals (
  id                BIGSERIAL PRIMARY KEY,
  ticker            TEXT NOT NULL,
  reporting_period  TEXT NOT NULL,
  publication_date  DATE,
  filing_date       DATE,
  available_from    DATE NOT NULL,
  source            TEXT NOT NULL,
  revision          INTEGER NOT NULL DEFAULT 1,
  metrics_json      JSONB NOT NULL DEFAULT '{}'::jsonb,
  import_job_id     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (ticker, reporting_period, revision, source)
);
CREATE INDEX IF NOT EXISTS ix_historical_fundamentals_ticker
  ON trading.historical_fundamentals (ticker, available_from);
COMMENT ON TABLE trading.historical_fundamentals IS
  'Schema-only, dormant (Workflow 18 nicht gebaut) - available_from ist die Pflichtgrenze: ein '
  'Geschaeftsbericht darf in der Simulation erst ab diesem Datum sichtbar sein, niemals ab '
  'reporting_period oder publication_date allein (siehe Auftrag, Abschnitt "Optionaler Workflow 18").';

-- ============================================================================
-- 3. Import-Job-Steuerung (Workflow 15 + 16)
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.import_jobs (
  id                        BIGSERIAL PRIMARY KEY,
  job_id                    TEXT NOT NULL UNIQUE,
  job_type                  TEXT NOT NULL CHECK (job_type IN ('market_data','news')),
  status                    TEXT NOT NULL DEFAULT 'draft' CHECK (status IN (
    'draft','queued','running','pausing','paused',
    'completed','completed_with_warnings','failed','cancelled'
  )),
  provider                  TEXT NOT NULL,
  instrument_selection_json JSONB,
  period_from               DATE,
  period_to                 DATE,
  dry_run                   BOOLEAN NOT NULL DEFAULT FALSE,
  overwrite_mode            TEXT NOT NULL DEFAULT 'fill_gaps' CHECK (overwrite_mode IN (
    'fill_gaps','overwrite','skip_existing'
  )),
  parameters_json           JSONB NOT NULL DEFAULT '{}'::jsonb,
  progress_total            INTEGER NOT NULL DEFAULT 0,
  progress_completed        INTEGER NOT NULL DEFAULT 0,
  warning_count             INTEGER NOT NULL DEFAULT 0,
  error_count                INTEGER NOT NULL DEFAULT 0,
  last_error                 TEXT,
  heartbeat_at               TIMESTAMPTZ,
  created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
  started_at                   TIMESTAMPTZ,
  finished_at                   TIMESTAMPTZ,
  version                        INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_import_jobs_status ON trading.import_jobs (status, job_type);
COMMENT ON COLUMN trading.import_jobs.dry_run IS
  'TRUE = prueft Provider-Erreichbarkeit/Parameter, schreibt aber keine Zeilen - Auftrags-'
  'Vorgabe "Testlauf" fuer Datenimporte, analog dem bestehenden DRY_RUN-Konzept in 00/06/14.';

CREATE TABLE IF NOT EXISTS trading.import_job_items (
  id               BIGSERIAL PRIMARY KEY,
  job_id           TEXT NOT NULL REFERENCES trading.import_jobs(job_id),
  sequence_number  INTEGER NOT NULL,
  instrument       TEXT NOT NULL,
  period_from      DATE,
  period_to        DATE,
  status           TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending','running','completed','failed','skipped'
  )),
  attempt          INTEGER NOT NULL DEFAULT 0,
  started_at       TIMESTAMPTZ,
  finished_at      TIMESTAMPTZ,
  heartbeat_at     TIMESTAMPTZ,
  checkpoint_json  JSONB,
  error            TEXT,
  UNIQUE (job_id, sequence_number)
);
CREATE INDEX IF NOT EXISTS ix_import_job_items_job_status ON trading.import_job_items (job_id, status);
COMMENT ON TABLE trading.import_job_items IS
  'Ein Paket je (job_id, sequence_number) - z.B. ein Instrument oder ein Instrument+Jahr. '
  'checkpoint_json haelt den zuletzt erfolgreich importierten Zeitpunkt fest, damit ein '
  'Wiederholungsversuch nach einem Fehler nicht bei Null anfaengt.';

-- ============================================================================
-- 4. Simulations-Ausfuehrung (Workflow 17) - strukturell getrennt von paper_trades
-- ============================================================================

CREATE TABLE IF NOT EXISTS trading.simulation_run_steps (
  id                 BIGSERIAL PRIMARY KEY,
  simulation_run_id  BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  sequence_number    INTEGER NOT NULL,
  simulated_date     DATE NOT NULL,
  status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending','running','completed','failed','skipped'
  )),
  attempt            INTEGER NOT NULL DEFAULT 0,
  started_at         TIMESTAMPTZ,
  finished_at        TIMESTAMPTZ,
  heartbeat_at       TIMESTAMPTZ,
  checkpoint_json    JSONB,
  error              TEXT,
  UNIQUE (simulation_run_id, sequence_number)
);
CREATE INDEX IF NOT EXISTS ix_simulation_run_steps_run_status
  ON trading.simulation_run_steps (simulation_run_id, status);
COMMENT ON TABLE trading.simulation_run_steps IS
  'Ein Paket je simuliertem Handelstag (oder Gruppe von Tagen) - ermoeglicht Fortsetzen nach '
  'Serverneustart/Pause, analog trading.import_job_items fuer Workflow 15/16.';

CREATE TABLE IF NOT EXISTS trading.simulation_recommendations (
  id                     BIGSERIAL PRIMARY KEY,
  simulation_run_id      BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  as_of_date             DATE NOT NULL,
  ticker                 TEXT NOT NULL,
  richtung               TEXT NOT NULL CHECK (richtung IN ('kauf','verkauf')),
  status                 TEXT NOT NULL DEFAULT 'offen' CHECK (status IN ('offen','geschlossen','verworfen')),
  strategy               TEXT,
  entry_grund            TEXT,
  exit_grund             TEXT,
  entry_datum            DATE,
  exit_datum             DATE,
  market_regime_at_entry TEXT,
  evidence_json          JSONB,
  rule_version           TEXT,
  configuration_version  TEXT,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Bewusst KEIN blankes UNIQUE(simulation_run_id, ticker) - ein Ticker darf ueber einen
-- mehrjaehrigen Lauf hinweg beliebig oft neu empfohlen werden (offen->geschlossen->offen...),
-- nur gleichzeitig offen darf er je Lauf nur einmal sein (exakt wie beim Live-Pendant
-- trading.recommendations, siehe ux_recommendations_one_open_per_ticker in sql/007).
CREATE UNIQUE INDEX IF NOT EXISTS ux_simulation_recommendations_one_open_per_ticker
  ON trading.simulation_recommendations (simulation_run_id, ticker) WHERE status = 'offen';
COMMENT ON TABLE trading.simulation_recommendations IS
  'Spiegelt trading.recommendations, aber je Simulationslauf statt global - '
  'ux_simulation_recommendations_one_open_per_ticker gilt nur innerhalb eines simulation_run_id, '
  'nicht buchweit wie das Live-Pendant ux_recommendations_one_open_per_ticker.';

CREATE TABLE IF NOT EXISTS trading.simulation_orders (
  id                       BIGSERIAL PRIMARY KEY,
  simulation_run_id        BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  simulation_recommendation_id BIGINT REFERENCES trading.simulation_recommendations(id),
  ticker                   TEXT NOT NULL,
  signal_date              DATE NOT NULL,
  order_created_at         TIMESTAMPTZ NOT NULL,
  intended_execution_date  DATE NOT NULL,
  actual_execution_date    DATE,
  order_type               TEXT NOT NULL CHECK (order_type IN ('market_open','limit')),
  limit_price              NUMERIC(18,6),
  raw_market_price         NUMERIC(18,6),
  slippage                 NUMERIC(18,6),
  commission               NUMERIC(18,6),
  executed_price           NUMERIC(18,6),
  quantity                 NUMERIC(18,4) NOT NULL,
  execution_status         TEXT NOT NULL DEFAULT 'pending' CHECK (execution_status IN (
    'pending','filled','not_filled_price','not_filled_no_data','cancelled'
  )),
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_simulation_orders_run ON trading.simulation_orders (simulation_run_id, intended_execution_date);
COMMENT ON COLUMN trading.simulation_orders.intended_execution_date IS
  'Fruehestens naechster Handelstag nach signal_date (Auftrags-Standardregel) - nie derselbe Tag.';

CREATE TABLE IF NOT EXISTS trading.simulation_trades (
  id                          BIGSERIAL PRIMARY KEY,
  simulation_run_id           BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  trade_id                    TEXT NOT NULL,
  simulation_order_id         BIGINT REFERENCES trading.simulation_orders(id),
  ticker                      TEXT NOT NULL,
  strategy                    TEXT NOT NULL,
  direction                   TEXT NOT NULL CHECK (direction IN ('long','short')),
  as_of_date                  DATE NOT NULL,
  signal_created_at           TIMESTAMPTZ NOT NULL,
  decision_time                TIMESTAMPTZ NOT NULL,
  entry_rule                   TEXT NOT NULL,
  planned_entry_zone_low       NUMERIC(18,6),
  planned_entry_zone_high      NUMERIC(18,6),
  simulated_entry_time          TIMESTAMPTZ,
  simulated_entry_price         NUMERIC(18,6),
  stop_price_initial            NUMERIC(18,6),
  target_price_initial          NUMERIC(18,6),
  stop_price_current            NUMERIC(18,6),
  time_stop_at                   TIMESTAMPTZ,
  theoretical_quantity            NUMERIC(18,4),
  risk_amount                     NUMERIC(18,6),
  position_value                  NUMERIC(18,6),
  market_regime_at_entry          TEXT,
  configuration_version            TEXT,
  rule_version                      TEXT,
  data_schema_version               TEXT NOT NULL DEFAULT 'historische-simulation-v1',
  execution_model_version            TEXT,
  risk_model_version                  TEXT,
  status                              TEXT NOT NULL DEFAULT 'open' CHECK (status IN (
    'open','closed','expired_unfilled','cancelled','data_error'
  )),
  exit_time                            TIMESTAMPTZ,
  exit_price                           NUMERIC(18,6),
  exit_reason                          TEXT,
  gross_pnl                            NUMERIC(18,6),
  net_pnl                              NUMERIC(18,6),
  realized_r_multiple                  NUMERIC(10,4),
  holding_period_days                  INTEGER,
  maximum_favorable_excursion           NUMERIC(18,6),
  maximum_adverse_excursion             NUMERIC(18,6),
  commission_total                      NUMERIC(18,6) NOT NULL DEFAULT 0,
  slippage_total                        NUMERIC(18,6) NOT NULL DEFAULT 0,
  known_at_entry_json                    JSONB,
  created_at                             TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at                             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (simulation_run_id, trade_id)
);
CREATE INDEX IF NOT EXISTS ix_simulation_trades_run ON trading.simulation_trades (simulation_run_id, status);
COMMENT ON TABLE trading.simulation_trades IS
  'Spiegelt trading.paper_trades (gleiches Feldset/Statusmaschine), aber bewusst eine eigene '
  'Tabelle statt eines Diskriminator-Felds auf paper_trades - siehe Konzeptdokument Abschnitt 8.2.';
COMMENT ON COLUMN trading.simulation_trades.known_at_entry_json IS
  'Snapshot dessen, was zum simulierten Entscheidungszeitpunkt bekannt war (Signal, Regime, '
  'Fundamentalrevision, News) - Nachweis gegen Look-ahead-Bias, gleiche Idee wie '
  'trading.backtest_trades.known_at_entry_json (sql/037), hier pro Trade statt nur im Grobformat.';

CREATE TABLE IF NOT EXISTS trading.simulation_positions (
  id                     BIGSERIAL PRIMARY KEY,
  simulation_run_id      BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  ticker                 TEXT NOT NULL,
  simulated_date         DATE NOT NULL,
  quantity               NUMERIC(18,4) NOT NULL,
  average_cost_basis     NUMERIC(18,6) NOT NULL,
  mark_price             NUMERIC(18,6),
  unrealized_pnl         NUMERIC(18,6),
  corporate_action_adjustment_json JSONB,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (simulation_run_id, ticker, simulated_date)
);
CREATE INDEX IF NOT EXISTS ix_simulation_positions_run_date
  ON trading.simulation_positions (simulation_run_id, simulated_date);

CREATE TABLE IF NOT EXISTS trading.simulation_daily_portfolio (
  id                    BIGSERIAL PRIMARY KEY,
  simulation_run_id     BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  simulated_date        DATE NOT NULL,
  cash                  NUMERIC(18,2) NOT NULL,
  positions_value       NUMERIC(18,2) NOT NULL,
  total_equity          NUMERIC(18,2) NOT NULL,
  benchmark_value       NUMERIC(18,2),
  drawdown_pct          NUMERIC(6,3),
  open_positions_count  INTEGER NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (simulation_run_id, simulated_date)
);
CREATE INDEX IF NOT EXISTS ix_simulation_daily_portfolio_run
  ON trading.simulation_daily_portfolio (simulation_run_id, simulated_date);
COMMENT ON TABLE trading.simulation_daily_portfolio IS
  'Taegliche Equity-Kurve je Lauf - Grundlage fuer Drawdown-Verlauf/Benchmark-Vergleich in der '
  'Steuerzentrale (Bereich 5, Ergebnisse).';

CREATE TABLE IF NOT EXISTS trading.simulation_metrics (
  id                          BIGSERIAL PRIMARY KEY,
  simulation_run_id           BIGINT NOT NULL REFERENCES trading.backtest_runs(id) UNIQUE,
  final_equity                NUMERIC(18,2),
  total_return_pct             NUMERIC(8,3),
  annualized_return_pct         NUMERIC(8,3),
  benchmark_return_pct           NUMERIC(8,3),
  excess_return_pct                NUMERIC(8,3),
  max_drawdown_pct                  NUMERIC(6,3),
  volatility_pct                      NUMERIC(6,3),
  sharpe_ratio                          NUMERIC(8,4),
  win_rate_pct                            NUMERIC(6,3),
  profit_factor                            NUMERIC(10,4),
  average_win                              NUMERIC(18,6),
  average_loss                             NUMERIC(18,6),
  trade_count                              INTEGER,
  average_holding_period_days               NUMERIC(8,2),
  total_commission                          NUMERIC(18,2),
  total_slippage                            NUMERIC(18,2),
  unfilled_order_pct                        NUMERIC(6,3),
  metrics_by_regime_json                    JSONB,
  metrics_by_sector_json                     JSONB,
  metrics_by_strategy_json                   JSONB,
  metrics_by_news_type_json                  JSONB,
  metrics_by_confidence_class_json           JSONB,
  computed_at                                TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE trading.simulation_metrics IS
  'Aggregierte, ABFRAGBARE Kennzahlen je Lauf (eigene typisierte Spalten fuer die haeufigsten '
  'Vergleichsfelder) - ergaenzt, nicht ersetzt, das JSONB-Feld backtest_runs.results_json '
  '(Rohdaten-Archiv). Pflicht fuer den Simulationsvergleich (Steuerzentrale Bereich 5).';

CREATE TABLE IF NOT EXISTS trading.simulation_errors (
  id                 BIGSERIAL PRIMARY KEY,
  simulation_run_id  BIGINT REFERENCES trading.backtest_runs(id),
  simulation_step_id BIGINT REFERENCES trading.simulation_run_steps(id),
  occurred_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  ticker             TEXT,
  simulated_date     DATE,
  error_class        TEXT NOT NULL,
  message            TEXT NOT NULL,
  technical_detail   TEXT,
  retryable          BOOLEAN NOT NULL DEFAULT TRUE,
  attempt_count      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_simulation_errors_run ON trading.simulation_errors (simulation_run_id, occurred_at DESC);
COMMENT ON TABLE trading.simulation_errors IS
  'Strukturierter Fehlerlog je Simulationsschritt, analog trading.workflow_errors aber mit '
  'simulation_run_id/simulation_step_id-Bezug statt Workflow-Name.';

CREATE TABLE IF NOT EXISTS trading.simulation_events (
  id                 BIGSERIAL PRIMARY KEY,
  simulation_run_id  BIGINT NOT NULL REFERENCES trading.backtest_runs(id),
  event_type         TEXT NOT NULL CHECK (event_type IN (
    'created','started','paused','resumed','cancelled','completed',
    'step_retried','reclassified','config_changed'
  )),
  event_time         TIMESTAMPTZ NOT NULL DEFAULT now(),
  old_value          TEXT,
  new_value          TEXT,
  details_json       JSONB NOT NULL DEFAULT '{}'::jsonb,
  triggered_by       TEXT NOT NULL DEFAULT 'simulation-steuerzentrale'
);
CREATE INDEX IF NOT EXISTS ix_simulation_events_run ON trading.simulation_events (simulation_run_id, event_time DESC);
COMMENT ON TABLE trading.simulation_events IS
  'Audit-Trail fuer Statusuebergaenge und Umklassifizierungen. event_type=reclassified ist '
  'PFLICHT, sobald ein Lauf mit out_of_sample_locked=TRUE seine data_category aendert (siehe '
  'Auftrag: "Falls eine Aenderung zugelassen wird, muss sie protokolliert werden").';

-- ============================================================================
-- 5. Konfigurationswerte (additiv, ergaenzt bestehende trading.pipeline_config)
-- ============================================================================

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('SIMULATION_DEFAULT_PACKAGE_SIZE', 20, 'Anzahl simulierter Handelstage je Worker-Aufruf von Workflow 17 (Standardwert, ueberschreibbar pro Lauf).'),
  ('IMPORT_DEFAULT_PACKAGE_SIZE', 1, 'Anzahl Instrumente je Worker-Aufruf von Workflow 15/16 (ein Instrument+Zeitraum pro Paket, Anbieterlimits schonend).'),
  ('SIMULATION_HEARTBEAT_TIMEOUT_MIN', 15, 'Minuten ohne Heartbeat, nach denen ein Job/Lauf in der Steuerzentrale als moeglicherweise haengengeblieben markiert wird.'),
  ('SIMULATION_MAX_PARALLEL_RUNS', 1, 'Maximale Anzahl gleichzeitig laufender Simulationslaeufe (Sicherheitsnetz gegen ueberlastete DB/FastAPI-Anbieterlimits).'),
  ('IMPORT_MAX_RETRY_ATTEMPTS', 3, 'Maximale Wiederholversuche je fehlgeschlagenem import_job_item, bevor es als failed stehen bleibt statt automatisch erneut versucht zu werden.'),
  ('SIMULATION_MIN_DATA_QUALITY_PCT', 80, 'Mindest-Datenabdeckung (Prozent erwarteter Handelstage) je Instrument, unterhalb derer ein Lauf das Instrument standardmaessig ueberspringt statt es zu verarbeiten.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('057', 'Historische Daten, Walk-Forward-Simulation, Web-Steuerzentrale: backtest_runs erweitert + 12 neue Tabellen (historical_*, import_jobs/import_job_items, simulation_*)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
