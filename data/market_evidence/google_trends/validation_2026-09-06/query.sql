SELECT refresh_date, week, dma_id, dma_name, term, score, rank, percent_gain
FROM `bigquery-public-data.google_trends.top_rising_terms`
WHERE refresh_date = DATE "2026-09-03"
ORDER BY week DESC, rank ASC, dma_id ASC
LIMIT 5
