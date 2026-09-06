WITH vocabulary AS (
  SELECT term
  FROM UNNEST([
    "dress", "dresses", "skirt", "skirts", "blazer", "blazers", "trench coat",
    "jeans", "barrel jeans", "wide leg jeans", "cargo pants", "cardigan", "vest",
    "coat", "jacket", "silk", "cashmere", "linen", "suede", "leather", "denim",
    "velvet", "satin", "lace", "burgundy", "chocolate brown", "butter yellow",
    "olive green", "navy blue", "powder pink", "maxi dress", "midi skirt",
    "bubble skirt", "drop waist dress", "wide leg pants", "straight leg jeans",
    "oversized blazer", "loafers", "ballet flats", "mary janes", "knee high boots",
    "sneakers", "mules", "tote bag", "crossbody bag", "shoulder bag", "bucket bag",
    "clutch", "handbag", "ready to wear", "womens clothing", "womens fashion",
    "fashion trends", "coach", "camel", "tan", "platform", "slip"
  ]) AS term
), matches AS (
  SELECT "top_rising_terms" AS source_table, refresh_date, week, dma_id, term
  FROM `bigquery-public-data.google_trends.top_rising_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week BETWEEN DATE "2026-06-07" AND DATE "2026-08-30"
    AND LOWER(term) IN (SELECT term FROM vocabulary)
  UNION ALL
  SELECT "top_terms" AS source_table, refresh_date, week, dma_id, term
  FROM `bigquery-public-data.google_trends.top_terms`
  WHERE refresh_date = DATE "2026-09-03"
    AND week BETWEEN DATE "2026-06-07" AND DATE "2026-08-30"
    AND LOWER(term) IN (SELECT term FROM vocabulary)
)
SELECT
  source_table,
  COUNT(*) AS raw_rows,
  COUNT(DISTINCT FORMAT("%s|%s|%s", week, LOWER(term), dma_id)) AS distinct_dma_observations,
  COUNT(DISTINCT FORMAT("%s|%s", week, LOWER(term))) AS deduplicated_term_weeks,
  MIN(week) AS earliest_week,
  MAX(week) AS latest_week
FROM matches
GROUP BY source_table
ORDER BY source_table;
