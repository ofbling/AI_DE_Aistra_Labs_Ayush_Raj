-- "excursion" = above band only per the contract's exact wording, not
-- outside band. tracking below_band separately, not folding it in.
-- no trip concept in the source data so this stays at reading grain

CREATE OR REPLACE TABLE marts.fact_cold_chain_reading AS
SELECT
    r.device_id, r.telemetry_vendor, r.firmware_version, r.vehicle_registration,
    r.route_code, r.warehouse_code, w.warehouse_name, w.region_name, r.gateway_id,
    r.reading_ts_utc, r.temp_value, r.temp_unit_resolved, r.temp_c,
    (r.temp_c > 8) AS above_band, (r.temp_c < 2) AS below_band,
    r.humidity_pct, r.door_open_flag, r.battery_pct, r.gps_lat, r.gps_lon,
    r.source_dt, r.source_path
FROM staging.reefer_telemetry r
LEFT JOIN marts.dim_warehouse w ON r.warehouse_code = w.warehouse_code;