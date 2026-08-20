SELECT 'news_category' AS dimension, news_category AS value, 'D+1' AS horizon,
  count(*) FILTER (WHERE direction_correct_d1 IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d1 = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE direction_correct_d1 IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE direction_correct_d1 = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE direction_correct_d1 IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg(abnormal_return_d1) FILTER (WHERE direction_correct_d1 IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY abnormal_return_d1) FILTER (WHERE direction_correct_d1 IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d1 IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct_d1 IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE direction_correct_d1 IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, CASE WHEN confounded THEN 0.25 WHEN baseline_quality = 'high' THEN 1.0 WHEN baseline_quality = 'medium' THEN 0.7 WHEN baseline_quality = 'limited' THEN 0.4 ELSE 0.5 END AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND news_category IS NOT NULL
) t
GROUP BY news_category
UNION ALL
SELECT 'news_category' AS dimension, news_category AS value, 'D+3' AS horizon,
  count(*) FILTER (WHERE direction_correct_d3 IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d3 = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE direction_correct_d3 IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE direction_correct_d3 = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE direction_correct_d3 IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg(abnormal_return_d3) FILTER (WHERE direction_correct_d3 IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY abnormal_return_d3) FILTER (WHERE direction_correct_d3 IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d3 IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct_d3 IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE direction_correct_d3 IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, CASE WHEN confounded THEN 0.25 WHEN baseline_quality = 'high' THEN 1.0 WHEN baseline_quality = 'medium' THEN 0.7 WHEN baseline_quality = 'limited' THEN 0.4 ELSE 0.5 END AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND news_category IS NOT NULL
) t
GROUP BY news_category
UNION ALL
SELECT 'news_category' AS dimension, news_category AS value, 'D+5' AS horizon,
  count(*) FILTER (WHERE direction_correct_d5 IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d5 = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE direction_correct_d5 IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE direction_correct_d5 = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE direction_correct_d5 IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg(abnormal_return_d5) FILTER (WHERE direction_correct_d5 IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY abnormal_return_d5) FILTER (WHERE direction_correct_d5 IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d5 IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct_d5 IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE direction_correct_d5 IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, CASE WHEN confounded THEN 0.25 WHEN baseline_quality = 'high' THEN 1.0 WHEN baseline_quality = 'medium' THEN 0.7 WHEN baseline_quality = 'limited' THEN 0.4 ELSE 0.5 END AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND news_category IS NOT NULL
) t
GROUP BY news_category
UNION ALL
SELECT 'news_category' AS dimension, news_category AS value, 'D+10' AS horizon,
  count(*) FILTER (WHERE direction_correct_d10 IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d10 = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE direction_correct_d10 IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE direction_correct_d10 = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE direction_correct_d10 IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg(abnormal_return_d10) FILTER (WHERE direction_correct_d10 IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY abnormal_return_d10) FILTER (WHERE direction_correct_d10 IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d10 IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct_d10 IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE direction_correct_d10 IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, CASE WHEN confounded THEN 0.25 WHEN baseline_quality = 'high' THEN 1.0 WHEN baseline_quality = 'medium' THEN 0.7 WHEN baseline_quality = 'limited' THEN 0.4 ELSE 0.5 END AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND news_category IS NOT NULL
) t
GROUP BY news_category
UNION ALL
SELECT 'news_category' AS dimension, news_category AS value, 'D+20' AS horizon,
  count(*) FILTER (WHERE direction_correct_d20 IS NOT NULL) AS sample_size,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d20 = TRUE AND confounded = FALSE) / NULLIF(count(*) FILTER (WHERE direction_correct_d20 IS NOT NULL AND confounded = FALSE), 0), 1) AS direction_accuracy,
  round(100.0 * sum(case_weight) FILTER (WHERE direction_correct_d20 = TRUE) / NULLIF(sum(case_weight) FILTER (WHERE direction_correct_d20 IS NOT NULL), 0), 1) AS weighted_direction_accuracy,
  round(avg(abnormal_return_d20) FILTER (WHERE direction_correct_d20 IS NOT NULL)::numeric, 3) AS avg_abnormal_return,
  round(percentile_cont(0.5) WITHIN GROUP (ORDER BY abnormal_return_d20) FILTER (WHERE direction_correct_d20 IS NOT NULL)::numeric, 3) AS median_abnormal_return,
  round(100.0 * count(*) FILTER (WHERE direction_correct_d20 IS NOT NULL AND confounded = TRUE) / NULLIF(count(*) FILTER (WHERE direction_correct_d20 IS NOT NULL), 0), 1) AS confounded_pct,
  round(avg(prediction_confidence) FILTER (WHERE direction_correct_d20 IS NOT NULL)::numeric, 1) AS avg_confidence
FROM (
  SELECT *, CASE WHEN confounded THEN 0.25 WHEN baseline_quality = 'high' THEN 1.0 WHEN baseline_quality = 'medium' THEN 0.7 WHEN baseline_quality = 'limited' THEN 0.4 ELSE 0.5 END AS case_weight
  FROM trading.news_impact_tracking
  WHERE created_at >= now() - interval '90 days' AND status != 'failed' AND news_category IS NOT NULL
) t
GROUP BY news_category
ORDER BY dimension, value, horizon;
