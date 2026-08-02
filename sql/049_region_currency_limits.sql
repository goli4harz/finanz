-- ============================================================================
-- 049 (Welle-3-Abgleich 2026-08-02, Fund 2/5): Region- und Waehrungs-
-- Expositionslimits fuer Workflow 14, Job A
-- ============================================================================
-- Der Auftragstext nennt "Exposition je Region" und "Exposition je Waehrung"
-- explizit in der Pruefliste vor den 9 benannten Konfigurationswerten - beide
-- existierten bisher als Gate ueberhaupt nicht (region wurde nur fuer das
-- Regime-Lookup verwendet, nicht als Limit). MAX_NON_EUR_EXPOSURE_PCT statt
-- eines allgemeinen "MAX_CURRENCY_EXPOSURE_PCT": bei einem aktuell 100%
-- EUR-denominierten Datenuniversum (trading.stock_instruments.currency)
-- wuerde ein Limit auf die Basiswaehrung selbst jede zweite Position
-- blockieren - das Gate soll erkennbare Fremdwaehrungskonzentration fangen,
-- nicht die Basiswaehrung selbst.

BEGIN;

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
  ('MAX_REGION_EXPOSURE_PCT', 60.0, 'Maximaler Anteil des Modell-Portfolios in einer einzelnen Region (Europa/USA/global, aus trading.stock_instruments.exchange abgeleitet), in Prozent (Welle-3-Abgleich, AP5).'),
  ('MAX_NON_EUR_EXPOSURE_PCT', 30.0, 'Maximaler Anteil des Modell-Portfolios in Nicht-EUR-Positionen, in Prozent - aktuell folgenlos (alle Bestandsticker EUR-denominiert), schema-bereit fuer kuenftige Fremdwaehrungspositionen (Welle-3-Abgleich, AP5).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('049', 'Region-/Waehrungs-Expositionslimits (Welle-3-Abgleich Fund 2/5)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
