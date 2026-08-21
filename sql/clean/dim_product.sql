-- Clean model: dim_product (SCD2)

-- same scd2 pattern as dim_outlet. no L13 tie planted in this table
-- (checked -- only outlet_master got that one), everything else applies

CREATE OR REPLACE TABLE clean.dim_product AS
WITH raw AS (
    SELECT sku_code, __op AS op_type, __op_ts::TIMESTAMP AS op_ts, __seq::BIGINT AS seq,
        product_name, category, brand, case_pack, mrp, list_price,
        gst_rate_pct, shelf_life_days, is_chilled, status
    FROM read_parquet('data/raw/erp_cdc/product_master/*/*.parquet', hive_partitioning = true)
),
ordered AS (
    SELECT *, LEAD(op_ts) OVER (PARTITION BY sku_code ORDER BY op_ts, seq) AS valid_to
    FROM raw
)
SELECT sku_code, product_name, category, brand, case_pack, mrp, list_price,
    gst_rate_pct, shelf_life_days, is_chilled, status,
    op_ts AS valid_from, valid_to, (valid_to IS NULL) AS is_current
FROM ordered WHERE op_type != 'D' ORDER BY sku_code, valid_from;
