-- distinct baskets = shopping trips, not receipt lines
SELECT channel_master AS channel, business_date, count(DISTINCT basket_id) AS basket_count
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY channel_master, business_date
ORDER BY business_date, channel;
