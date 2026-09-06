WITH candidates AS (
  SELECT "top_rising_terms" AS source_table, refresh_date, week, dma_id, dma_name,
         term, score, rank, percent_gain
  FROM `bigquery-public-data.google_trends.top_rising_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week IN (DATE "2026-06-07", DATE "2026-07-19", DATE "2026-08-30")
    AND LOWER(term) = "white sox vs astros"
  UNION ALL
  SELECT "top_terms" AS source_table, refresh_date, week, dma_id, dma_name,
         term, score, rank, CAST(NULL AS INT64) AS percent_gain
  FROM `bigquery-public-data.google_trends.top_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week IN (DATE "2026-06-07", DATE "2026-07-19", DATE "2026-08-30")
    AND LOWER(term) = "leon black"
)
SELECT *
FROM candidates
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY source_table, week, LOWER(term) ORDER BY dma_id
) <= 3
ORDER BY source_table, week, dma_id;
