-- Clean model: orders_current

-- PARTNER_API inflates order_value_gross by 8.5% (double-counted
-- freight, per the open Finance ticket in the feed contract that was
-- never closed out). 
-- Instead, source_system is kept
-- as reported and partner_api_freight_flag makes the known
-- discrepancy queryable.

-- latest record per order wins. ordering by seq alone here, not
-- (op_ts, seq) like the other two cdc tables -- this feed's delete rows
-- keep the original insert's op_ts, so that ordering never actually fired

CREATE OR REPLACE TABLE clean.orders_current AS
WITH raw AS (
    SELECT
        order_number, __op AS op_type,
        __op_ts::TIMESTAMP AS op_ts, __seq::BIGINT AS seq,
        outlet_code, warehouse_code, route_code,
        order_date::DATE AS order_date,
        requested_delivery_date::DATE AS requested_delivery_date,
        order_status, line_count, order_value_gross,
        discount_amount, tax_amount, source_system
    FROM read_parquet('data/raw/erp_cdc/sales_order_header/*/*.parquet', hive_partitioning = true)
),
latest AS (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_number ORDER BY seq DESC) AS rn
    FROM raw
)
SELECT
    order_number, outlet_code, warehouse_code, route_code,
    order_date, requested_delivery_date, order_status, line_count,
    order_value_gross, discount_amount, tax_amount, source_system,
    (source_system = 'PARTNER_API') AS partner_api_freight_flag,
    op_ts AS last_updated_ts
FROM latest
WHERE rn = 1 AND op_type != 'D';
