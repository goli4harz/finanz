-- Haertung Welle 1-3, Phase 14: Feature-Flags fuer die gesteuerte, stufenweise Aktivierung
-- von 13 (Markt-Screener) und 14 (Portfolio-Risiko/Paper-Trading) ueber den Orchestrator (00).
-- Default FALSE (deaktiviert) fuer alle drei - der Orchestrator liest diese Werte jetzt in
-- "Config: DRY_RUN laden"/"Kontext zusammenfuehren" und ueberspringt die jeweilige Stufe
-- vollstaendig, solange das Flag nicht explizit auf TRUE gesetzt wird (Sicherheitsregel:
-- keine Aktivierung von 13/14, bevor deren DRY_RUN-Abnahmetests erfolgreich sind).
-- Additiv, idempotent (ON CONFLICT DO NOTHING - aendert nichts an bereits vorhandenen Werten).

BEGIN;

INSERT INTO trading.pipeline_config (config_key, value_bool, description)
VALUES
  ('ENABLE_MARKET_SCANNER', FALSE, 'Schaltet Stufe 13 (Markt-Screener) im Orchestrator (00) frei. Bleibt FALSE bis zum erfolgreichen Abschluss der Testsuite D (Haertung Welle 1-3, Phase 17/18).'),
  ('ENABLE_PAPER_TRADING', FALSE, 'Schaltet Stufe 14 (Portfolio-Risiko und Paper-Trading) im Orchestrator (00) frei. Bleibt FALSE bis ausreichend abgeschlossene Paper Trades und ein belastbares Out-of-Sample-Verfahren vorliegen (Sicherheitsregel, Phase 17/18).'),
  ('ENABLE_TRADE_LEARNING', FALSE, 'Reserviert fuer die kuenftige Aktivierung von 09b (Lernagent). 09b bleibt gemaess Sicherheitsregel inaktiv; dieses Flag wird aktuell von keinem Workflow gelesen, ist aber bereits Teil des einheitlichen Feature-Flag-Schemas (Haertung Welle 1-3, Phase 14/15).')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('056', 'Haertung Welle 1-3, Phase 14: Feature-Flags ENABLE_MARKET_SCANNER/ENABLE_PAPER_TRADING/ENABLE_TRADE_LEARNING (Default FALSE)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
