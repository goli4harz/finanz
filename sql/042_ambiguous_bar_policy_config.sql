-- ============================================================================
-- 042 (Fehleranalyse E10, mittel, Haertungsauftrag 2026-08-02): fehlender
-- pipeline_config-Seed fuer AMBIGUOUS_BAR_POLICY_CODE
-- ============================================================================
-- Der Code-Fix vom 2026-08-01 (Commit 0aaf567, "Teil E: Workflow 14") las
-- bereits CFG.AMBIGUOUS_BAR_POLICY_CODE statt der bisherigen hartkodierten
-- Konstante, aber der Key war weder in "DB: Portfolio-Konfiguration laden
-- (Exec)"s SELECT-Liste noch in trading.pipeline_config vorhanden - CFG.
-- AMBIGUOUS_BAR_POLICY_CODE war also immer undefined, die Policy blieb de
-- facto weiterhin hartkodiert auf 'conservative_stop_first'. Additiv, keine
-- bestehende Zeile/Verhalten veraendert (Default 1 = identisch zum bisherigen
-- Verhalten).

INSERT INTO trading.pipeline_config (config_key, value_numeric, description)
VALUES
  ('AMBIGUOUS_BAR_POLICY_CODE', 1, 'Policy fuer Stop+Ziel in derselben Tageskerze (Fehleranalyse E9/E10, docs/AUSFUEHRUNGSMODELL.md): 1=conservative_stop_first (Default, unveraendertes Verhalten), 2=conservative_target_first.')
ON CONFLICT (config_key) DO NOTHING;
