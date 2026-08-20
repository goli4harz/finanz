-- ============================================================================
-- Phase 8 (TRADING_ENGINE_MIGRATION.md): Feature-Flag fuer den neuen
-- trading_engine-Pfad in Workflow 17
-- ============================================================================
-- Steuert die IF-Weiche in Workflow 17 zwischen dem bestehenden, eingebetteten
-- JS-Code ("Verarbeite Tage-Paket") und dem neuen Node, der pro Simulationstag
-- POST /engine/simulation/step aufruft ("Verarbeite Tage-Paket (Engine)").
-- Default FALSE: der neue Pfad wird zunaechst NUR verdrahtet, aber nicht
-- aktiv genutzt, bis der manuelle Vergleichslauf aus TRADING_ENGINE_MIGRATION.md
-- (Schritt 5) abgeschlossen und vom Nutzer bestaetigt ist. Umschalten danach
-- ein einzeiliges UPDATE, kein Workflow-Redeploy.

INSERT INTO trading.pipeline_config (config_key, value_bool, description) VALUES
  ('TRADING_ENGINE_STEP_ENABLED', FALSE,
   'Workflow 17: steuert, ob "Verarbeite Tage-Paket (Engine)" (ruft POST /engine/simulation/step '
   'der trading_engine auf) statt des bestehenden eingebetteten JS-Codes verwendet wird. Greift '
   'nur zusaetzlich zu und unabhaengig von runCtx.news_enabled=false (News-Laeufe nutzen immer '
   'den alten Pfad, siehe TRADING_ENGINE_MIGRATION.md Abschnitt 1.3). FALSE = alter Pfad '
   '(Default bei Einfuehrung, bis der manuelle Vergleichslauf bestaetigt ist).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('070', 'TRADING_ENGINE_STEP_ENABLED-Flag fuer die Phase-8-Migration von Workflow 17 auf die trading_engine')
ON CONFLICT (version) DO NOTHING;
