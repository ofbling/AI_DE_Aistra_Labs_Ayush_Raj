-- was going to stitch receive->dispatch into a cycle time here. checked
-- the generator first -- warehouse/order/sku/batch/pallet are all random
-- per scan, nothing links one to another. confirmed with a coincidence
-- check too. stays flat, no stitching, no fake join to orders

CREATE OR REPLACE TABLE marts.fact_wms_scan_event AS
SELECT
    s.scan_id, s.warehouse_code, w.warehouse_name, w.region_name,
    s.event_type, s.order_number, s.sku_code, s.batch_id, s.qty_cases,
    s.pallet_id, s.dock_door, s.operator_id, s.handheld_device,
    s.event_ts_ist, s.event_date, s.source_dt, s.source_path
FROM staging.wms_scan_events s
LEFT JOIN marts.dim_warehouse w ON s.warehouse_code = w.warehouse_code;