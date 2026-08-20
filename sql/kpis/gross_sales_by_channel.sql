-- KPI: Gross Sales by Channel
--
-- Formula uses raw qty, NOT qty_eaches. Checked against the generator:
-- unit_price, qty, discount_amount and tax_amount are all computed from
-- each other as one internally consistent group (discount_amount and
-- tax_amount are both literally unit_price * qty * <rate>) -- uom/case
-- packaging plays no part in that math at all. Using qty_eaches here
-- would overstate revenue on the ~19% of pre-drift rows sold by the case
-- by up to case_pack times (6-30x), and would no longer reconcile against
-- discount_amount/tax_amount on those same rows. qty_eaches is correct
-- for a UNITS metric (see units_sold_eaches.sql), not a REVENUE one.
--
-- channel_master (the ERP outlet record, correct for the point in time of
-- sale) is used as the reporting dimension, not channel_pos (what the
-- till happened to say) -- channel_master is the more authoritative,
-- CDC-replayed source. channel_pos remains available in fact_sales for
-- diagnosing till/master disagreement, which is a different question.
--
-- Grain: channel x business_date. Aggregate further (week/month/quarter)
-- by joining marts.dim_date and grouping on its fiscal columns instead of
-- business_date directly.

SELECT
    channel_master AS channel,
    business_date,
    round(sum(unit_price * qty), 2) AS gross_sales_inr,
    sum(qty) AS units_sold_native,
    count(*) AS line_count
FROM marts.fact_sales
WHERE business_date BETWEEN $start_date AND $end_date
GROUP BY channel_master, business_date
ORDER BY business_date, channel;
