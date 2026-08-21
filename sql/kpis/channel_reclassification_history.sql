-- date filter has to go OUTSIDE the lag() comparison, not folded into
-- the same where clause -- otherwise filtering cuts off the "before"
-- row and every boundary case looks like a first-ever assignment

WITH reclassifications AS (
    SELECT outlet_code,
        LAG(channel) OVER (PARTITION BY outlet_code ORDER BY valid_from) AS channel_before,
        channel AS channel_after, valid_from AS changed_at, is_current
    FROM clean.dim_outlet
    QUALIFY channel != LAG(channel) OVER (PARTITION BY outlet_code ORDER BY valid_from)
)
SELECT * FROM reclassifications
WHERE changed_at BETWEEN $start_date AND $end_date
ORDER BY changed_at, outlet_code;
