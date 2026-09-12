-- ============================================================================
-- 089 - trading.simulation_decision_log.decision: idempotente/defensive
-- Haertung der CHECK-Constraint-Erweiterung aus Migration 088 (LIVE_PARITY
-- Schritt 4L.2C-R, 2026-09-12).
-- ============================================================================
-- Hintergrund: 088 hat den Constraint per einfachem DROP+ADD ohne
-- Zustandspruefung erweitert (ACCEPTED/REJECTED/BLOCKED/NO_FILL ->
-- + SHADOW_LOGGED) - das war zum Zeitpunkt korrekt und ist bereits produktiv
-- angewendet (verifiziert: neuer Constraint live bestaetigt, ein echter
-- AVAILABLE_DATA_LIVE_REPLAY-Mini-Run hat bereits decision='SHADOW_LOGGED'-
-- Zeilen erfolgreich geschrieben). 088 wird NICHT nachtraeglich veraendert -
-- sie bleibt im Repo exakt der historisch tatsaechlich ausgefuehrte Stand.
--
-- Diese Migration ist eine reine Haertung fuer alle KUENFTIGEN Anwendungen
-- (z.B. ein Restore auf einer anderen Umgebung, ein Rebuild von Grund auf,
-- oder ein versehentlicher zweiter Lauf): sie erkennt den tatsaechlichen
-- IST-Zustand des Constraints ueber seine kanonische Definition
-- (pg_get_constraintdef - PostgreSQL normalisiert CHECK-IN-Listen immer zur
-- selben "= ANY (ARRAY[...])"-Form, unabhaengig davon, wie die urspruengliche
-- DDL formuliert war, siehe Phase 5 der Auftragsspezifikation) und handelt
-- NUR die beiden bekannten, produktiv beobachteten Zustaende:
--
--   CASE A (Zielzustand bereits korrekt, z.B. nach 088 oder nach dieser
--           Migration selbst): NO-OP.
--   CASE B (bekannter Altzustand vor 088, z.B. auf einer Umgebung, auf der
--           088 noch nicht gelaufen ist): Constraint atomar auf den
--           Zielzustand erweitern - inhaltlich identisch zu 088, hier nur
--           mit Zustandspruefung davor statt blind.
--
-- Jeder andere Zustand (Constraint fehlt komplett, oder enthaelt zusaetzliche/
-- andere Werte als die beiden bekannten Faelle) fuehrt zu einem RAISE
-- EXCEPTION (fail closed) - diese Migration ueberschreibt niemals eine fremde,
-- unbekannte Schemaevolution des Constraints. Keine Zeile/Spalte wird von
-- dieser Migration jemals veraendert, nur die Constraint-Definition selbst.
-- ============================================================================

BEGIN;

DO $$
DECLARE
  current_def text;
  target_def_expected text := 'CHECK ((decision = ANY (ARRAY[''ACCEPTED''::text, ''REJECTED''::text, ''BLOCKED''::text, ''NO_FILL''::text, ''SHADOW_LOGGED''::text])))';
  legacy_def_expected text := 'CHECK ((decision = ANY (ARRAY[''ACCEPTED''::text, ''REJECTED''::text, ''BLOCKED''::text, ''NO_FILL''::text])))';
BEGIN
  SELECT pg_get_constraintdef(oid) INTO current_def
  FROM pg_constraint
  WHERE conrelid = 'trading.simulation_decision_log'::regclass
    AND conname = 'simulation_decision_log_decision_check'
    AND contype = 'c';

  IF current_def IS NULL THEN
    RAISE EXCEPTION 'GAP_SHADOW_LOGGED_DB_CONSTRAINT: constraint simulation_decision_log_decision_check nicht gefunden auf trading.simulation_decision_log - fail closed, keine Aenderung vorgenommen. Erwartet entweder den Ziel- oder den bekannten Altzustand.';
  ELSIF current_def = target_def_expected THEN
    RAISE NOTICE 'GAP_SHADOW_LOGGED_DB_CONSTRAINT: Constraint bereits im Zielzustand (SHADOW_LOGGED erlaubt) - NO-OP.';
  ELSIF current_def = legacy_def_expected THEN
    RAISE NOTICE 'GAP_SHADOW_LOGGED_DB_CONSTRAINT: bekannter Altzustand (vor 088) gefunden - erweitere Constraint additiv um SHADOW_LOGGED.';
    ALTER TABLE trading.simulation_decision_log DROP CONSTRAINT simulation_decision_log_decision_check;
    ALTER TABLE trading.simulation_decision_log ADD CONSTRAINT simulation_decision_log_decision_check
      CHECK (decision IN ('ACCEPTED','REJECTED','BLOCKED','NO_FILL','SHADOW_LOGGED'));
  ELSE
    RAISE EXCEPTION 'GAP_SHADOW_LOGGED_DB_CONSTRAINT: unbekannter/fremder Constraint-Zustand gefunden, fail closed (keine Aenderung): %', current_def;
  END IF;
END $$;

INSERT INTO trading.schema_migrations (version, description)
VALUES ('089', 'trading.simulation_decision_log.decision: idempotente/defensive Haertung der 088-Constraint-Erweiterung (SHADOW_LOGGED) - erkennt Ziel-/Altzustand ueber pg_get_constraintdef, fail-closed bei unbekanntem Zustand, keine Datenaenderung')
ON CONFLICT (version) DO NOTHING;

COMMIT;
