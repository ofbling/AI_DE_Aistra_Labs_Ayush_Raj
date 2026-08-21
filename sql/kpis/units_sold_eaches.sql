-- this one DOES want qty_eaches -- it's a volume question not a money one
SELECT business_date, sum(qty_eaches) AS units_sold_eaches
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY business_date
ORDER BY business_date;
