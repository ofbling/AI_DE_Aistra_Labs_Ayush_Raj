-- Clean model: dim_product (SCD2)
--
-- Same replay pattern as dim_outlet.sql: order by (__op_ts, __seq), never
-- extract_date (L12, which applies to this feed too), LEAD() to compute
-- valid_to, deletes close out the prior version without becoming one.
--
-- Note: L13 (the deliberate same-__op_ts tie) was only injected into
-- outlet_master in the generator, not product_master -- so no tie-break
-- spot-check is expected to find anything here. The ordering logic handles
-- it identically either way; there just isn't a planted case to prove it
-- against for this table.

CREATE OR REPLACE TABLE clean.dim_product AS
WITH raw AS (
    SELECT
        sku_code,
        __op AS op_type,
        __op_ts::TIMESTAMP AS op_ts,
        __seq::BIGINT AS seq,
        product_name,
        category,
        brand,
        case_pack,
        mrp,
        list_price,
        gst_rate_pct,
        shelf_life_days,
        is_chilled,
        status
    FROM read_parquet('data/raw/erp_cdc/product_master/*/*.parquet', hive_partitioning = true)
),
ordered AS (
    SELECT
        *,
        LEAD(op_ts) OVER (PARTITION BY sku_code ORDER BY op_ts, seq) AS valid_to
    FROM raw
)
SELECT
    sku_code,
    product_name,
    category,
    brand,
    case_pack,
    mrp,
    list_price,
    gst_rate_pct,
    shelf_life_days,
    is_chilled,
    status,
    op_ts AS valid_from,
    valid_to,
    (valid_to IS NULL) AS is_current
FROM ordered
WHERE op_type != 'D'
ORDER BY sku_code, valid_from;
