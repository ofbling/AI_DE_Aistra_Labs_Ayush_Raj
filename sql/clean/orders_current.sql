-- Clean model: orders_current
--
-- Current state per order_number only (last record wins), not a full SCD2
-- history like dim_outlet/dim_product -- no requirement so far needs order
-- lifecycle history, and the raw CDC stream stays available under
-- data/raw/erp_cdc/sales_order_header/ if that changes later. Don't build
-- ahead of an actual need.
--
-- L15  ~0.9% of orders are hard-deleted well after insert (tombstone
--      arrives late, __seq pushed +10,000,000 so it always sorts last).
--      Ordering by (op_ts, seq) DESC and taking the top row per order
--      handles this the same way dim_outlet/dim_product handle deletes:
--      if the latest record for a key is a 'D', that order is excluded
--      from this table entirely.
--
-- L14  PARTNER_API inflates order_value_gross by 8.5% (double-counted
--      freight, per the open Finance ticket in the feed contract that was
--      never closed out). NOT silently corrected here -- Finance owns
--      that number and the exact cause/factor isn't something a pipeline
--      should assume it knows for certain. Instead, source_system is kept
--      as reported and partner_api_freight_flag makes the known
--      discrepancy queryable. Any adjustment is a KPI-layer decision, not
--      a clean-layer one.
--
-- Note: source_system is drawn independently per CDC record in the
-- generator, not fixed per order -- in principle a single order's I/U
-- history could carry different source_system values across its records.
-- This table reports whatever the LATEST record says, consistent with
-- "current state" for every other column.

CREATE OR REPLACE TABLE clean.orders_current AS
WITH raw AS (
    SELECT
        order_number,
        __op AS op_type,
        __op_ts::TIMESTAMP AS op_ts,
        __seq::BIGINT AS seq,
        outlet_code,
        warehouse_code,
        route_code,
        order_date,
        requested_delivery_date,
        order_status,
        line_count,
        order_value_gross,
        discount_amount,
        tax_amount,
        source_system
    FROM read_parquet('data/raw/erp_cdc/sales_order_header/*/*.parquet', hive_partitioning = true)
),
latest AS (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY order_number ORDER BY op_ts DESC, seq DESC) AS rn
    FROM raw
)
SELECT
    order_number,
    outlet_code,
    warehouse_code,
    route_code,
    order_date,
    requested_delivery_date,
    order_status,
    line_count,
    order_value_gross,
    discount_amount,
    tax_amount,
    source_system,
    (source_system = 'PARTNER_API') AS partner_api_freight_flag,
    op_ts AS last_updated_ts
FROM latest
WHERE rn = 1 AND op_type != 'D';