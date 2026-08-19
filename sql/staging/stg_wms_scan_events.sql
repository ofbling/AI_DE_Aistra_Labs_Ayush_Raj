-- Staging model: wms_scan_events
--
-- No schema drift, no vendor/unit issues, and no duplicate-emission defect
-- for this feed (scan_id is generated as a unique per-row id in the
-- source; there is nothing in generate_dataset.py that clones wms rows the
-- way it does for pos_transactions/reefer_telemetry) -- so this model is
-- mostly type/lineage cleanup, not defect correction.
--
-- Timestamp handling: the contract documents event_ts as "site local", not
-- UTC. Checked rather than assumed (per 03_Working_With_The_Data.md's own
-- warning that feeds don't agree on what their timestamps mean): every one
-- of the 8 sites in warehouse_master.csv is Asia/Kolkata, so site-local
-- already equals IST and no offset is applied here. This is a load-bearing
-- assumption, not a given -- if a warehouse in another timezone were ever
-- onboarded, this model would need to join warehouse_master and apply a
-- per-site offset instead of treating every row as already-IST.
--
-- DEFECT L11 (~6.5% of scan events never emitted) is NOT handled here --
-- there's no data to recover, so nothing to fix at this layer. It surfaces
-- downstream wherever a cycle-time KPI stitches stage events together.

CREATE OR REPLACE TABLE staging.wms_scan_events AS
SELECT
    scan_id,
    warehouse_code,
    event_type,
    order_number,
    sku_code,
    batch_id,
    qty_cases,
    pallet_id,
    dock_door,
    operator_id,
    handheld_device,
    event_ts::TIMESTAMP AS event_ts_ist,
    CAST(event_ts::TIMESTAMP AS DATE) AS event_date,
    dt AS source_dt,
    filename AS source_path
FROM read_parquet(
    'data/raw/wms_scan_events/*/*.parquet',
    hive_partitioning = true,
    filename = true
);
