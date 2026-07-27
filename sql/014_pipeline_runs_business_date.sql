-- ============================================================================
-- Paket 4 (Phase 10a der fachlichen Ueberarbeitung): Idempotenz-Grundlage
-- ============================================================================
-- business_date wird in "00 - Tagesabschluss-Orchestrator"s Node "Run-ID erzeugen"
-- (und lokal in 04's "Log Cleanup-Lauf (SQL bauen)") bereits zur Laufzeit berechnet,
-- aber bisher nirgends in pipeline_runs persistiert. Diese Migration ergaenzt nur
-- die Spalte + Backfill + einen Index, keine Verhaltensaenderung an den Workflows
-- selbst (die Node-Anpassungen, um die Spalte tatsaechlich zu befuellen, sind ein
-- separater Schritt NACH dieser Migration, damit die Spalte beim naechsten
-- automatischen Lauf bereits existiert).
--
-- BEWUSST KEIN UNIQUE-Constraint auf (business_date, workflow_name, stage_name):
-- dieses Repo hat eine etablierte Testkultur mit wiederholten manuellen Re-Runs am
-- selben Tag (siehe Verifikation von Paket 1-3, README "Reusable n8n testing
-- techniques"). Ein harter Constraint wuerde jeden Test-Rerun als Duplikat-Fehler
-- zaehlen und echte Duplikat-Signale mit Test-Rauschen vermischen. Ob/wie ein
-- echter Schutz (harter Constraint + expliziter Ausnahme-Modus fuers Testen, oder
-- ein Guard-Node VOR den eigentlichen Schreibvorgaengen von 02/02b/05/06/10) gebaut
-- wird, ist eine eigene, separat abzunehmende Entscheidung - nicht Teil dieses Pakets.

ALTER TABLE trading.pipeline_runs ADD COLUMN IF NOT EXISTS business_date DATE;

-- Best-effort-Backfill fuer Bestandszeilen aus dem run_id-String (Format
-- 'daily-YYYY-MM-DD-...' bzw. 'cleanup-YYYY-MM-DD-...'). Zeilen mit anderem Format
-- (z.B. 'standalone-<timestamp>') bleiben bewusst NULL, nicht parsbar.
UPDATE trading.pipeline_runs
SET business_date = substring(run_id FROM '^[a-z]+-([0-9]{4}-[0-9]{2}-[0-9]{2})-')::date
WHERE business_date IS NULL
  AND run_id ~ '^[a-z]+-[0-9]{4}-[0-9]{2}-[0-9]{2}-';

CREATE INDEX IF NOT EXISTS ix_pipeline_runs_business_date_stage
    ON trading.pipeline_runs (business_date, workflow_name, stage_name);

COMMENT ON COLUMN trading.pipeline_runs.business_date IS
    'Geschaeftstag (Europe/Berlin), aus 00s "Run-ID erzeugen"/04s lokaler getBusinessDate() '
    'uebernommen. Nur ein Index, absichtlich kein UNIQUE-Constraint - siehe Kommentar oben.';
