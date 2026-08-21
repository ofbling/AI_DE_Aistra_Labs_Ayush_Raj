-- Staging model: reefer_telemetry
--
-- {{REEFER_FILES}} is substituted by pipeline/run_staging.py with an
-- explicit file list that excludes dt=2025-07-14/part-00000.parquet
-- (DEFECT L18: truncated, unreadable, but still counted in the manifest).
-- A WHERE clause can't route around a corrupt file -- the scan fails before
-- any filter runs -- so the exclusion has to happen at the file-list level.

-- handled:
-- fixes the clock skew + F/C split (COLDEYE reports Fahrenheit, THERMLOG reports Celsius), drops dupes. no natural key on this
-- feed so dedup is on the full row

--not handled:
-- null temp_value (sensor dropouts) is preserved as NULL, not imputed. 
--Excluding nulls from an excursion-rate denominator is a KPI-query decision, not a staging one.
-- the GW-017 outage is a real hole in the source, not something a transformation can fix. 
--Belongs in a completeness/freshness check.

CREATE OR REPLACE TABLE staging.reefer_telemetry AS
WITH raw AS (
    SELECT *, filename AS source_path
    FROM read_parquet({{REEFER_FILES}}, hive_partitioning = true, filename = true)
),
typed AS (
    SELECT device_id, telemetry_vendor, firmware_version, vehicle_registration,
        route_code, warehouse_code, gateway_id,
        reading_ts::TIMESTAMP
            - CASE WHEN firmware_version = '2.1.4' THEN INTERVAL 7 HOUR ELSE INTERVAL 0 HOUR END AS reading_ts_utc,
        COALESCE(temp_unit, CASE WHEN telemetry_vendor = 'COLDEYE' THEN 'F' ELSE 'C' END) AS temp_unit_resolved,
        temp_value, humidity_pct, door_open_flag, battery_pct, gps_lat, gps_lon,
        dt AS source_dt, source_path
    FROM raw
),
normalized AS (
    SELECT *, CASE WHEN temp_unit_resolved = 'F' THEN (temp_value - 32) * 5.0 / 9.0 ELSE temp_value END AS temp_c
    FROM typed
)
SELECT DISTINCT * FROM normalized;