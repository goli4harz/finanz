-- ============================================================================
-- WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): Sizing-Audit-Trail
-- auf trading.paper_trades - bisher nur auf simulation_orders/simulation_trades
-- (sql/060) vorhanden.
-- ============================================================================
-- Job A (Engine-Pfad) kappt die Positionsgroesse ab jetzt statt sie bei
-- Limitueberschreitung komplett zu verwerfen (Nutzerentscheidung: "kappen wie
-- WF17", siehe TRADING_ENGINE_MIGRATION.md Abschnitt 7 / Architekturfragen
-- Punkt 1). Ohne diese Spalten waere nicht mehr nachvollziehbar, WIE STARK
-- ein Trade tatsaechlich gekappt wurde - genau der Audit-Trail, den sql/060
-- fuer WF17 bereits eingefuehrt hat, jetzt auch fuer WF14.
--
-- theoretical_quantity existiert auf paper_trades bereits (WF06s eigene,
-- ungeprüfte Ausgangsgroesse) - wird durch die Engine-Migration NICHT
-- veraendert. Die beiden neuen Spalten sind zusaetzlich, kein Ersatz:
-- theoretical_risk_amount = das zu theoretical_quantity gehoerige Risiko
-- (Engine-Ausgabe, ungekappt), clamp_reason = welches Limit (falls ueberhaupt
-- eines) das tatsaechliche risk_amount/position_value/theoretical_quantity
-- nach unten gezogen hat.
--
-- Beide NULLABLE: der alte Job-A-Pfad (Flag FALSE) kennt sie nicht.

ALTER TABLE trading.paper_trades
  ADD COLUMN IF NOT EXISTS theoretical_risk_amount NUMERIC,
  ADD COLUMN IF NOT EXISTS clamp_reason TEXT;

COMMENT ON COLUMN trading.paper_trades.theoretical_risk_amount IS
  'Risikobetrag VOR Kappung durch ein Portfolio-Limit (Engine-Ausgabe SizingResult.'
  'theoretical_risk_amount). NULL = Trade wurde nie ueber den Engine-Pfad '
  '(TRADING_ENGINE_PORTFOLIO_CHECK_ENABLED=TRUE) verarbeitet.';
COMMENT ON COLUMN trading.paper_trades.clamp_reason IS
  'Welches Limit die tatsaechliche Positionsgroesse gekappt hat (z.B. SECTOR_LIMIT, '
  'SINGLE_POSITION_LIMIT) - NULL = nicht gekappt ODER nie ueber den Engine-Pfad '
  'verarbeitet (siehe theoretical_risk_amount).';

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('080', 'theoretical_risk_amount + clamp_reason auf paper_trades fuer Job-A-Sizing-Audit-Trail (WF14-Migration, Kappen statt Verwerfen)')
ON CONFLICT (version) DO NOTHING;
