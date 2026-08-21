-- Staging model: wms_scan_events

-- no real defects here, just types + lineage. checked "site local"
-- warehouse_master the contract documents event_ts as "site local", not
-- UTC
-- all 8 sites are IST so no shift needed
--(~6.5% of scan events never emitted) is NOT handled here --
-- there's no data to recover, so nothing to fix at this layer

CREATE OR REPLACE TABLE staging.wms_scan_events AS
SELECT scan_id, warehouse_code, event_type, order_number, sku_code, batch_id,
    qty_cases, pallet_id, dock_door, operator_id, handheld_device,
    event_ts::TIMESTAMP AS event_ts_ist,
    CAST(event_ts::TIMESTAMP AS DATE) AS event_date,
    dt AS source_dt, filename AS source_path
FROM read_parquet('data/raw/wms_scan_events/*/*.parquet', hive_partitioning = true, filename = true);