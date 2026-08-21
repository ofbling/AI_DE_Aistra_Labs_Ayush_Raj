-- Clean model: dim_outlet (SCD2)

-- Reads erp_cdc/outlet_master directly rather than through a separate
-- staging model first: unlike pos_transactions/reefer_telemetry, there is
-- no schema drift or corrupt file to work around before replay logic can
-- run, so typing and replay happen together here.

-- scd2 replay. sort by (op_ts, seq), never extract_date -- extract_date
-- lags the real change date on ~1.6% of records. deletes get dropped but
-- their timestamp still closes out the row before them

CREATE SCHEMA IF NOT EXISTS clean;

CREATE OR REPLACE TABLE clean.dim_outlet AS
WITH raw AS (
    SELECT outlet_code, __op AS op_type, __op_ts::TIMESTAMP AS op_ts, __seq::BIGINT AS seq,
        outlet_name, channel, outlet_format, city, route_code, warehouse_code,
        credit_limit, credit_terms_days, gst_number, status
    FROM read_parquet('data/raw/erp_cdc/outlet_master/*/*.parquet', hive_partitioning = true)
),
ordered AS (
    SELECT *, LEAD(op_ts) OVER (PARTITION BY outlet_code ORDER BY op_ts, seq) AS valid_to
    FROM raw
)
SELECT outlet_code, outlet_name, channel, outlet_format, city, route_code,
    warehouse_code, credit_limit, credit_terms_days, gst_number, status,
    op_ts AS valid_from, valid_to, (valid_to IS NULL) AS is_current
FROM ordered WHERE op_type != 'D' ORDER BY outlet_code, valid_from;
