-- ============================================================================
-- 011_news_konfidenz_trennung.sql
--
-- Paket 1 (Phase 4 der "Fachlichen Ueberarbeitung", Schema-Teil): trennt
-- Relevanz-Konfidenz, Richtungs-Wahrscheinlichkeit, Staerke-Konfidenz und
-- Datenqualitaet, die bisher teilweise in einem einzigen Score (konfidenz)
-- vermischt waren. Legt nur die Spalten an - Prompt-/Validierungs-Aenderungen
-- in 03/03a folgen in einem eigenen Paket.
--
-- Bewusste Entscheidung (Nutzerfrage/-bestaetigung 2026-07-26): KEINE neuen
-- predicted_direction/predicted_strength/model_name-Spalten, obwohl im
-- Originalauftrag so benannt - trading.news_assessments hat mit
-- wirkungsrichtung/wirkung_staerke/modell_version bereits exakt diese
-- Konzepte. Neue, gleichbedeutende Spalten wuerden dem Ziel aus Phase 2
-- (genau eine Wahrheit je Sache) widersprechen. Die bestehenden Spalten
-- uebernehmen diese Rolle und gelten ab sofort als die dort geforderten
-- "Legacy"-Felder (weiterhin lesbar, nicht ersetzt).
-- ============================================================================

ALTER TABLE trading.news_assessments
    ADD COLUMN IF NOT EXISTS relevance_confidence NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS probability_positive NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS probability_negative NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS probability_neutral NUMERIC(5,4),
    ADD COLUMN IF NOT EXISTS strength_confidence NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS data_quality_score NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS prediction_horizon_days INTEGER,
    ADD COLUMN IF NOT EXISTS prediction_created_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_probability_range_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_probability_range_check
            CHECK (
                (probability_positive IS NULL OR probability_positive BETWEEN 0 AND 1)
                AND (probability_negative IS NULL OR probability_negative BETWEEN 0 AND 1)
                AND (probability_neutral IS NULL OR probability_neutral BETWEEN 0 AND 1)
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_probability_sum_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_probability_sum_check
            CHECK (
                probability_positive IS NULL
                OR probability_negative IS NULL
                OR probability_neutral IS NULL
                OR (probability_positive + probability_negative + probability_neutral) BETWEEN 0.99 AND 1.01
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_relevance_confidence_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_relevance_confidence_check
            CHECK (relevance_confidence IS NULL OR relevance_confidence BETWEEN 0 AND 100);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_strength_confidence_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_strength_confidence_check
            CHECK (strength_confidence IS NULL OR strength_confidence BETWEEN 0 AND 100);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_data_quality_score_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_data_quality_score_check
            CHECK (data_quality_score IS NULL OR data_quality_score BETWEEN 0 AND 100);
    END IF;
END
$$;

COMMENT ON COLUMN trading.news_assessments.probability_positive IS
    'Wahrscheinlichkeitsverteilung der Kursrichtung (positiv/negativ/neutral muessen zusammen ~1 ergeben, '
    'per CHECK erzwungen). Ungueltige Verteilungen werden von 03/03a bereits vor dem INSERT abgelehnt/retried, '
    'dieser Constraint ist die letzte Verteidigungslinie, nicht die einzige.';
COMMENT ON COLUMN trading.news_assessments.data_quality_score IS
    'Neu, unabhaengig von Relevanz/Richtung/Staerke - bewertet die Qualitaet der Eingangsdaten selbst '
    '(z.B. Vollstaendigkeit des Artikeltexts, Eindeutigkeit der Ticker-Zuordnung).';
COMMENT ON COLUMN trading.news_assessments.wirkungsrichtung IS
    'Legacy-Feld (Bestandsspalte) - uebernimmt fachlich die Rolle von "predicted_direction" aus der '
    'Ueberarbeitung 2026-07; bewusst nicht durch eine gleichbedeutende neue Spalte ersetzt (siehe Kommentar im Migrationskopf).';
COMMENT ON COLUMN trading.news_assessments.wirkung_staerke IS
    'Legacy-Feld (Bestandsspalte) - uebernimmt fachlich die Rolle von "predicted_strength" aus der Ueberarbeitung 2026-07.';
COMMENT ON COLUMN trading.news_assessments.modell_version IS
    'Legacy-Feld (Bestandsspalte) - uebernimmt fachlich die Rolle von "model_name" aus der Ueberarbeitung 2026-07.';
