-- Workflow 17: echter Trailing-Stop (statt fixem ATR-Stop) + Mini-Future-Kostenmodell
-- (Hebel, Spread, Finanzierung) statt des bisherigen Aktien-Kommission/Slippage-Modells.
-- Nutzervorgabe 2026-08-04: 3-5 Tage Vorausschau (mean_reversion-Horizont dafuer bereits im
-- Code von 3 auf 5 Tage angepasst, reine Zahl, keine neue Strategie), Hebel 4x, Trailing-Stop
-- fuer long UND short (Abstand einmalig bei Einstieg fixiert = ATR-basierter Anfangs-Stop-
-- Abstand, zieht danach nur in die guenstige Richtung nach - exakt wie eine echte Trailing-
-- Order beim Broker, siehe recherchierte Funktionsweise), Kosten als Durchschnittswert:
-- Spread 0,4% + Finanzierung ca. 2,5%/Jahr aufs Hebel-Exposure.

BEGIN;

ALTER TABLE trading.simulation_trades
  ADD COLUMN IF NOT EXISTS extreme_price_since_entry NUMERIC(18,6);

COMMENT ON COLUMN trading.simulation_trades.extreme_price_since_entry IS
  'Hoechster Schlusskurs seit Einstieg bei Long-Positionen bzw. niedrigster bei Short - '
  'Referenzpunkt fuer den Trailing-Stop. trail_distance selbst wird NICHT gespeichert, sondern '
  'bei jedem Tick aus simulated_entry_price - stop_price_initial neu abgeleitet (beide bereits '
  'vorhandene, unveraenderliche Spalten).';

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('MINI_FUTURE_LEVERAGE', 4, 'Workflow 17: angenommener Hebel fuer den Handel via Mini-Futures - fliesst aktuell nur informativ ein, die Risiko-Positionsgroessenformel bleibt unveraendert auf das zugrundeliegende Exposure bezogen.'),
  ('MINI_FUTURE_SPREAD_PCT', 0.4, 'Workflow 17: angenommener Durchschnitts-Spread (in Prozent des Positionswerts, gesamter Hin-und-Rueck-Handel) fuer Mini-Futures auf die gehandelten Blue-Chip-Basiswerte - haeftig bei Einstieg und Ausstieg belastet.'),
  ('MINI_FUTURE_FINANCING_PCT_PA', 2.5, 'Workflow 17: angenommene jaehrliche Finanzierungskosten (in Prozent p.a.) aufs Hebel-Exposure (position_value) bei Mini-Futures, anteilig nach tatsaechlicher Haltedauer bei Ausstieg berechnet.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('062', 'Workflow 17: Trailing-Stop (extreme_price_since_entry) + Mini-Future-Kostenmodell (Hebel/Spread/Finanzierung), mean_reversion-Horizont 3->5 Tage')
ON CONFLICT (version) DO NOTHING;

COMMIT;
