-- KPI: Basket Count
--
-- Distinct baskets, not line count or transaction count -- basket_id is
-- what the contract documents as "groups lines into one shopper
-- transaction," so this is genuinely "how many shopping trips," not "how
-- many receipt lines."

SELECT
    channel_master AS channel,
    business_date,
    count(DISTINCT basket_id) AS basket_count
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY channel_master, business_date
ORDER BY business_date, channel;
