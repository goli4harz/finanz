-- ============================================================================
-- 060 - Workflow 17: Positionsgroesse KAPPEN statt VERWERFEN (Nutzervorgabe
-- 2026-08-03) + Sektor/Region-Tracking auf simulation_trades.
--
-- Kontext: der erste Live-Test (sql/057-Schema, reine 1:1-Portierung aus 06/14)
-- zeigte, dass die urspruengliche "risikobasiert berechnen, bei Ueberschreitung
-- eines Limits VERWERFEN"-Logik bei engen ATR-Stops praktisch JEDES Signal
-- blockierte (37-64% Positionswert vs. 8%-Einzelpositionslimit) - unabhaengig
-- von der Anzahl der Instrumente im Universum, also ein Rechen-, kein
-- Diversifikationsproblem. Neue Formel:
--   final_quantity = floor(min(
--     risk_based_quantity, max_single_position_quantity, remaining_portfolio_quantity,
--     remaining_sector_quantity, remaining_region_quantity
--   ))
-- Das Risikobudget ist eine Obergrenze, kein Pflichtziel - ein Trade wird nicht
-- allein deshalb verworfen, weil das tatsaechliche Risiko nach der Kappung unter
-- das Ziel-% faellt. Theoretische (unclamped) und tatsaechliche (nach Kappung)
-- Werte werden GETRENNT gespeichert, der bindende Kappungsgrund wird protokolliert.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS) und wird NICHT automatisch ausgefuehrt -
-- manueller Lauf ueber "97 - Einmalig - Beliebige Query ausfuehren".
-- ============================================================================

BEGIN;

-- trading.simulation_trades: bestehende Spalten theoretical_quantity/risk_amount behalten
-- ihre Bedeutung (theoretical_quantity = unclamped risikobasierte Menge, risk_amount =
-- TATSAECHLICH eingegangenes Risiko nach Kappung, so wie sie bereits in der
-- Portfolio-Risikoaggregation verwendet werden) - neu hinzu kommen die jeweilige
-- Gegenzahl plus der Kappungsgrund und Sektor/Region fuer die Kappungsformel selbst.
ALTER TABLE trading.simulation_trades
  ADD COLUMN IF NOT EXISTS actual_quantity NUMERIC(18,4),
  ADD COLUMN IF NOT EXISTS theoretical_risk_amount NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS clamp_reason TEXT,
  ADD COLUMN IF NOT EXISTS sektor TEXT,
  ADD COLUMN IF NOT EXISTS region TEXT;

COMMENT ON COLUMN trading.simulation_trades.theoretical_quantity IS
  'Unclamped, rein risikobasierte Stueckzahl (Risikobudget / Stop-Abstand) - VOR jeder '
  'Kappung durch Positions-/Sektor-/Portfolio-/Regionslimits.';
COMMENT ON COLUMN trading.simulation_trades.actual_quantity IS
  'Tatsaechlich gehandelte Stueckzahl nach Kappung auf das bindende Limit (siehe '
  'clamp_reason) - das ist die Menge, die tatsaechlich in position_value/risk_amount '
  'eingeht, IMMER abgerundet (floor).';
COMMENT ON COLUMN trading.simulation_trades.risk_amount IS
  'TATSAECHLICHES eingegangenes Risiko (actual_quantity * unit_risk) - kann unter dem '
  'Ziel-Risikoprozentsatz liegen, wenn die Position gekappt wurde. Fuer den vollen '
  'Zielwert siehe theoretical_risk_amount.';
COMMENT ON COLUMN trading.simulation_trades.clamp_reason IS
  'Welches Limit die Positionsgroesse gebunden hat: NULL (nicht gekappt, risikobasierte '
  'Menge passte bereits) | SINGLE_POSITION_LIMIT | TOTAL_RISK_LIMIT | SECTOR_LIMIT | '
  'REGION_LIMIT.';

-- trading.simulation_orders (sql/059 hat bereits quantity/risk_amount/sektor angelegt -
-- deren Bedeutung wird hier ebenso auf "tatsaechlich nach Kappung" festgelegt) plus die
-- fehlende theoretische Gegenzahl und Region.
ALTER TABLE trading.simulation_orders
  ADD COLUMN IF NOT EXISTS theoretical_quantity NUMERIC(18,4),
  ADD COLUMN IF NOT EXISTS theoretical_risk_amount NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS clamp_reason TEXT,
  ADD COLUMN IF NOT EXISTS region TEXT;

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('MAX_REGION_EXPOSURE_PCT', 60.0, 'Kappungsgrenze fuer Workflow 17s Positionsgroessen-Formel: maximaler Anteil des Modellportfolios in einer Region (XETRA->Europa, NASDAQ/NYSE->USA, sonst global) - Wert uebernommen aus der dokumentierten 14-Konfiguration.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('060', 'Workflow 17: Positionsgroesse kappen statt verwerfen (theoretical_/actual_quantity, theoretical_risk_amount, clamp_reason, sektor/region auf simulation_trades+orders)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
