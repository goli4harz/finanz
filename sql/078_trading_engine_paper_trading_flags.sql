-- ============================================================================
-- WF14-Migration (TRADING_ENGINE_MIGRATION.md Abschnitt 7): zwei Feature-Flags
-- fuer die neuen trading_engine-Pfade in Workflow 14 (Job A und Job B)
-- ============================================================================
-- Steuert je eine IF-Weiche in Workflow 14, analog zum Muster aus sql/070
-- (Workflow 17): der bestehende, eingebettete JS-Code bleibt vollstaendig
-- unveraendert bestehen, die neuen Nodes rufen stattdessen die neuen,
-- schlankeren Endpunkte POST /engine/portfolio/check-and-size (Job A) bzw.
-- POST /engine/execution/process-trades (Job B) auf.
--
-- BEWUSST ZWEI GETRENNTE FLAGS statt eines gemeinsamen (anders als sql/070,
-- das nur einen Pfad hat): Job A (welche Trades ueberhaupt entstehen) und
-- Job B (Fill/Exit/PnL bereits committierten Geldes) sind unterschiedliche
-- Risikoflaechen bei einem LIVE-Produktivsystem (Workflow 14 ist kein
-- Backtest wie 17) - unabhaengig schaltbar, unabhaengig zurueckrollbar.
--
-- Default FALSE fuer beide: die neuen Pfade werden zunaechst nur verdrahtet
-- ("dormant deploy"), nicht aktiv genutzt, bis der Dry-Run-Vergleich aus
-- TRADING_ENGINE_MIGRATION.md Abschnitt 7 (Rollout & Verifikation) je Flag
-- abgeschlossen und vom Nutzer bestaetigt ist. Umschalten danach je ein
-- einzeiliges UPDATE, kein Workflow-Redeploy.

INSERT INTO trading.pipeline_config (config_key, value_bool, description) VALUES
  ('TRADING_ENGINE_PORTFOLIO_CHECK_ENABLED', FALSE,
   'Workflow 14 Job A: steuert, ob "Job A: Portfoliopruefung + Trade-Anlage (Engine)" (ruft POST '
   '/engine/portfolio/check-and-size der trading_engine je Kandidat auf) statt des bestehenden '
   'eingebetteten JS-Codes verwendet wird. STRATEGY_DEACTIVATED bleibt in beiden Faellen ein '
   'n8n-seitiger Vorfilter (kein Engine-Aequivalent). FALSE = alter Pfad (Default bei Einfuehrung, '
   'bis der Dry-Run-Vergleich bestaetigt ist).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.pipeline_config (config_key, value_bool, description) VALUES
  ('TRADING_ENGINE_EXECUTION_ENABLED', FALSE,
   'Workflow 14 Job B: steuert, ob "Job B: Ausfuehrung/Exit simulieren (Engine)" (ruft POST '
   '/engine/execution/process-trades der trading_engine im Batch auf) statt des bestehenden '
   'eingebetteten JS-Codes verwendet wird. Bringt bei TRUE zwei echte Verhaltensaenderungen mit: '
   'Mini-Future-Kostenmodell statt einfacher Gebuehren-Basispunkte, und erstmals einen '
   'Trailing-Stop fuer Live-Paper-Trading (siehe TRADING_ENGINE_MIGRATION.md Abschnitt 7). '
   'FALSE = alter Pfad (Default bei Einfuehrung, bis der Dry-Run-Vergleich bestaetigt ist).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('078', 'TRADING_ENGINE_PORTFOLIO_CHECK_ENABLED + TRADING_ENGINE_EXECUTION_ENABLED-Flags fuer die WF14-Migration (Job A/Job B) auf die trading_engine')
ON CONFLICT (version) DO NOTHING;
