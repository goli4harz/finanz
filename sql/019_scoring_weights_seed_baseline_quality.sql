-- ============================================================================
-- Nachtrag zur fachlichen Ueberarbeitung: trading.scoring_weights aktivieren
-- ============================================================================
-- OFFENE_AUFGABEN.md (Prioritaet 3) hielt fest, dass scoring_weights von der
-- eigentlichen Gewichtungslogik noch nicht gelesen wird - konkret die in
-- "09 - Lernagent Newswirkung" (Nodes "SQL: Je Newskategorie", "SQL: Je Quelle",
-- "SQL: Je Ticker", "SQL: Je Konfidenz-Bucket") hartkodierte Formel
-- (confounded=0.25, baseline_quality high=1.0/medium=0.7/limited=0.4), mit der
-- die gewichtete Trefferquote (weighted_direction_accuracy) fuer den woechentlichen
-- Lernbericht berechnet wird.
--
-- Seedet die 4 Gewichte als aktive Zeilen mit exakt den bisherigen hartkodierten
-- Werten - reine Bestandsuebernahme, KEINE Verhaltensaenderung bei Einspielung
-- dieser Migration. Erst eine spaetere manuelle Aenderung (z.B. ueber
-- "12 - Lernvorschlag-Freigabe" oder eine direkte Aktivierung eines neuen
-- scoring_weights-Eintrags) wirkt sich tatsaechlich auf den naechsten Lauf von
-- "09" aus.

INSERT INTO trading.scoring_weights (weight_key, weight_value, version, active, metadata_json)
VALUES
    ('baseline_quality_high',    1.00, 1, TRUE, '{"source": "hardcoded-default", "used_by": "09 - Lernagent Newswirkung"}'::JSONB),
    ('baseline_quality_medium',  0.70, 1, TRUE, '{"source": "hardcoded-default", "used_by": "09 - Lernagent Newswirkung"}'::JSONB),
    ('baseline_quality_limited', 0.40, 1, TRUE, '{"source": "hardcoded-default", "used_by": "09 - Lernagent Newswirkung"}'::JSONB),
    ('confounded_case',          0.25, 1, TRUE, '{"source": "hardcoded-default", "used_by": "09 - Lernagent Newswirkung"}'::JSONB)
ON CONFLICT (weight_key, version) DO NOTHING;
