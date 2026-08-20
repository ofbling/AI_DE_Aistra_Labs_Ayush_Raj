-- KPI: Units Sold, in Eaches
--
-- Uses qty_eaches (not raw qty) -- this is a volume metric, so cases are
-- correctly expanded to their eaches count via dim_product.case_pack
-- (see fact_sales.sql for why case_pack, not uom_conversion.csv). This is
-- the one KPI where qty_eaches is the right column; gross_sales_by_channel
-- deliberately does NOT use it (see that file's comment).
--
-- Grain: business_date (add channel/category to GROUP BY if a breakdown
-- is needed; left out here to match illustrative question 3's phrasing,
-- "units sold last month," which asks for a single total).

SELECT
    business_date,
    sum(qty_eaches) AS units_sold_eaches
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY business_date
ORDER BY business_date;
