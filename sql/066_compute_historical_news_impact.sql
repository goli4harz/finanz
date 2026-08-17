-- ============================================================================
-- 066: Einmalige Stapelverarbeitung - historische Newswirkung berechnen
-- ============================================================================
-- Kein Schema-Objekt (keine schema_migrations-Zeile) - dieses Skript FUELLT
-- trading.historical_news_impact_tracking (sql/064) aus den bereits
-- vorliegenden trading.historical_news_assessments + trading.historical_
-- price_data (inkl. ^GDAXI, siehe Import-Job imp-2026-08-17-51d8ab).
--
-- Bewusst als reine SQL-Stapelverarbeitung statt eines neuen n8n-Workflows:
-- bei historischen Daten liegt der komplette Kursverlauf danach bereits vor,
-- ein einziger Durchlauf reicht (keine Inkrementallogik wie bei Workflow 08
-- noetig, das dort ja auf zukuenftige Handelstage warten muss). Idempotent
-- durch ON CONFLICT (news_id, ticker) DO UPDATE - kann nach jedem weiteren
-- historischen Import erneut ausgefuehrt werden.
--
-- Methodik identisch zu Workflow 08 ("News-Wirkungsanalyse"): Baseline-
-- Bestimmung ueber Handelssitzungs-Zeitfenster (vor/waehrend/nach), D+1/3/
-- 5/10/20 Kursvergleich, benchmark-bereinigte "Abnormal Return"-Berechnung
-- gegen ^GDAXI ueber exaktes Kalenderdatum (nicht Array-Position - D11-Fix
-- aus Workflow 08 uebernommen), Richtungstreffer je Horizont.
--
-- BEKANNTE VEREINFACHUNG gegenueber Workflow 08 (bewusst, siehe Session-
-- Notiz): die "aussergewoehnliche taegliche Benchmark-Bewegung"-Stoerfaktor-
-- Erkennung ist hier NICHT nachgebaut, nur die "weitere kursrelevante News
-- im Fenster"-Erkennung. Kann bei Bedarf spaeter ergaenzt werden.
--
-- Sitzungszeiten: fest 09:00-17:30 Europe/Berlin (identisch zum Workflow-
-- 08-Fallback-Default) - alle betroffenen Watchlist-Ticker sind XETRA.

BEGIN;

