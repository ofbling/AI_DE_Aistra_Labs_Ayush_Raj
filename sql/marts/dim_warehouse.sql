-- all 8 sites are Asia/Kolkata today -- keeping the real column instead
-- of hardcoding that, so a future non-IST warehouse shows up as data

CREATE OR REPLACE TABLE marts.dim_warehouse AS
SELECT warehouse_code, warehouse_name, city, region_name, timezone, chilled_capacity_pallets
FROM read_csv_auto('data/reference/warehouse_master.csv');