-- KPI: Channel Reclassification History
--
-- Directly answers illustrative question 6: "which outlets changed
-- channel classification, and when." Made possible entirely by dim_outlet
-- being built as a full SCD2 history (see dim_outlet.sql) rather than a
-- current-state-only lookup -- this query would be impossible against a
-- table that only ever showed today's channel.
--
-- The date filter is applied in an OUTER query, after LAG() has already
-- run over the FULL, unfiltered history -- not folded into a single
-- WHERE clause. Filtering valid_from before computing LAG would silently
-- corrupt results at the boundary: an outlet's earliest version still
-- inside the date range would wrongly look like its very first version
-- ever (no "before" to compare against), hiding a real reclassification
-- that happened to have its prior version just outside the window.
--
-- QUALIFY + LAG() keeps only rows where the channel genuinely differs
-- from the immediately PRIOR version of the same outlet. An outlet's true
-- first version is correctly excluded (LAG returns NULL there -- an
-- initial assignment, not a reclassification). Versions where some OTHER
-- attribute changed but channel stayed the same are excluded too.

WITH reclassifications AS (
    SELECT
        outlet_code,
        LAG(channel) OVER (PARTITION BY outlet_code ORDER BY valid_from) AS channel_before,
        channel AS channel_after,
        valid_from AS changed_at,
        is_current
    FROM clean.dim_outlet
    QUALIFY channel != LAG(channel) OVER (PARTITION BY outlet_code ORDER BY valid_from)
)
SELECT *
FROM reclassifications
WHERE changed_at BETWEEN $start_date AND $end_date
ORDER BY changed_at, outlet_code;
