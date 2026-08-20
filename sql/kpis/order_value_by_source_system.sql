-- KPI: Order Value by Source System
--
-- Directly answers illustrative question 7: "Order value by source
-- system, and whether the three sources are comparable."
--
-- Uses orders_current (latest known state per order), not a sum across
-- every historical version of an order -- order_value_gross is a
-- point-in-time attribute of the order's current state, not something to
-- add up across an order's own revision history.
--
-- Prediction, worth checking against the real numbers: order_value_gross
-- is drawn from the same Uniform(2000, 480000) range for all three source
-- systems in the generator, so SFA_MOBILE and ERP_WEB should average
-- close to each other (~241,000), and PARTNER_API should average close to
-- 8.5% higher (~261,500) -- purely from the known multiplier, not from
-- orders actually being any larger.

SELECT
    source_system,
    count(*) AS orders,
    round(avg(order_value_gross), 0) AS avg_order_value_gross,
    round(sum(order_value_gross), 0) AS total_order_value_gross
FROM clean.orders_current
WHERE order_date BETWEEN $start_date AND $end_date
GROUP BY source_system
ORDER BY source_system;