WITH relevant AS (
  SELECT hn.id AS news_id, hn.news_key, hn.published_at, hn.source AS quelle_domain,
         hna.wirkungsrichtung, hna.wirkung_staerke, hna.konfidenz, hna.news_kategorie,
         hna.betroffene_ticker_json
  FROM trading.historical_news hn
  JOIN trading.historical_news_assessments hna ON hna.news_id = hn.id
  WHERE hna.relevant = true
),
expanded AS (
  SELECT r.news_id, r.news_key, r.published_at, r.quelle_domain,
         r.wirkungsrichtung AS predicted_direction, r.wirkung_staerke AS predicted_strength,
         r.konfidenz AS prediction_confidence, r.news_kategorie AS news_category,
         trim(both '"' from t::text) AS ticker
  FROM relevant r, jsonb_array_elements(r.betroffene_ticker_json) t
),
sess AS (
  SELECT e.*,
    (e.published_at AT TIME ZONE 'Europe/Berlin')::date AS news_date,
    (e.published_at AT TIME ZONE 'Europe/Berlin')::time AS local_time
  FROM expanded e
),
cased AS (
  SELECT s.*,
    CASE WHEN local_time < TIME '09:00' THEN 'vor_handelsbeginn'
         WHEN local_time < TIME '17:30' THEN 'waehrend_handelszeit'
         ELSE 'nach_handelsende' END AS baseline_case,
    CASE WHEN local_time < TIME '09:00' THEN 'high'
         WHEN local_time < TIME '17:30' THEN 'limited'
         ELSE 'high' END AS baseline_quality
  FROM sess s
),
ranked AS (
  SELECT ticker, trading_date, close,
         ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY trading_date) AS rn
  FROM trading.historical_price_data
),
baselined AS (
  SELECT c.*, br.trading_date AS baseline_date, br.close AS baseline_price, br.rn AS baseline_rn
  FROM cased c
  LEFT JOIN LATERAL (
    SELECT trading_date, close, rn FROM ranked r
    WHERE r.ticker = c.ticker
      AND ( (c.baseline_case = 'nach_handelsende' AND r.trading_date <= c.news_date)
         OR (c.baseline_case != 'nach_handelsende' AND r.trading_date < c.news_date) )
    ORDER BY r.trading_date DESC LIMIT 1
  ) br ON true
),
horizons AS (
  SELECT b.*,
    p1.trading_date AS date_d1, p1.close AS price_d1,
    p3.trading_date AS date_d3, p3.close AS price_d3,
    p5.trading_date AS date_d5, p5.close AS price_d5,
    p10.trading_date AS date_d10, p10.close AS price_d10,
    p20.trading_date AS date_d20, p20.close AS price_d20
  FROM baselined b
  LEFT JOIN ranked p1 ON p1.ticker=b.ticker AND p1.rn = b.baseline_rn+1
  LEFT JOIN ranked p3 ON p3.ticker=b.ticker AND p3.rn = b.baseline_rn+3
  LEFT JOIN ranked p5 ON p5.ticker=b.ticker AND p5.rn = b.baseline_rn+5
  LEFT JOIN ranked p10 ON p10.ticker=b.ticker AND p10.rn = b.baseline_rn+10
  LEFT JOIN ranked p20 ON p20.ticker=b.ticker AND p20.rn = b.baseline_rn+20
),
bmk AS (
  SELECT trading_date, close FROM trading.historical_price_data WHERE ticker='^GDAXI'
),
withbmk AS (
  SELECT h.*,
    bbase.close AS benchmark_baseline_price,
    b1.close AS bench_price_d1, b3.close AS bench_price_d3, b5.close AS bench_price_d5,
    b10.close AS bench_price_d10, b20.close AS bench_price_d20
  FROM horizons h
  LEFT JOIN bmk bbase ON bbase.trading_date = h.baseline_date
  LEFT JOIN bmk b1 ON b1.trading_date = h.date_d1
  LEFT JOIN bmk b3 ON b3.trading_date = h.date_d3
  LEFT JOIN bmk b5 ON b5.trading_date = h.date_d5
  LEFT JOIN bmk b10 ON b10.trading_date = h.date_d10
  LEFT JOIN bmk b20 ON b20.trading_date = h.date_d20
),
returns AS (
  SELECT w.*,
    CASE WHEN price_d1 IS NOT NULL AND baseline_price IS NOT NULL THEN round(((price_d1/baseline_price)-1)::numeric,6) END AS return_d1,
    CASE WHEN price_d3 IS NOT NULL AND baseline_price IS NOT NULL THEN round(((price_d3/baseline_price)-1)::numeric,6) END AS return_d3,
    CASE WHEN price_d5 IS NOT NULL AND baseline_price IS NOT NULL THEN round(((price_d5/baseline_price)-1)::numeric,6) END AS return_d5,
    CASE WHEN price_d10 IS NOT NULL AND baseline_price IS NOT NULL THEN round(((price_d10/baseline_price)-1)::numeric,6) END AS return_d10,
    CASE WHEN price_d20 IS NOT NULL AND baseline_price IS NOT NULL THEN round(((price_d20/baseline_price)-1)::numeric,6) END AS return_d20,
    CASE WHEN bench_price_d1 IS NOT NULL AND benchmark_baseline_price IS NOT NULL THEN round(((bench_price_d1/benchmark_baseline_price)-1)::numeric,6) END AS benchmark_return_d1,
    CASE WHEN bench_price_d3 IS NOT NULL AND benchmark_baseline_price IS NOT NULL THEN round(((bench_price_d3/benchmark_baseline_price)-1)::numeric,6) END AS benchmark_return_d3,
    CASE WHEN bench_price_d5 IS NOT NULL AND benchmark_baseline_price IS NOT NULL THEN round(((bench_price_d5/benchmark_baseline_price)-1)::numeric,6) END AS benchmark_return_d5,
    CASE WHEN bench_price_d10 IS NOT NULL AND benchmark_baseline_price IS NOT NULL THEN round(((bench_price_d10/benchmark_baseline_price)-1)::numeric,6) END AS benchmark_return_d10,
    CASE WHEN bench_price_d20 IS NOT NULL AND benchmark_baseline_price IS NOT NULL THEN round(((bench_price_d20/benchmark_baseline_price)-1)::numeric,6) END AS benchmark_return_d20
  FROM withbmk w
),
abnormal AS (
  SELECT r.*,
    CASE WHEN return_d1 IS NOT NULL AND benchmark_return_d1 IS NOT NULL THEN round((return_d1-benchmark_return_d1)::numeric,6) END AS abnormal_return_d1,
    CASE WHEN return_d3 IS NOT NULL AND benchmark_return_d3 IS NOT NULL THEN round((return_d3-benchmark_return_d3)::numeric,6) END AS abnormal_return_d3,
    CASE WHEN return_d5 IS NOT NULL AND benchmark_return_d5 IS NOT NULL THEN round((return_d5-benchmark_return_d5)::numeric,6) END AS abnormal_return_d5,
    CASE WHEN return_d10 IS NOT NULL AND benchmark_return_d10 IS NOT NULL THEN round((return_d10-benchmark_return_d10)::numeric,6) END AS abnormal_return_d10,
    CASE WHEN return_d20 IS NOT NULL AND benchmark_return_d20 IS NOT NULL THEN round((return_d20-benchmark_return_d20)::numeric,6) END AS abnormal_return_d20
  FROM returns r
),
directions AS (
  SELECT a.*,
    CASE WHEN abnormal_return_d1 IS NULL THEN NULL WHEN abnormal_return_d1 > 0.005 THEN 'positiv' WHEN abnormal_return_d1 < -0.005 THEN 'negativ' ELSE 'neutral' END AS observed_direction_d1,
    CASE WHEN abnormal_return_d20 IS NULL THEN NULL WHEN abnormal_return_d20 > 0.005 THEN 'positiv' WHEN abnormal_return_d20 < -0.005 THEN 'negativ' ELSE 'neutral' END AS observed_direction_d20
  FROM abnormal a
),
confounding AS (
  SELECT d.*,
    (SELECT count(*) FROM expanded e2
      WHERE e2.ticker = d.ticker AND e2.news_id != d.news_id
        AND e2.published_at > d.published_at AND e2.published_at <= d.published_at + interval '28 days'
        AND e2.news_category IN ('quarterly_results','profit_warning','merger_acquisition','regulation')
    ) AS major_followup_count
  FROM directions d
)
INSERT INTO trading.historical_news_impact_tracking (
  news_id, news_key, ticker, news_date, publication_timestamp,
  predicted_direction, predicted_strength, prediction_confidence, news_category, source,
  baseline_price, baseline_timestamp, benchmark_symbol, benchmark_baseline_price,
  price_d1, price_d3, price_d5, price_d10, price_d20,
  return_d1, return_d3, return_d5, return_d10, return_d20,
  benchmark_return_d1, benchmark_return_d3, benchmark_return_d5, benchmark_return_d10, benchmark_return_d20,
  abnormal_return_d1, abnormal_return_d3, abnormal_return_d5, abnormal_return_d10, abnormal_return_d20,
  max_positive_move, max_negative_move,
  observed_direction, direction_correct,
  confounded, confounding_reason, additional_news_count, has_major_followup_news,
  status, baseline_quality,
  direction_correct_d1, direction_correct_d3, direction_correct_d5, direction_correct_d10, direction_correct_d20,
  completed_at
)
SELECT
  news_id, news_key, ticker, news_date, published_at,
  predicted_direction, predicted_strength, prediction_confidence, news_category, quelle_domain,
  baseline_price, baseline_date::timestamptz, '^GDAXI', benchmark_baseline_price,
  price_d1, price_d3, price_d5, price_d10, price_d20,
  return_d1, return_d3, return_d5, return_d10, return_d20,
  benchmark_return_d1, benchmark_return_d3, benchmark_return_d5, benchmark_return_d10, benchmark_return_d20,
  abnormal_return_d1, abnormal_return_d3, abnormal_return_d5, abnormal_return_d10, abnormal_return_d20,
  GREATEST(return_d1, return_d3, return_d5, return_d10, return_d20),
  LEAST(return_d1, return_d3, return_d5, return_d10, return_d20),
  observed_direction_d20, (predicted_direction = observed_direction_d20),
  (major_followup_count > 0),
  CASE WHEN major_followup_count > 0 THEN 'Weitere kursrelevante News im Beobachtungsfenster (' || major_followup_count || ')' END,
  major_followup_count::integer, (major_followup_count > 0),
  CASE WHEN price_d20 IS NOT NULL THEN 'completed' WHEN baseline_price IS NULL THEN 'failed' ELSE 'waiting_d20' END,
  baseline_quality,
  CASE WHEN abnormal_return_d1 IS NULL THEN NULL WHEN predicted_direction = observed_direction_d1 THEN TRUE ELSE FALSE END,
  CASE WHEN abnormal_return_d3 IS NULL THEN NULL ELSE (predicted_direction = (CASE WHEN abnormal_return_d3>0.005 THEN 'positiv' WHEN abnormal_return_d3<-0.005 THEN 'negativ' ELSE 'neutral' END)) END,
  CASE WHEN abnormal_return_d5 IS NULL THEN NULL ELSE (predicted_direction = (CASE WHEN abnormal_return_d5>0.005 THEN 'positiv' WHEN abnormal_return_d5<-0.005 THEN 'negativ' ELSE 'neutral' END)) END,
  CASE WHEN abnormal_return_d10 IS NULL THEN NULL ELSE (predicted_direction = (CASE WHEN abnormal_return_d10>0.005 THEN 'positiv' WHEN abnormal_return_d10<-0.005 THEN 'negativ' ELSE 'neutral' END)) END,
  CASE WHEN abnormal_return_d20 IS NULL THEN NULL ELSE (predicted_direction = observed_direction_d20) END,
  CASE WHEN price_d20 IS NOT NULL THEN now() END
