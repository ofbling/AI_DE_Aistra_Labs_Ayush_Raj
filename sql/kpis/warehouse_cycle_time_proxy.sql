-- KPI: Warehouse Cycle Time -- APPROXIMATE PROXY, read the limitations
-- before using this number for anything.
--
-- A true per-job dock-to-dispatch cycle time is NOT computable from this
-- data. Checked directly in fact_wms_scan_event.sql: no field links a
-- RECEIVE scan to the DISPATCH scan for the same physical goods --
-- warehouse_code, order_number, sku_code, batch_id and pallet_id are all
-- assigned independently at random per scan in the source system.
-- Confirmed empirically too: matching a DISPATCH event to a same-pallet
-- prior RECEIVE at the same warehouse succeeds at almost exactly the rate
-- pure chance predicts (~3.76% observed vs ~3.8% expected), not the
-- near-100% a real link would produce.
--
-- What follows instead is a coarse, warehouse-level PROXY: for each
-- warehouse and day, the gap between the typical (median) time-of-day a
-- RECEIVE scan happens and the typical time-of-day a DISPATCH scan
-- happens, averaged across days. This does NOT track any single item's
-- journey -- it is a rough measure of how spread out handling activity is
-- across a warehouse's day, nothing more.
--
-- PREDICTION TO CHECK, not an assumed fact: the generator assigns each
-- scan's time as a random base time plus a FIXED +15 minutes per handling
-- stage (RECEIVE=+0 ... DISPATCH=+75min). If that's really how the data
-- was built, this query should return close to 75 minutes at nearly every
-- warehouse, regardless of real differences between them -- which would
-- mean the number reflects the data generation mechanism, not warehouse
-- performance. Run it and see before trusting this as a real signal.

WITH daily AS (
    SELECT
        warehouse_name,
        event_date,
        median(event_ts_ist) FILTER (WHERE event_type = 'RECEIVE')  AS median_receive_ts,
        median(event_ts_ist) FILTER (WHERE event_type = 'DISPATCH') AS median_dispatch_ts
    FROM marts.fact_wms_scan_event
    WHERE event_date BETWEEN $start_date AND $end_date
    GROUP BY warehouse_name, event_date
    HAVING median_receive_ts IS NOT NULL AND median_dispatch_ts IS NOT NULL
)
SELECT
    warehouse_name,
    count(*) AS days_with_data,
    round(avg(date_diff('minute', median_receive_ts, median_dispatch_ts)), 1) AS avg_daily_gap_minutes
FROM daily
GROUP BY warehouse_name
ORDER BY warehouse_name;
