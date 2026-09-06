-- ============================================================================
-- 085 - Eigenstaendige Cost-Model-Config-Keys fuer den ungehebelten
-- Research-Backtest (historische-simulation-v2). WF17-v2-Reparatur.
-- ============================================================================
-- Bewiesen (Sitzungsdiagnose 2026-09-06): MINI_FUTURE_LEVERAGE wird im Legacy-
-- Pfad nie in einer Rechenoperation verwendet - die Simulation ist wirtschaftlich
-- ungehebelter Aktien-/Underlying-Handel MIT einem Mini-Future-artigen
-- Kostenmodell (Spread + Finanzierung auf den vollen Notionalwert). Um diese
-- Verwechslungsgefahr fuer v2 auszuschliessen, bekommt das Kostenmodell eigene,
-- eindeutig benannte Keys - MINI_FUTURE_SPREAD_PCT/MINI_FUTURE_FINANCING_PCT_PA
-- bleiben UNVERAENDERT fuer v1 erhalten (falls ein v1-Lauf je fortgesetzt wird).
--
-- v2-Kapitalmodell (dokumentiert, keine Rechenaenderung ausser der Umbenennung
-- der gelesenen Config-Keys):
--   LEVERAGE = 1 (kein Hebel-Term irgendwo im Code)
--   Positionswert = voller Notionalwert (fill.price * quantity)
--   Cash-Bindung  = voller Positionswert (+ Spread-Kosten haelftig bei Entry)
--   P&L           = Kursdifferenz * Stueckzahl - Spread (Entry+Exit) - Finanzierung
--   Exposure      = voller Notionalwert / Modellportfolio
--   Risiko        = tatsaechlicher Stop-Abstand * Stueckzahl (unveraendert wie v1)
-- ============================================================================

BEGIN;

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('RESEARCH_BACKTEST_SPREAD_COST_PCT', 0.4,
   'v2-Aequivalent zu MINI_FUTURE_SPREAD_PCT, aber EXPLIZIT als reines Kostenmodell fuer den '
   'ungehebelten historische-simulation-v2 Research-Backtest benannt - KEIN Hebel. '
   'MINI_FUTURE_SPREAD_PCT bleibt fuer v1 unveraendert erhalten.'),
  ('RESEARCH_BACKTEST_FINANCING_COST_PCT_PA', 2.5,
   'v2-Aequivalent zu MINI_FUTURE_FINANCING_PCT_PA, aber EXPLIZIT als reines Kostenmodell fuer '
   'den ungehebelten historische-simulation-v2 Research-Backtest benannt - KEIN Hebel. '
   'MINI_FUTURE_FINANCING_PCT_PA bleibt fuer v1 unveraendert erhalten.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('085', 'RESEARCH_BACKTEST_SPREAD_COST_PCT + RESEARCH_BACKTEST_FINANCING_COST_PCT_PA: eigenstaendig benanntes Kostenmodell fuer den ungehebelten v2-Research-Backtest, MINI_FUTURE_* bleibt fuer v1 unveraendert - WF17-v2-Reparatur')
ON CONFLICT (version) DO NOTHING;

COMMIT;
