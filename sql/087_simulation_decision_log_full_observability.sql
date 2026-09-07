-- ============================================================================
-- 087 - Erweitert trading.simulation_decision_log um vollstaendige Observability-
-- Felder fuer WF17-Kandidaten-Entscheidungen (J2, Sitzungsdiagnose 2026-09-07).
-- ============================================================================
-- Hintergrund: das urspruengliche Schema (Migration 084) hatte nur 13 Spalten
-- (Identitaet + decision/reason + raw_score/theoretical_quantity/actual_quantity/
-- position_value) - ausreichend fuer eine grobe Ja/Nein-Entscheidung, aber nicht
-- fuer eine spaetere Ablation ohne Rekonstruktion aus simulation_trades. Diese
-- Migration ist REIN ADDITIV (nur ADD COLUMN IF NOT EXISTS, nullable, keine
-- Defaults, keine bestehende Spalte/Zeile veraendert) und REIN OBSERVABILITY -
-- keine Handelsentscheidung wird durch dieses Schema selbst beeinflusst.
--
-- Traceability-Spalten (simulation_recommendation_id/order_id/trade_id) sind
-- bewusst nullable ohne FK-Constraint: eine Decision-Log-Zeile kann entstehen,
-- bevor die zugehoerige Recommendation/Order/Trade ueberhaupt existiert (z.B.
-- REJECTED/BLOCKED-Faelle haben nie eine), und ein ACCEPTED-Fall kennt seine
-- eigenen IDs zum Zeitpunkt des Inserts noch nicht (die werden erst durch die
-- nachgelagerte CTE in "Baue SQL fuer Paket-Ergebnisse" vergeben). Kein FK in
-- diesem Schritt, wie vorgegeben.
--
-- diagnostics_json ist bewusst ein Sammel-Feld fuer Strategie-spezifische
-- Zusatzwerte (z.B. News-Evidence, Fundamentaldaten, Indikator-Zwischenwerte),
-- NICHT ein Ausweichort fuer Werte, die eigentlich eine eigene Spalte brauchen -
-- die oben explizit benannten Kernfelder bleiben eigene Spalten.
-- ============================================================================

BEGIN;

-- SIGNAL / REGIME
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS adjusted_score numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS market_regime text;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS combined_regime text;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS fit_multiplier numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS direction_regime_alignment text;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS rule_version text;

-- PREIS / GEOMETRIE
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS entry_reference_price numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS entry_zone_low numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS entry_zone_high numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS stop_price numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS target_price numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS reward_risk_ratio numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS atr_value numeric;

-- SIZING
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS risk_amount numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS unit_risk numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS quantity_by_risk numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS quantity_by_value numeric;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS limiting_factor text;

-- DECISION
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS decision_stage text;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS sequence_index integer;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS blockers_json jsonb;

-- TRACEABILITY (bewusst ohne FK-Constraint, siehe Kommentar oben)
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS simulation_recommendation_id bigint;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS simulation_order_id bigint;
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS simulation_trade_id text;

-- FUTURE-PROOF DIAGNOSTICS
ALTER TABLE trading.simulation_decision_log ADD COLUMN IF NOT EXISTS diagnostics_json jsonb;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('087', 'trading.simulation_decision_log: 25 additive Observability-Spalten (Signal/Regime, Preis/Geometrie, Sizing, Decision-Stage, Traceability, diagnostics_json) fuer vollstaendige Kandidaten-Ablation ohne Trade-Rekonstruktion - J2 Sitzungsdiagnose 2026-09-07')
ON CONFLICT (version) DO NOTHING;

COMMIT;
