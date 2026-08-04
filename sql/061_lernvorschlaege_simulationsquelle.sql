-- Phase 7 (Historische Simulation): Lernvorschlaege koennen jetzt zusaetzlich zu echten
-- Live-Trades (trading.paper_trades) auch aus einem abgeschlossenen Walk-Forward-Simulationslauf
-- (trading.simulation_trades) abgeleitet werden - der eigentliche Grund fuer die historische
-- Simulation ("schneller lernen als in Echtzeit"). Umgesetzt als eigener Workflow
-- "09c - Lernagent Handelsstrategien (Simulation)" statt Aenderung an der LIVE-Produktions-
-- Workflow 09b (gleiches Prinzip wie Workflow 16b als eigene Kopie von 03s KI-Bewertung statt
-- Refactor der Live-Newspipeline).
--
-- Audit-Trail: jeder Vorschlag traegt jetzt sichtbar, ob er aus echten Trades oder einer
-- Simulation stammt, und bei Simulation aus welchem Lauf - Pflicht fuer die manuelle Freigabe
-- in Workflow 12 (Lernvorschlag-Freigabe), damit ein Mensch weiss, worauf er sich verlaesst.

BEGIN;

ALTER TABLE trading.learning_rule_proposals
  ADD COLUMN IF NOT EXISTS data_source TEXT NOT NULL DEFAULT 'live'
    CHECK (data_source IN ('live', 'simulation')),
  ADD COLUMN IF NOT EXISTS source_run_id BIGINT REFERENCES trading.backtest_runs(id);

COMMENT ON COLUMN trading.learning_rule_proposals.data_source IS
  'Woher die zugrundeliegende Trade-Statistik stammt: live (trading.paper_trades, wie bisher '
  'ausschliesslich) oder simulation (trading.simulation_trades eines Walk-Forward-Laufs).';
COMMENT ON COLUMN trading.learning_rule_proposals.source_run_id IS
  'Nur bei data_source=simulation gesetzt: der Explorations-Lauf (backtest_runs.id), aus '
  'dessen simulation_trades die Statistik berechnet wurde. NULL bei data_source=live.';

-- Index fuer die neue Steuerzentrale-Aktion ("Lernvorschlag aus diesem Lauf ableiten") -
-- Duplikatspruefung "gibt es fuer diesen Lauf schon einen offenen Vorschlag" braucht das.
CREATE INDEX IF NOT EXISTS ix_learning_rule_proposals_source_run
  ON trading.learning_rule_proposals (source_run_id) WHERE source_run_id IS NOT NULL;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('061', 'learning_rule_proposals: data_source/source_run_id fuer simulationsbasierte Lernvorschlaege (Phase 7)')
ON CONFLICT (version) DO NOTHING;

COMMIT;
