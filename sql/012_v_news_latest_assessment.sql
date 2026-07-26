-- ============================================================================
-- 012_v_news_latest_assessment.sql
--
-- Paket 2 (Phase 2 der "Fachlichen Ueberarbeitung"): "genau eine gueltige
-- Bewertung je Nachricht". Workflow 08 dedupliziert bereits korrekt selbst
-- (DISTINCT ON + Prioritaet nach prompt_version), aber 06/07/10 joinen
-- trading.news_assessments bisher ohne jede Deduplizierung - hat eine News
-- sowohl eine Erst- als auch eine Recherchebewertung, sehen diese drei
-- Workflows beide Zeilen (docs/FACHLICHE_BESTANDSAUFNAHME.md, Abschnitt 5).
--
-- Diese Migration legt die zentrale View an, die 08s bereits produktive
-- Prioritaetslogik repliziert. Kein Consumer wird in diesem Schritt
-- umgestellt (folgt in einem eigenen Paket) - reine Vorbereitung.
-- ============================================================================

-- Vorprodukt: fehlte bisher komplett - keine Spalte markiert eine Bewertung
-- als manuell bestaetigt/abgelehnt. Inert bis eine kuenftige Freigabe-
-- Oberflaeche das nutzt (nach dem Muster von "Watchlist verwalten" /
-- "RSS-Quellen verwalten" / "12 - Lernvorschlag-Freigabe"), nicht Teil
-- dieses Pakets.
ALTER TABLE trading.news_assessments
    ADD COLUMN IF NOT EXISTS confirmation_status TEXT NOT NULL DEFAULT 'unconfirmed';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'news_assessments_confirmation_status_check'
          AND conrelid = 'trading.news_assessments'::regclass
    ) THEN
        ALTER TABLE trading.news_assessments
            ADD CONSTRAINT news_assessments_confirmation_status_check
            CHECK (confirmation_status IN ('unconfirmed', 'manually_confirmed', 'manually_rejected'));
    END IF;
END
$$;

COMMENT ON COLUMN trading.news_assessments.confirmation_status IS
    'Manuelle Freigabe-Ebene ueber der automatischen Erst-/Recherchebewertung. Aktuell schreibt kein '
    'Workflow hierauf (kein manueller Freigabe-Workflow existiert) - Feld ist vorbereitet, nicht aktiv genutzt.';

-- Repliziert exakt die bereits produktive Prioritaetslogik aus 08
-- (DISTINCT ON (ni.id) ... CASE WHEN prompt_version='news-recherche-agent-v1' THEN 1
--  WHEN prompt_version='news-ingestion-v1' THEN 2 ELSE 3 END, created_at DESC),
-- ergaenzt um eine hoehere Prioritaetsstufe fuer manuell bestaetigte Bewertungen.
--
-- Sicherheits-Voraussetzung (verifiziert, nicht angenommen): 03/03a schreiben
-- trading.news_assessments nur im Erfolgsfall (INSERT nur nach erfolgreicher
-- KI-Bewertung, Fehler setzen ausschliesslich news_items.status/research_status).
-- "Fehlgeschlagene/verworfene Bewertungen erscheinen nie als gueltig" ist also
-- bereits strukturell garantiert, kein Zusatzfilter dafuer noetig.
CREATE OR REPLACE VIEW trading.v_news_latest_assessment AS
SELECT DISTINCT ON (ni.id)
    ni.id                       AS news_id,
    na.id                       AS assessment_id,
    CASE
        WHEN na.prompt_version = 'news-recherche-agent-v1' THEN 'research'
        WHEN na.prompt_version = 'news-ingestion-v1' THEN 'first_pass'
        ELSE 'other'
    END                         AS assessment_source,
    na.prompt_version,
    na.created_at               AS assessed_at,
    na.betroffene_ticker_json   AS ticker_json,
    na.news_kategorie           AS category,
    na.wirkung_staerke          AS effect_level,
    na.wirkungsrichtung         AS direction,
    na.relevant                 AS relevance,
    na.konfidenz                AS confidence,
    na.relevance_confidence,
    na.probability_positive,
    na.probability_negative,
    na.probability_neutral,
    na.strength_confidence,
    na.data_quality_score,
    ni.research_status,
    na.ist_wiederholung         AS is_duplicate,
    ni.event_cluster_id,
    na.confirmation_status
FROM trading.news_items ni
JOIN trading.news_assessments na ON na.news_id = ni.id
WHERE na.confirmation_status IS DISTINCT FROM 'manually_rejected'
ORDER BY ni.id,
    CASE
        WHEN na.confirmation_status = 'manually_confirmed' THEN 0
        WHEN na.prompt_version = 'news-recherche-agent-v1' THEN 1
        WHEN na.prompt_version = 'news-ingestion-v1' THEN 2
        ELSE 3
    END,
    na.created_at DESC;

COMMENT ON VIEW trading.v_news_latest_assessment IS
    'Genau eine gueltige Bewertung je News (Phase 2 der fachlichen Ueberarbeitung). Prioritaet: '
    'manuell bestaetigt > aktuelle Recherchebewertung > aktuelle Erstbewertung, jeweils neueste zuerst. '
    'Repliziert die bereits in 08 produktive Logik. Noch kein Consumer umgestellt - folgt in Paket 3.';
