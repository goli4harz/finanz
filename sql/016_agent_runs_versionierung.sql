-- ============================================================================
-- Paket 6 (Phase 12 der fachlichen Ueberarbeitung): Regel-/Konfigurationsversionierung
-- ============================================================================
-- trading.agent_runs bekommt rule_version/configuration_version. Tabellenwahl
-- bewusst agent_runs statt einer neuen Tabelle: agent_runs ist bereits die
-- "ein Modellaufruf = eine Zeile"-Protokolltabelle mit model_name/prompt_version,
-- eine neue Tabelle waere nur gerechtfertigt, wenn eine n:m-Beziehung noetig waere.
--
-- Beide Felder als JSONB-Snapshot statt Skalar, da scoring_weights mehrere
-- unabhaengig versionierte weight_key-Zeilen gleichzeitig aktiv haben kann (kein
-- einzelner Skalarwert reicht) - konsistent mit dem bereits vorhandenen
-- metadata_json-Muster in derselben Tabelle.
--
-- Schema-only: kein Consumer (03/03a/09/10) befuellt diese Felder in diesem Paket.
-- 09 referenziert scoring_weights aktuell ueberhaupt nicht - ein Wiring waere eine
-- echte Erweiterung der Lernagent-Logik und gehoert in ein eigenes, separat
-- abzunehmendes Paket, nicht hier schon mitgeliefert.

ALTER TABLE trading.agent_runs
    ADD COLUMN IF NOT EXISTS rule_version JSONB,
    ADD COLUMN IF NOT EXISTS configuration_version JSONB;

COMMENT ON COLUMN trading.agent_runs.rule_version IS
    'Snapshot der zum Aufrufzeitpunkt aktiven trading.scoring_weights, Form '
    '{weight_key: version}. Schema-only, kein Consumer befuellt dieses Feld aktuell.';
COMMENT ON COLUMN trading.agent_runs.configuration_version IS
    'Snapshot der zum Aufrufzeitpunkt gelesenen trading.pipeline_config-Werte '
    '(z.B. DRY_RUN, Schwellenwerte). Schema-only, kein Consumer befuellt dieses Feld aktuell.';
