-- Clean model: dim_outlet (SCD2)
--
-- Reads erp_cdc/outlet_master directly rather than through a separate
-- staging model first: unlike pos_transactions/reefer_telemetry, there is
-- no schema drift or corrupt file to work around before replay logic can
-- run, so typing and replay happen together here.
--
-- L12  ~1.6% of records land in a LATER extract_date than their __op_ts.
--      extract_date (file-arrival date) is never used for ordering below --
--      only __op_ts and __seq are, per the contract's own correction.
-- L13  ~1% of keys carry two records with an identical __op_ts. __seq
--      breaks the tie. Confirmed this resolves correctly: a tied pair
--      produces a real but zero-duration version for the earlier __seq,
--      immediately superseded by the later __seq's version -- kept in the
--      output rather than filtered, for full traceability.
-- (KP-3155) this table is what "no point-in-time view of outlet
--      attributes" was asking for: valid_from/valid_to/is_current give
--      both current-state and historical answers from one table.
--
-- Deletes (__op = 'D') are not exposed as versions -- their attribute
-- payload isn't meaningful -- but their op_ts still closes out the prior
-- version via the LEAD() window below, so a deleted outlet correctly ends
-- up with no is_current row, rather than a stale one.

CREATE SCHEMA IF NOT EXISTS clean;

CREATE OR REPLACE TABLE clean.dim_outlet AS
WITH raw AS (
    SELECT
        outlet_code,
        __op AS op_type,
        __op_ts::TIMESTAMP AS op_ts,
        __seq::BIGINT AS seq,
        outlet_name,
        channel,
        outlet_format,
        city,
        route_code,
        warehouse_code,
        credit_limit,
        credit_terms_days,
        gst_number,
        status
    FROM read_parquet('data/raw/erp_cdc/outlet_master/*/*.parquet', hive_partitioning = true)
),
ordered AS (
    SELECT
        *,
        LEAD(op_ts) OVER (PARTITION BY outlet_code ORDER BY op_ts, seq) AS valid_to
    FROM raw
)
SELECT
    outlet_code,
    outlet_name,
    channel,
    outlet_format,
    city,
    route_code,
    warehouse_code,
    credit_limit,
    credit_terms_days,
    gst_number,
    status,
    op_ts AS valid_from,
    valid_to,
    (valid_to IS NULL) AS is_current
FROM ordered
WHERE op_type != 'D'
ORDER BY outlet_code, valid_from;
