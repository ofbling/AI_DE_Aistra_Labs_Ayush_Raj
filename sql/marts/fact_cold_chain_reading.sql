-- Marts fact: fact_cold_chain_reading
--
-- Grain: one row per cleaned reefer_telemetry reading (device, reading_ts).
-- The source schema has no trip/journey identifier -- readings are tagged
-- with route_code and warehouse_code "at time of reading," not grouped
-- into discrete trips -- so this stays at reading grain rather than
-- inventing trip boundaries the data doesn't support. Illustrative
-- question 4's "chilled trips" will need to be approximated as
-- readings-per-route-per-day at the KPI layer, not resolved here.
--
-- Excursion definition follows the feed contract literally: "Target band
-- for chilled product is 2 to 8 degrees Celsius. An excursion is any
-- reading above the band." That's ABOVE only, not outside -- so
-- above_band is what the contract calls an excursion; below_band is kept
-- as a separate, distinct signal since a reading under 2C is arguably just
-- as operationally relevant (product literally freezing) even though the
-- contract's own definition doesn't count it as an "excursion." Exposing
-- both rather than silently picking one.
--
-- L5/L6/L7 (clock skew, vendor units, missing temp_unit) are already fixed
-- upstream in staging.reefer_telemetry -- temp_c here is the normalized
-- value. Raw temp_value and temp_unit_resolved are carried through anyway,
-- not for use in a real excursion KPI, but so the naive-vs-normalized
-- comparison in run_marts.py can be run directly against this table.
--
-- L8 (null temp_value) stays NULL through temp_c, and above_band/
-- below_band correctly evaluate to NULL rather than FALSE for those rows
-- -- SQL's three-valued logic means COUNT(*) FILTER (WHERE above_band)
-- naturally excludes them, so an excursion-rate query doesn't need extra
-- null-handling as long as it doesn't coalesce these flags to a boolean.
--
-- L10 (GW-017 outage) and L18 (truncated file) are NOT addressed here --
-- there's no data to recover at this layer. They belong in a completeness
-- report, not a fact table transformation.
--
-- No carrier join. dim_carrier has no linkage from any raw feed (see
-- dim_carrier.sql) -- illustrative question 4's "by carrier" genuinely
-- cannot be answered from this table or any other in this dataset.

CREATE OR REPLACE TABLE marts.fact_cold_chain_reading AS
SELECT
    r.device_id,
    r.telemetry_vendor,
    r.firmware_version,
    r.vehicle_registration,
    r.route_code,
    r.warehouse_code,
    w.warehouse_name,
    w.region_name,
    r.gateway_id,
    r.reading_ts_utc,
    r.temp_value,
    r.temp_unit_resolved,
    r.temp_c,
    (r.temp_c > 8) AS above_band,
    (r.temp_c < 2) AS below_band,
    r.humidity_pct,
    r.door_open_flag,
    r.battery_pct,
    r.gps_lat,
    r.gps_lon,
    r.source_dt,
    r.source_path
FROM staging.reefer_telemetry r
LEFT JOIN marts.dim_warehouse w
    ON r.warehouse_code = w.warehouse_code;
