-- Marts dimension: dim_warehouse
-- Direct load. All 8 sites are Asia/Kolkata (verified during
-- wms_scan_events staging) -- timezone is carried through here so any
-- future warehouse outside IST is caught by a data change, not a
-- hardcoded assumption breaking silently.

CREATE OR REPLACE TABLE marts.dim_warehouse AS
SELECT
    warehouse_code,
    warehouse_name,
    city,
    region_name,
    timezone,
    chilled_capacity_pallets
FROM read_csv_auto('data/reference/warehouse_master.csv');
