-- ============================================================================
-- Welle 3, Arbeitspaket 5+6: Portfoliorisikomotor-Konfiguration + Stressszenarien
-- ============================================================================

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('MAX_TOTAL_OPEN_RISK_PCT',      6.0,  'Summe aller offenen risk_amount-Betraege darf diesen Anteil des Modell-Portfolios nicht uebersteigen.'),
  ('MAX_SECTOR_EXPOSURE_PCT',      15.0, 'Maximaler Anteil des Modell-Portfolios in offenen Positionen desselben Sektors.'),
  ('MAX_SINGLE_POSITION_PCT',      8.0,  'Maximaler Anteil des Modell-Portfolios in einer einzelnen offenen Position (Konzentrationslimit, schaerfer als MAX_POSITION_VALUE_PCT aus Welle 1, das nur den Einzeltrade betrachtet).'),
  ('MAX_OPEN_POSITIONS',           10,   'Maximale Anzahl gleichzeitig offener theoretischer Positionen.'),
  ('MAX_DIRECTIONAL_EXPOSURE_PCT', 40.0, 'Maximaler Anteil des Modell-Portfolios in dieselbe Richtung (long oder short) ueber alle offenen Positionen.'),
  ('MAX_PORTFOLIO_DRAWDOWN_PCT',   15.0, 'Ab diesem realisierten Drawdown des Paper-Trading-Ledgers (seit Systemstart) werden neue Eroeffnungen blockiert.'),
  ('CORRELATION_LOOKBACK_DAYS',    60,   'Fenster fuer die paarweise Korrelationsberechnung offener Positionen (Tagesrenditen).'),
  ('MAX_PAIRWISE_CORRELATION',     0.75, 'Ab dieser paarweisen Korrelation (Betrag) zwischen zwei offenen/geplanten Positionen greift ein Konzentrationshinweis.'),
  ('STRESS_RISK_REDUCTION_FACTOR', 0.5,  'Multiplikator auf MAX_TOTAL_OPEN_RISK_PCT, wenn das Marktregime der betroffenen Region combined_regime=stress zeigt (Auftragsvorgabe: aktuelle Stressphase beruecksichtigen).')
ON CONFLICT (config_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS trading.portfolio_risk_checks (
  id                    BIGSERIAL PRIMARY KEY,
  run_id                TEXT,
  ticker                TEXT NOT NULL,
  checked_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  portfolio_approved    BOOLEAN NOT NULL,
  portfolio_risk_before NUMERIC(8,5),
  portfolio_risk_after  NUMERIC(8,5),
  blockers_json         JSONB NOT NULL DEFAULT '[]'::jsonb,
  config_snapshot_json  JSONB,
  risk_model_version    TEXT
);
CREATE INDEX IF NOT EXISTS ix_portfolio_risk_checks_ticker ON trading.portfolio_risk_checks (ticker, checked_at DESC);
COMMENT ON TABLE trading.portfolio_risk_checks IS
  'Welle 3, AP5: jede Portfoliorisiko-Pruefung vor einer geplanten Eroeffnung, mit '
  'strukturierten Blockern (gleiches Muster wie trading.recommendation_veto_log) - '
  'auch genehmigte Pruefungen werden gespeichert (Nachvollziehbarkeit).';

CREATE TABLE IF NOT EXISTS trading.stress_scenarios (
  id                     BIGSERIAL PRIMARY KEY,
  run_id                 TEXT,
  scenario_name          TEXT NOT NULL,
  assumptions_json        JSONB NOT NULL,
  affected_positions_json JSONB NOT NULL,
  estimated_loss          NUMERIC(18,6),
  loss_pct_of_portfolio    NUMERIC(8,5),
  data_quality             TEXT NOT NULL,
  model_version             TEXT NOT NULL,
  computed_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_stress_scenarios_run ON trading.stress_scenarios (run_id, scenario_name);
COMMENT ON TABLE trading.stress_scenarios IS
  'Welle 3, AP6: einfache, transparente Stressszenarien (Index -3%/-5%/-10%, Vol-Sprung, '
  'Sektor -7%, Waehrungsschock, Gap-durch-Stop, Mehrfach-Stop) je Portfoliorisiko-Lauf.';

-- Neue Tabellen fuer die Lernagent-Aktivierungspfade (AP9), die 12 - Lernvorschlag-
-- Freigabe fuer die neuen Vorschlagstypen braucht (siehe docs/LERNAGENT_HANDELSSTRATEGIEN.md).
CREATE TABLE IF NOT EXISTS trading.strategy_status (
  strategy      TEXT PRIMARY KEY,
  aktiv         BOOLEAN NOT NULL DEFAULT TRUE,
  deactivated_at TIMESTAMPTZ,
  deactivated_reason TEXT,
  source_proposal_id BIGINT REFERENCES trading.learning_rule_proposals(id),
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO trading.strategy_status (strategy, aktiv) VALUES
  ('mean_reversion', TRUE), ('trend_following', TRUE), ('breakout', TRUE), ('news_event', TRUE)
ON CONFLICT (strategy) DO NOTHING;
COMMENT ON TABLE trading.strategy_status IS
  'Welle 3, AP9: einzige Stelle, um eine Strategiefamilie global zu deaktivieren '
  '(Lernvorschlagstyp "strategy_deactivation", aktiviert ueber 12). "06" prueft dies '
  'vor der Kandidatenauswahl je Ticker.';

CREATE TABLE IF NOT EXISTS trading.strategy_parameters (
  strategy        TEXT NOT NULL,
  parameter_key   TEXT NOT NULL,
  parameter_value NUMERIC NOT NULL,
  version         INTEGER NOT NULL DEFAULT 1,
  source_proposal_id BIGINT REFERENCES trading.learning_rule_proposals(id),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (strategy, parameter_key)
);
INSERT INTO trading.strategy_parameters (strategy, parameter_key, parameter_value) VALUES
  ('mean_reversion', 'stop_atr_multiplier', 1.0), ('mean_reversion', 'target_atr_multiplier', 1.5), ('mean_reversion', 'horizon_days', 3),
  ('trend_following', 'stop_atr_multiplier', 1.5), ('trend_following', 'target_atr_multiplier', 2.5), ('trend_following', 'horizon_days', 15),
  ('breakout', 'stop_atr_multiplier', 1.0), ('breakout', 'target_atr_multiplier', 3.0), ('breakout', 'horizon_days', 7),
  ('news_event', 'horizon_days', 2)
ON CONFLICT (strategy, parameter_key) DO NOTHING;
COMMENT ON TABLE trading.strategy_parameters IS
  'Welle 3, AP9+AP10: seit Welle 2 in "02" hartkodierte Stop-/Ziel-Multiplikatoren und '
  'Zeitstop-Horizonte, jetzt hier als Default geseedet UND von "02"/"06" als Override '
  'gelesen (Fallback auf den bisherigen hartkodierten Wert, falls keine Zeile existiert) - '
  'macht die Lernvorschlagstypen "time_stop_change"/Multiplikator-Anpassung ohne Code-Push aktivierbar.';
