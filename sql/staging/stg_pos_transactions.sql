-- Staging model: pos_transactions
-- Fixes applied here (context-free -- no joins to reference data):
--   L4  schema drift: qty/quantity_units unified into one `qty` column
--   L2  event_ts is UTC; business_date is derived in Asia/Kolkata (UTC+5:30,
--       no DST, so a fixed offset is correct, not an approximation)
--   L3  exact duplicate rows from at-least-once delivery, deduped on the
--       documented natural key (txn_id, txn_line_no)
-- ingest_date (landing date) is kept distinct from business_date (derived
-- from event_ts) on purpose -- the legacy Finance report groups by the
-- former; correct reporting must group by the latter.

CREATE OR REPLACE TABLE staging.pos_transactions AS
WITH raw AS (
    SELECT *
    FROM read_parquet(
        'data/raw/pos_transactions/*/*.parquet',
        hive_partitioning = true,
        union_by_name = true,
        filename = true
    )
),
typed AS (
    SELECT
        txn_id,
        txn_line_no,
        basket_id,
        outlet_code,
        channel,
        sku_code,
        COALESCE(qty, quantity_units)::INTEGER AS qty,
        uom,
        loyalty_id,
        unit_price,
        discount_amount,
        tax_amount,
        payment_mode,
        till_id,
        cashier_id,
        promo_code,
        source_file,
        event_ts::TIMESTAMP AS event_ts_utc,
        event_ts::TIMESTAMP + INTERVAL 330 MINUTE AS event_ts_ist,
        CAST(event_ts::TIMESTAMP + INTERVAL 330 MINUTE AS DATE) AS business_date,
        ingest_date,
        filename AS source_path
    FROM raw
),
deduped AS (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY txn_id, txn_line_no ORDER BY event_ts_utc
           ) AS rn
    FROM typed
)
SELECT * EXCLUDE (rn)
FROM deduped
WHERE rn = 1;
