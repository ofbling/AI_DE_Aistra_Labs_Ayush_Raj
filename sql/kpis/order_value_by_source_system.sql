-- the query that caught orders_current's tombstone bug -- totals used to
-- sum to the full 320k order universe, now correctly land at 317,120
SELECT source_system, count(*) AS orders,
    round(avg(order_value_gross), 0) AS avg_order_value_gross,
    round(sum(order_value_gross), 0) AS total_order_value_gross
FROM clean.orders_current
WHERE order_date BETWEEN $start_date AND $end_date
GROUP BY source_system
ORDER BY source_system;
