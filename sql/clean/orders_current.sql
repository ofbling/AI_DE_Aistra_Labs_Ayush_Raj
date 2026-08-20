-- Clean model: orders_current
--
-- Current state per order_number only (last record wins), not a full SCD2
-- history like dim_outlet/dim_product -- no requirement so far needs order
-- lifecycle history, and the raw CDC stream stays available under
-- data/raw/erp_cdc/sales_order_header/ if that changes later. Don't build
-- ahead of an actual need.
--
-- ORDERING: seq DESC alone, NOT (op_ts, seq) the way dim_outlet/dim_product
-- use it. Found empirically -- Order Value by Source System came back with
-- exactly 320,000 orders (the full universe) instead of the ~317,120
-- expected after ~0.9% tombstoning (L15). Root cause, traced in the
-- generator: sales_order_header's delete rows are cloned directly from
-- their original INSERT row and only __op, __seq, and extract_date get
-- overwritten -- __op_ts is left untouched, stuck at the original insert
-- time. Every order with at least one update (nearly all of them) then
-- has update records with a genuinely LATER __op_ts than their own stale
-- delete, so ordering by op_ts first always picks the update, never the
-- delete, and the tombstone silently never took effect.
--
-- __seq does not have this problem: the delete's seq is always
-- original_insert_seq + 10,000,000, guaranteed higher than any real
-- record for that order (ordinary seq tops out around a million), and for
-- every NON-delete record in this table __seq increases in exact lockstep
-- with __op_ts anyway (each order's updates are generated with step and
-- day moving together), so sorting by seq alone gives an identical result
-- to (op_ts, seq) for every row except the one case that needed fixing.
--
-- This is NOT a blanket "trust seq over op_ts" rule -- the opposite holds
-- for dim_outlet/dim_product, where update seq is assigned by a simple
-- incrementing loop independent of each update's randomly-drawn day, so
-- seq order there does NOT track true chronological order and op_ts has
-- to stay primary. The right ordering key depends on how each table's CDC
-- stream was actually built, not one rule applied everywhere.
--
-- order_date and requested_delivery_date are cast to DATE here -- the raw
-- feed stores them as plain ISO strings, not a real date type. Casting
-- once here instead of requiring every downstream query to remember to.
--
-- L15  tombstones now actually take effect -- see above.
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
        ROW_NUMBER() OVER (PARTITION BY order_number ORDER BY seq DESC) AS rn
    FROM raw
)
SELECT
    order_number,
    outlet_code,
    warehouse_code,
    route_code,
    order_date::DATE AS order_date,
    requested_delivery_date::DATE AS requested_delivery_date,
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
