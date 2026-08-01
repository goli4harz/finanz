-- ============================================================================
-- 038_learning_proposal_activation_failed_status.sql
--
-- Haertungsauftrag Teil A (Fehleranalyse A6): "Ein Vorschlag darf nur dann als
-- activated markiert werden, wenn das tatsaechliche Ziel-Update exakt die
-- erwartete Anzahl von Zeilen geaendert hat." Bisher setzte der Freigabe-
-- Workflow (12) den Status unbedingt auf 'activated', unabhaengig davon, ob
-- das eigentliche Ziel-Update (pipeline_config/strategy_parameters/
-- strategy_regime_matrix/strategy_status/scoring_weights) ueberhaupt eine
-- Zeile getroffen hat.
--
-- Neuer Status 'activation_failed': das Ziel-Update hat 0 Zeilen betroffen
-- (falscher/veralteter target_type/target_value, ungueltiger proposed_value,
-- oder der Vorschlag wurde parallel bereits anders bearbeitet). Bleibt fuer
-- manuelle Nachpruefung sichtbar, wird NICHT automatisch erneut versucht.
--
-- Additiv, idempotent (DROP+ADD nur falls die Bedingung noch nicht die neue
-- Werteliste enthaelt), aendert keine bestehenden Zeilen.
-- ============================================================================

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_learning_rule_proposals_status'
          AND pg_get_constraintdef(oid) LIKE '%activation_failed%'
    ) THEN
        ALTER TABLE trading.learning_rule_proposals
            DROP CONSTRAINT IF EXISTS chk_learning_rule_proposals_status;
        ALTER TABLE trading.learning_rule_proposals
            ADD CONSTRAINT chk_learning_rule_proposals_status
            CHECK (status IN ('proposed','approved','rejected','activated','activation_failed','expired'));
    END IF;
END $$;

COMMENT ON COLUMN trading.learning_rule_proposals.status IS
    'proposed=neu vom Lernagenten, approved/rejected=Zwischenstatus (aktuell ungenutzt, Freigabe geht direkt proposed->activated), activated=Ziel-Update hat mind. 1 Zeile getroffen, activation_failed=Freigabe versucht aber Ziel-Update traf 0 Zeilen (siehe Fehleranalyse A6), expired=nicht mehr gueltig.';
