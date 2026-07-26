-- ============================================================================
-- 013_v_news_latest_assessment_erweiterung.sql
--
-- Paket 3 (Vorbereitung): erweitert trading.v_news_latest_assessment um Felder,
-- die 06/07/10 tatsaechlich brauchen (wirkungsebene, ticker_begruendung,
-- wirkungs_begruendung, sentiment), aber in 012 noch fehlten - erst beim
-- Lesen der drei Consumer-Queries aufgefallen. CREATE OR REPLACE VIEW ist
-- sicher erneut ausfuehrbar (bestehende Spalten bleiben unveraendert,
-- reine Ergaenzung), kein Consumer nutzt die View bisher (folgt in diesem
-- selben Paket).
-- ============================================================================

-- WICHTIG: CREATE OR REPLACE VIEW erlaubt nur ANHAENGEN neuer Spalten am Ende der
-- SELECT-Liste, kein Umsortieren/Umbenennen bestehender Positionen (live am
-- Test-Schema gefunden: "cannot change name of view column ... to ..."). Die vier
-- neuen Felder (wirkungsebene/ticker_begruendung/wirkungs_begruendung/sentiment)
-- muessen deshalb hinter das letzte Feld aus 012, nicht in die urspruengliche
-- fachliche Reihenfolge einsortiert werden.
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
    na.confirmation_status,
    na.wirkungsebene,
    na.ticker_begruendung,
    na.wirkungs_begruendung,
    na.sentiment
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
