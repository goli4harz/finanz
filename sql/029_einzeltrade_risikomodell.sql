-- ============================================================================
-- Welle 1, Arbeitspaket 6: Einzeltrade-Risikomodell
-- ============================================================================
-- Konservative Default-Werte (Nutzer kann sie spaeter per SQL/UI aendern,
-- siehe trading.pipeline_config). Portfoliowert ist ein FIKTIVER Modellwert
-- fuer die theoretische Positionsgroessen-Berechnung - es gibt kein echtes
-- Depot, das gesamte System bleibt Simulation.

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
  ('MODEL_PORTFOLIO_VALUE',   100000, 'Fiktiver Modell-Portfoliowert (EUR) fuer die theoretische Positionsgroessen-Berechnung. Kein echtes Depot.'),
  ('MAX_RISK_PER_TRADE_PCT',  1.0,    'Maximal riskierter Anteil des Modell-Portfolios je Einzeltrade, in Prozent (konservativ: 1%).'),
  ('MIN_REWARD_RISK_RATIO',   1.5,    'Mindest-Chance-Risiko-Verhaeltnis (Ziel-Abstand / Stop-Abstand). Darunter: hartes Veto, keine Eroeffnung.'),
  ('MAX_POSITION_VALUE_PCT',  20.0,   'Maximaler Anteil des Modell-Portfolios, der in eine einzelne theoretische Position fliessen darf, in Prozent.'),
  ('DEFAULT_SLIPPAGE_BPS',    10,     'Angenommene Slippage in Basispunkten (0.10%) je Trade, konservativ geschaetzt (Hebelprodukt-Spread nicht real bekannt).'),
  ('DEFAULT_FEES_BPS',        15,     'Angenommene Gebuehren in Basispunkten (0.15%) je Trade (Order-/Spread-Naeherung, kein echter Broker-Tarif).'),
  ('MAX_DATA_AGE_MINUTES',    1440,   'Maximal zulaessiges Alter des zugrunde liegenden Kurses in Minuten (24h), bevor Kursdaten als veraltet gelten.')
ON CONFLICT (config_key) DO NOTHING;

-- Risikofelder je theoretischer Position (additiv auf trading.recommendations,
-- ergaenzt die in sql/017 bereits vorbereiteten stop_price/target_price).
ALTER TABLE trading.recommendations
  ADD COLUMN IF NOT EXISTS risk_amount           NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS unit_risk             NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS theoretical_quantity  NUMERIC(18,4),
  ADD COLUMN IF NOT EXISTS position_value        NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS position_value_pct    NUMERIC(7,4),
  ADD COLUMN IF NOT EXISTS reward_risk_ratio      NUMERIC(10,4),
  ADD COLUMN IF NOT EXISTS estimated_fees        NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS estimated_slippage    NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS max_planned_loss      NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS risk_model_version    TEXT;

COMMENT ON COLUMN trading.recommendations.risk_amount IS 'model_portfolio_value * max_risk_per_trade_pct zum Eroeffnungszeitpunkt (EUR).';
COMMENT ON COLUMN trading.recommendations.unit_risk IS 'abs(entry_price - stop_price).';
COMMENT ON COLUMN trading.recommendations.theoretical_quantity IS 'floor(risk_amount / unit_risk) - theoretische Stueckzahl, rein rechnerisch, keine reale Order.';
COMMENT ON COLUMN trading.recommendations.position_value IS 'theoretical_quantity * entry_price.';
COMMENT ON COLUMN trading.recommendations.position_value_pct IS 'position_value / model_portfolio_value, in Prozent - gegen MAX_POSITION_VALUE_PCT geprueft.';
COMMENT ON COLUMN trading.recommendations.reward_risk_ratio IS 'abs(target_price - entry_price) / abs(entry_price - stop_price) - gegen MIN_REWARD_RISK_RATIO geprueft.';
COMMENT ON COLUMN trading.recommendations.estimated_fees IS 'position_value * DEFAULT_FEES_BPS/10000.';
COMMENT ON COLUMN trading.recommendations.estimated_slippage IS 'position_value * DEFAULT_SLIPPAGE_BPS/10000.';
COMMENT ON COLUMN trading.recommendations.max_planned_loss IS 'unit_risk * theoretical_quantity + estimated_fees + estimated_slippage - der geplante maximale Verlust inkl. Kostenpuffer.';
COMMENT ON COLUMN trading.recommendations.risk_model_version IS 'Versionskennung der Risikomodell-Formel (aktuell "welle1-v1"), damit spaetere Formelaenderungen alte Zeilen nicht falsch interpretieren.';
