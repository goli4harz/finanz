-- ============================================================================
-- 059 - Workflow 17: trading.simulation_orders um den zum Entscheidungszeitpunkt
-- bekannten Kontext erweitert (Entry-Zone, Stop/Target, Richtung, Strategie, Sektor).
--
-- Kontext: eine Order wird an Tag T erzeugt (Signal generiert, Positionsgroesse
-- berechnet), aber fruehestens an Tag T+1 ausgefuehrt - und dieser Fuellversuch kann
-- in einem SPAETEREN Worker-Tick (separate n8n-Ausfuehrung, kein gemeinsamer
-- Speicher zwischen Ticks) stattfinden, wenn die Order am Ende eines Tages-Pakets
-- erzeugt wurde. sql/057s urspruengliches simulation_orders-Schema hatte dafuer nur
-- `limit_price` (ein einzelner Wert) - weder die vollstaendige Entry-Zone
-- (low/high, fuer den Fuell-Check noetig) noch Stop/Target/Richtung/Strategie/
-- Sektor (fuer die Trade-Anlage nach dem Fill und die Portfolio-Risikopruefung
-- noetig) waren gespeichert. Diese Migration schliesst die Luecke additiv, statt
-- bestehende Spalten zweckzuentfremden.
--
-- Idempotent (ADD COLUMN IF NOT EXISTS) und wird NICHT automatisch ausgefuehrt -
-- manueller Lauf ueber "97 - Einmalig - Beliebige Query ausfuehren" wie alle
-- bisherigen Migrationen.
-- ============================================================================

BEGIN;

ALTER TABLE trading.simulation_orders
  ADD COLUMN IF NOT EXISTS direction TEXT,
  ADD COLUMN IF NOT EXISTS strategy TEXT,
  ADD COLUMN IF NOT EXISTS sektor TEXT,
  ADD COLUMN IF NOT EXISTS entry_zone_low NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS entry_zone_high NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS stop_price NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS target_price NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS time_stop_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS risk_amount NUMERIC(18,6),
  ADD COLUMN IF NOT EXISTS rule_version TEXT,
  ADD COLUMN IF NOT EXISTS configuration_version TEXT;

DO $$
BEGIN
  ALTER TABLE trading.simulation_orders DROP CONSTRAINT IF EXISTS chk_simulation_orders_direction;
  ALTER TABLE trading.simulation_orders ADD CONSTRAINT chk_simulation_orders_direction
    CHECK (direction IN ('long', 'short') OR direction IS NULL);
END $$;

COMMENT ON COLUMN trading.simulation_orders.entry_zone_low IS
  'Zusammen mit entry_zone_high der zum Signalzeitpunkt (Tag T) berechnete Fuellbereich - '
  'noetig, weil die Fuellpruefung an einem SPAETEREN Tag (T+1 oder spaeter, ggf. in einem '
  'anderen Worker-Tick ohne gemeinsamen Speicher) stattfindet.';
COMMENT ON COLUMN trading.simulation_orders.stop_price IS
  'Zum Signalzeitpunkt berechneter Stop - wird beim Fill unveraendert in '
  'trading.simulation_trades.stop_price_initial/current uebernommen.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('059', 'Workflow 17: simulation_orders um Entscheidungskontext (Richtung/Strategie/Sektor/Entry-Zone/Stop/Target) erweitert')
ON CONFLICT (version) DO NOTHING;

COMMIT;
