-- Marts fact: fact_wms_scan_event
--
-- IMPORTANT FINDING, not one of the 18 named defects: there is no field in
-- wms_scan_events that reliably links a RECEIVE scan to the DISPATCH scan
-- for the same physical goods. Checked the generator directly --
-- warehouse_code, order_number, sku_code, batch_id, and pallet_id are each
-- drawn independently at random per scan row, with no shared key tying a
-- chain of stage events together for one job. order_number in particular
-- is semantically suspect even before checking the code: RECEIVE/PUTAWAY
-- are inbound-from-supplier events, unrelated to which outbound sales
-- order the stock eventually fulfils.
--
-- Practical effect: a genuine, traceable "dock-to-dispatch cycle time per
-- job" (illustrative question 5, and one of the three metrics Divya named
-- explicitly) CANNOT be computed from this feed as shipped -- not because
-- of DEFECT L11 (missing scans, which just makes an already-hard problem
-- harder), but because there is no linking key to stitch on even with
-- zero missing scans. This is a data gap, not a data quality issue -- the
-- same category as dim_carrier's missing linkage.
--
-- This table stays at honest scan grain: cleaned, typed, warehouse-joined,
-- nothing stitched. No join to orders_current on order_number -- doing so
-- would attach a spurious, effectively random order's details to each
-- scan and imply a real relationship that isn't there.
--
-- An approximate, clearly-labeled cycle-time PROXY (warehouse+day level:
-- gap between typical RECEIVE and typical DISPATCH times, not a per-job
-- number) belongs in the KPI query library, not here -- naming it a "fact"
-- at this grain would overstate what it actually is.

CREATE OR REPLACE TABLE marts.fact_wms_scan_event AS
SELECT
    s.scan_id,
    s.warehouse_code,
    w.warehouse_name,
    w.region_name,
    s.event_type,
    s.order_number,
    s.sku_code,
    s.batch_id,
    s.qty_cases,
    s.pallet_id,
    s.dock_door,
    s.operator_id,
    s.handheld_device,
    s.event_ts_ist,
    s.event_date,
    s.source_dt,
    s.source_path
FROM staging.wms_scan_events s
LEFT JOIN marts.dim_warehouse w
    ON s.warehouse_code = w.warehouse_code;
