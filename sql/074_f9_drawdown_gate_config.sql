-- F9 (Haertungsauftrag "Vollstaendige Fehlerbereinigung", zurueckgestellt 2026-08-02,
-- umgesetzt 2026-08-23): Stabilitaet-ueber-Zeit-Gate im Lernagenten 09b - Rolling-Drawdown
-- je Strategie ueber die geschlossenen Paper Trades (realized_r_multiple), zusaetzliches
-- hartes Gate analog zu F6 (Regime-Konzentration) und F7 (ambiguous_pct). Berechnung selbst
-- lebt im Workflow (neue Nodes "Baue Drawdown-Query (Trades)" / "SQL: Drawdown je Strategie
-- (Trades)"), diese Migration seedet nur die beiden Konfigurationswerte mit konservativen
-- Startwerten (analog zu sql/043s MAX_AMBIGUOUS_PCT_FOR_PROPOSAL-Konvention).
--
-- Bewusst NICHT umgesetzt: die urspruenglich mitgedachte Veto-Rate-Komponente
-- ("Anteil blockierter Signale je Strategie") - trading.recommendation_veto_log hat keine
-- Strategie-Spalte (nur ticker/action/blockers_json/created_at), eine Zuordnung Veto->Strategie
-- waere ein eigenstaendiger Schema-Fund/Folgeauftrag, kein Teil dieses Gates.

INSERT INTO trading.pipeline_config (config_key, value_numeric, description) VALUES
  ('F9_DRAWDOWN_WINDOW_DAYS', 180,
   'F9 (Haertungsauftrag): Rolling-Fenster in Tagen fuer die Drawdown-Stabilitaetspruefung je Strategie im Lernagenten 09b.'),
  ('F9_MAX_DRAWDOWN_R', 6.0,
   'F9 (Haertungsauftrag): Maximaler erlaubter Peak-zu-Tiefpunkt-Drawdown in R-Multiples je Strategie im Fenster, darueber wird die Strategie von neuen Lernvorschlaegen ausgeschlossen.')
ON CONFLICT (config_key) DO NOTHING;

INSERT INTO trading.schema_migrations (version, description) VALUES
  ('074', 'F9 Drawdown-Gate: Konfigurationswerte fuer 09b (F9_DRAWDOWN_WINDOW_DAYS, F9_MAX_DRAWDOWN_R)')
ON CONFLICT (version) DO NOTHING;
