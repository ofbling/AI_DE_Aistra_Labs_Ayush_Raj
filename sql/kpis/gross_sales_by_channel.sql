-- uses qty, NOT qty_eaches -- discount_amount/tax_amount in the source
-- are computed off raw qty too (checked the generator), so using eaches
-- here would stop reconciling against those on case-sold lines

SELECT
    channel_master AS channel, business_date,
    round(sum(unit_price * qty), 2) AS gross_sales_inr,
    sum(qty) AS units_sold_native,
    count(*) AS line_count
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY channel_master, business_date
ORDER BY business_date, channel;
