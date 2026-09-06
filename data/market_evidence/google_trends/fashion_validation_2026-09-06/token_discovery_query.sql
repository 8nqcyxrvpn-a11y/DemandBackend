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
SELECT source_table, LOWER(term) AS term, COUNT(*) AS raw_rows,
       COUNT(DISTINCT week) AS week_count, MIN(week) AS earliest_week,
       MAX(week) AS latest_week, COUNT(DISTINCT dma_id) AS dma_count
FROM matches
GROUP BY source_table, term
ORDER BY source_table, raw_rows DESC, term;