FROM confounding
ON CONFLICT (news_id, ticker) DO UPDATE SET
  price_d1=EXCLUDED.price_d1, price_d3=EXCLUDED.price_d3, price_d5=EXCLUDED.price_d5, price_d10=EXCLUDED.price_d10, price_d20=EXCLUDED.price_d20,
  return_d1=EXCLUDED.return_d1, return_d3=EXCLUDED.return_d3, return_d5=EXCLUDED.return_d5, return_d10=EXCLUDED.return_d10, return_d20=EXCLUDED.return_d20,
  abnormal_return_d1=EXCLUDED.abnormal_return_d1, abnormal_return_d3=EXCLUDED.abnormal_return_d3, abnormal_return_d5=EXCLUDED.abnormal_return_d5,
  abnormal_return_d10=EXCLUDED.abnormal_return_d10, abnormal_return_d20=EXCLUDED.abnormal_return_d20,
  direction_correct_d1=EXCLUDED.direction_correct_d1, direction_correct_d3=EXCLUDED.direction_correct_d3, direction_correct_d5=EXCLUDED.direction_correct_d5,
  direction_correct_d10=EXCLUDED.direction_correct_d10, direction_correct_d20=EXCLUDED.direction_correct_d20,
  status=EXCLUDED.status, updated_at=now(), completed_at=EXCLUDED.completed_at;

COMMIT;
