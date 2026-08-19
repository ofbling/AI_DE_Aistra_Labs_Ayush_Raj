-- Marts dimension: dim_carrier
--
-- IMPORTANT GAP, not a defect list item because it isn't a data quality
-- problem -- it's a missing linkage. No raw feed (reefer_telemetry,
-- wms_scan_events, sales_order_header) carries a carrier_id or any field
-- that maps to one. reefer_telemetry has route_code and warehouse_code;
-- there is no route_code -> carrier_id table anywhere in data/reference/.
--
-- Practical effect: illustrative question 4 ("chilled trips breaching
-- temperature ... by carrier") is NOT ANSWERABLE from the feeds as given.
-- This table is loaded for completeness and in case a linkage shows up
-- later, but nothing in marts/ currently joins to it. Flagging this
-- explicitly rather than inventing a route->carrier mapping that isn't in
-- the source data.

CREATE OR REPLACE TABLE marts.dim_carrier AS
SELECT
    carrier_id,
    carrier_name,
    mode,
    sla_hours,
    rate_per_km
FROM read_csv_auto('data/reference/carrier_master.csv');
