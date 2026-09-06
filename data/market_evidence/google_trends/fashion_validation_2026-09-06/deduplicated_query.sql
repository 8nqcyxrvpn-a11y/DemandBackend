WITH matches AS (
  SELECT "top_rising_terms" AS source_table, refresh_date, week, dma_id, dma_name,
         term, score, rank, percent_gain
  FROM `bigquery-public-data.google_trends.top_rising_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week BETWEEN DATE "2026-06-07" AND DATE "2026-08-30"
    AND REGEXP_CONTAINS(LOWER(term), r'(dress|skirt|jeans|shoe|sneaker|boot|bag|purse|fashion|outfit|shirt|pants|jacket|coat|sweater|cardigan|silk|linen|leather|suede|denim|lace|velvet|satin|burgundy|pink|blue|green|brown|black|white)')
  UNION ALL
  SELECT "top_terms" AS source_table, refresh_date, week, dma_id, dma_name,
         term, score, rank, CAST(NULL AS INT64) AS percent_gain
  FROM `bigquery-public-data.google_trends.top_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week BETWEEN DATE "2026-06-07" AND DATE "2026-08-30"
    AND REGEXP_CONTAINS(LOWER(term), r'(dress|skirt|jeans|shoe|sneaker|boot|bag|purse|fashion|outfit|shirt|pants|jacket|coat|sweater|cardigan|silk|linen|leather|suede|denim|lace|velvet|satin|burgundy|pink|blue|green|brown|black|white)')
)
SELECT source_table, refresh_date, week, LOWER(term) AS term,
       COUNT(*) AS raw_dma_rows, COUNT(DISTINCT dma_id) AS distinct_dmas,
       MIN(score) AS min_score, MAX(score) AS max_score, AVG(score) AS avg_score,
       MIN(rank) AS min_rank, MAX(rank) AS max_rank,
       MIN(percent_gain) AS min_percent_gain, MAX(percent_gain) AS max_percent_gain,
       ARRAY_AGG(STRUCT(dma_id, dma_name, score, rank, percent_gain)
                 ORDER BY dma_id LIMIT 25) AS dma_provenance_sample
FROM matches
GROUP BY source_table, refresh_date, week, term
ORDER BY source_table, week, term;
