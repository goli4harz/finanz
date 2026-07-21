-- ============================================================================
-- 006_learning_proposals_time_horizon.sql
--
-- Prioritaet 9 ("Lernagent methodisch verbessern", Punkt 25): Vorschlaege des
-- Lernagenten (09) muessen den Zeithorizont (D+1/D+3/D+5/D+10/D+20) tragen,
-- auf dem das zugrundeliegende Finding basiert -- seit der Umstellung auf
-- Kennzahlen je (Dimension x Zeitraum)-Kombination ist ein Finding sonst
-- nicht mehr eindeutig einem Beleg zuordenbar.
--
-- "evidence" (ebenfalls von Punkt 25 gefordert) bekommt bewusst KEINE eigene
-- Spalte -- die bereits vorhandene generische metadata_json-Spalte deckt das
-- ab, ohne Schema-Overhead fuer einen reinen Nachweis-Blob.
--
-- Wiederholbar/idempotent: ADD COLUMN IF NOT EXISTS. Aendert keine
-- bestehenden Zeilen/Werte.
-- ============================================================================

ALTER TABLE trading.learning_rule_proposals
    ADD COLUMN IF NOT EXISTS time_horizon TEXT;

COMMENT ON COLUMN trading.learning_rule_proposals.time_horizon IS
    'Zeithorizont (z.B. D+1/D+3/D+5/D+10/D+20), auf dem das zugrundeliegende Finding basiert. NULL bei Vorschlaegen aus der Zeit vor Prioritaet 9 (horizontuebergreifend berechnet).';
