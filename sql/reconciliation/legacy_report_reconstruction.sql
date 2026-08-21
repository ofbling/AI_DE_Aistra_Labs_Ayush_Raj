-- reproduces the two bugs divya described, on purpose, using real pos
-- data -- groups by ingest_date not business_date, and skips dedup.
-- both are already fixed in staging.pos_transactions; this deliberately
-- undoes both to test whether that's what the legacy report actually did

CREATE SCHEMA IF NOT EXISTS reconciliation;

CREATE OR REPLACE TABLE reconciliation.legacy_reconstruction AS
WITH raw AS (
    SELECT *
    FROM read_parquet('data/raw/pos_transactions/*/*.parquet',
        hive_partitioning = true, union_by_name = true)
),
weekly AS (
    SELECT
        channel,
        DATE '2025-01-01' + (FLOOR(date_diff('day', DATE '2025-01-01', ingest_date::DATE) / 7.0)::INTEGER * 7) AS week_ending,
        COALESCE(qty, quantity_units) AS qty,
        unit_price,
        basket_id
    FROM raw
)
SELECT
    week_ending,
    channel,
    round(sum(unit_price * qty), 2) AS reconstructed_gross_sales_inr,
    sum(qty) AS reconstructed_units_sold,
    count(DISTINCT basket_id) AS reconstructed_basket_count
FROM weekly
GROUP BY week_ending, channel
ORDER BY week_ending, channel;
