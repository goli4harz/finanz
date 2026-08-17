-- ============================================================================
-- 065: Kombinierte Sicht Live- + historische Newswirkungs-Verfolgung
-- ============================================================================
-- Damit Workflow 09 (Lernagent) beide Quellen gemeinsam auswerten kann, ohne
-- seine SQL-Auswertungsknoten doppelt zu pflegen. data_source unterscheidet
-- die Herkunft (fuer eine spaetere getrennte Betrachtung, falls gewuenscht).
-- effective_created_at nutzt bei historischen Zeilen news_date statt
-- created_at (Zeitpunkt der Berechnung, i.d.R. "heute") - sonst wuerde jede
-- historische Zeile ueber Workflow 09s "created_at >= now() - interval
-- '90 days'"-Filter faelschlich als "aktuell" durchgehen, unabhaengig davon
-- wie alt das eigentliche Nachrichtenereignis war.

BEGIN;

CREATE OR REPLACE VIEW trading.v_news_impact_tracking_combined AS
SELECT
    'live'::text AS data_source,
    created_at AS effective_created_at,
    id, news_id, news_key, ticker, news_date, news_time, publication_timestamp,
    first_trading_date, predicted_direction, predicted_strength, prediction_confidence,
    news_category, impact_level, source, baseline_price, baseline_timestamp,
    benchmark_symbol, benchmark_baseline_price,
    price_d1, price_d3, price_d5, price_d10, price_d20,
    return_d1, return_d3, return_d5, return_d10, return_d20,
    benchmark_return_d1, benchmark_return_d3, benchmark_return_d5, benchmark_return_d10, benchmark_return_d20,
    abnormal_return_d1, abnormal_return_d3, abnormal_return_d5, abnormal_return_d10, abnormal_return_d20,
    max_positive_move, max_negative_move, observed_direction, observed_strength,
    direction_correct, strength_correct, quality_score, confounded, confounding_reason,
    additional_news_count, status, created_at, updated_at, completed_at, baseline_quality,
    direction_correct_d1, direction_correct_d3, direction_correct_d5, direction_correct_d10, direction_correct_d20,
    has_major_followup_news
FROM trading.news_impact_tracking

UNION ALL

SELECT
    'historical'::text AS data_source,
    news_date::timestamptz AS effective_created_at,
    id, news_id, news_key, ticker, news_date, news_time, publication_timestamp,
    first_trading_date, predicted_direction, predicted_strength, prediction_confidence,
    news_category, impact_level, source, baseline_price, baseline_timestamp,
    benchmark_symbol, benchmark_baseline_price,
    price_d1, price_d3, price_d5, price_d10, price_d20,
    return_d1, return_d3, return_d5, return_d10, return_d20,
    benchmark_return_d1, benchmark_return_d3, benchmark_return_d5, benchmark_return_d10, benchmark_return_d20,
    abnormal_return_d1, abnormal_return_d3, abnormal_return_d5, abnormal_return_d10, abnormal_return_d20,
    max_positive_move, max_negative_move, observed_direction, observed_strength,
    direction_correct, strength_correct, quality_score, confounded, confounding_reason,
    additional_news_count, status, created_at, updated_at, completed_at, baseline_quality,
    direction_correct_d1, direction_correct_d3, direction_correct_d5, direction_correct_d10, direction_correct_d20,
    has_major_followup_news
FROM trading.historical_news_impact_tracking;

COMMENT ON VIEW trading.v_news_impact_tracking_combined IS
  'Kombiniert news_impact_tracking (Live) und historical_news_impact_tracking fuer den Lernagenten (Workflow 09). effective_created_at ersetzt created_at als Zeitfilter-Basis, damit historische Zeilen nicht ueber ihr Berechnungsdatum, sondern ihr echtes Nachrichtendatum eingeordnet werden.';

INSERT INTO trading.schema_migrations (version, description)
VALUES ('065', 'View v_news_impact_tracking_combined - vereint Live- und historische Newswirkungs-Verfolgung fuer Workflow 09')
ON CONFLICT (version) DO NOTHING;

COMMIT;
