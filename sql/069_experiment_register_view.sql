-- ============================================================================
-- Experimentierplattform, Punkt 5: Experiment-Register als View
-- ============================================================================
-- Auftragsvorgabe: ein Experiment soll als eine Zeile sichtbar sein (Hypothese,
-- Zeitraum/Konfiguration, Ergebnis, Entscheidung). Die Bausteine existieren
-- bereits verteilt auf drei Tabellen (backtest_runs, learning_rule_proposals,
-- simulation_events) - siehe EXPERIMENT_PLATFORM_REVIEW.md Punkt 5. Statt einer
-- neuen Parallelstruktur nur eine View, die zusammenfuehrt. Grain der View ist
-- ein backtest_run ("ein Experiment") - die daraus abgeleiteten Lernvorschlaege
-- (0..n je Lauf, ueber source_run_id) werden pro Lauf aggregiert, damit die
-- "ein Experiment = eine Zeile"-Eigenschaft erhalten bleibt, auch wenn ein
-- Lauf mehrere Vorschlaege ausgeloest hat.

-- Fehlendes Feld aus dem Auftrag: eine VOR dem Test formulierte Hypothese.
-- 'reason' auf learning_rule_proposals ist eine NACHTRAEGLICHE Begruendung des
-- Lernagenten fuer einen bereits fertigen Vorschlag - keine vorab formulierte
-- Hypothese. Nullable, wird von den Lernagenten (09b/09c) aktuell noch nicht
-- befuellt - das ist eine separate, spaetere Aenderung an deren Prompts, hier
-- nur das Schema-Feld dafuer.
ALTER TABLE trading.learning_rule_proposals
  ADD COLUMN IF NOT EXISTS hypothesis TEXT;

COMMENT ON COLUMN trading.learning_rule_proposals.hypothesis IS
  'Vor dem auslösenden Backtest/der Auswertung formulierte Erwartung ("was soll dieser Test zeigen") '
  '- im Unterschied zu reason (nachtraegliche Begruendung des fertigen Vorschlags). Aktuell von '
  'keinem Workflow befuellt; Feld fuer eine spaetere Prompt-Erweiterung der Lernagenten (09b/09c) '
  'vorbereitet, siehe EXPERIMENT_PLATFORM_REVIEW.md Punkt 5.';

CREATE OR REPLACE VIEW trading.v_experiment_register AS
SELECT
  br.id                              AS run_id,
  br.backtest_id,
  br.run_type,
  br.data_category,
  br.strategy_filter,
  br.name,
  br.description,
  br.status                          AS run_status,
  br.out_of_sample_locked,
  br.start_date,
  br.end_date,
  br.started_at,
  br.finished_at,
  br.trade_count,
  br.results_json,
  br.config_snapshot_json,
  br.created_by,
  COALESCE(p.proposals_json, '[]'::jsonb) AS proposals_json,
  COALESCE(p.proposal_count, 0)           AS proposal_count,
  p.latest_proposal_status,
  p.latest_proposal_activated_at,
  ev.last_event_type,
  ev.last_event_at
FROM trading.backtest_runs br
LEFT JOIN LATERAL (
  SELECT
    jsonb_agg(jsonb_build_object(
      'proposal_id', lrp.id,
      'hypothesis', lrp.hypothesis,
      'reason', lrp.reason,
      'proposal_type', lrp.proposal_type,
      'target_type', lrp.target_type,
      'target_value', lrp.target_value,
      'current_value', lrp.current_value,
      'proposed_value', lrp.proposed_value,
      'sample_size', lrp.sample_size,
      'confidence_level', lrp.confidence_level,
      'status', lrp.status,
      'created_at', lrp.created_at,
      'reviewed_at', lrp.reviewed_at,
      'reviewed_by', lrp.reviewed_by,
      'activated_at', lrp.activated_at
    ) ORDER BY lrp.created_at) AS proposals_json,
    COUNT(*) AS proposal_count,
    (array_agg(lrp.status ORDER BY lrp.created_at DESC))[1]       AS latest_proposal_status,
    (array_agg(lrp.activated_at ORDER BY lrp.created_at DESC))[1] AS latest_proposal_activated_at
  FROM trading.learning_rule_proposals lrp
  WHERE lrp.source_run_id = br.id
) p ON TRUE
LEFT JOIN LATERAL (
  SELECT se.event_type AS last_event_type, se.event_time AS last_event_at
  FROM trading.simulation_events se
  WHERE se.simulation_run_id = br.id
  ORDER BY se.event_time DESC
  LIMIT 1
) ev ON TRUE;

COMMENT ON VIEW trading.v_experiment_register IS
  'Experimentierplattform Punkt 5: ein backtest_run = eine Zeile ("ein Experiment"). Fuehrt '
  'backtest_runs (Zeitraum/Konfiguration/Ergebnis), die daraus abgeleiteten '
  'learning_rule_proposals (0..n, per source_run_id, als JSON-Array aggregiert) und das letzte '
  'simulation_events-Ereignis zusammen. Keine neue Tabelle, keine eigene Schreiblogik noetig - '
  'nur lesend ueber bestehende Daten.';

-- Nachtrag: sql/067 und sql/068 haben sich beim Live-Einspielen (per WF97-Diagnose-Webhook,
-- ausserhalb des normalen Migrations-Workflows 99) nicht selbst in schema_migrations
-- eingetragen - Abweichung von der seit sql/044 geltenden Konvention. Hier nachgeholt, die
-- beiden Dateien im Repo wurden nachtraeglich um dieselbe Registrierung ergaenzt.
INSERT INTO trading.schema_migrations (version, description) VALUES
  ('067', 'strategy_regime_matrix: active-Spalte ersetzt rule_version als Kriterium fuer die aktuell gueltige Zeile (Experimentierplattform Punkt 2)'),
  ('068', 'market_context_history: Point-in-Time-Revisionierung analog fundamentals_history/technical_signals_history (Experimentierplattform Punkt 4)'),
  ('069', 'Experiment-Register als View (trading.v_experiment_register) + hypothesis-Spalte auf learning_rule_proposals (Experimentierplattform Punkt 5)')
ON CONFLICT (version) DO NOTHING;
