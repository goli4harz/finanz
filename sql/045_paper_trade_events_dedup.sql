-- ============================================================================
-- 045 (Fehleranalyse B9, niedrig-mittel, Haertungsauftrag 2026-08-02):
-- deterministische run_id + UNIQUE-Constraints gegen Duplikate bei
-- wiederholten Laeufen von Workflow 14
-- ============================================================================
-- B9: run_id in 14 war bisher 'p14-'+heute+'-'+Date.now() (Job A) bzw.
-- 'stress-'+heute+'-'+Date.now() (Job C) - jeder Lauf, auch am selben Tag,
-- bekam eine andere run_id, ein wiederholter Lauf konnte also nie als
-- Duplikat erkannt werden. Job B hatte gar keinen run_id-Begriff.
-- portfolio_risk_checks/stress_scenarios/paper_trade_events hatten dazu
-- passend auch keine UNIQUE-Constraints. Diese Migration ist rein additiv
-- (Spalte + Constraint), die Code-Seite (deterministische run_id, ON
-- CONFLICT DO NOTHING) ist Teil desselben Commits in Workflow 14.
--
-- FIX 2026-08-02 (Fehleranalyse G2): explizit in BEGIN/COMMIT gefasst, statt
-- sich auf implizites Postgres-Node-Verhalten zu verlassen - bei einem
-- Fehler mitten in der Sequenz (z.B. CREATE UNIQUE INDEX faellt auf einen
-- Bestandsduplikat) werden so alle vorherigen Schritte dieser Migration
-- ebenfalls zurueckgerollt statt teilweise angewendet zu bleiben.

BEGIN;

-- paper_trade_events: neue business_date-Spalte (deterministisch statt der
-- bisherigen event_time DEFAULT now()) als Grundlage fuer den Dedup-Schluessel.
ALTER TABLE trading.paper_trade_events
  ADD COLUMN IF NOT EXISTS business_date DATE;

-- Backfill bestehender Zeilen aus event_time (best-effort - fuer die
-- historischen Zeilen ist das identisch zum tatsaechlichen Handelstag, da
-- 14 bisher nur einmal taeglich lief).
UPDATE trading.paper_trade_events
SET business_date = event_time::date
WHERE business_date IS NULL;

-- Harte DB-Garantie: pro Trade+Ereignistyp+Tag hoechstens eine Zeile. Faellt
-- CREATE UNIQUE INDEX auf einen bereits vorhandenen Duplikat-Konflikt, macht
-- das den Konflikt sichtbar statt ihn zu verschleiern (gleiches Prinzip wie
-- sql/039s ux_paper_trade_costs_trade_costtype).
CREATE UNIQUE INDEX IF NOT EXISTS ux_paper_trade_events_trade_type_date
  ON trading.paper_trade_events (trade_id, event_type, business_date);

COMMENT ON COLUMN trading.paper_trade_events.business_date IS
  'Handelstag des Ereignisses (deterministisch, nicht aus event_time abgeleitet) - Grundlage fuer die Dedup-Garantie gegen wiederholte Laeufe (Fehleranalyse B9).';

-- portfolio_risk_checks: mit deterministischer run_id ('p14a-'+business_date)
-- ist ein Wiederholungslauf am selben Tag erkennbar.
CREATE UNIQUE INDEX IF NOT EXISTS ux_portfolio_risk_checks_run_ticker
  ON trading.portfolio_risk_checks (run_id, ticker);

-- stress_scenarios: gleiches Prinzip mit 'stress-'+business_date.
CREATE UNIQUE INDEX IF NOT EXISTS ux_stress_scenarios_run_scenario
  ON trading.stress_scenarios (run_id, scenario_name);

COMMIT;
