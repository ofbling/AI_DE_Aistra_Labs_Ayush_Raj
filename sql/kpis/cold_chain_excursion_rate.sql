-- null temp_c stays out of both sides of the ratio automatically, just
-- don't coalesce above_band to a bool or that stops working
SELECT
    warehouse_name, telemetry_vendor, date_trunc('month', reading_ts_utc) AS month,
    count(*) FILTER (WHERE temp_c IS NOT NULL) AS readings,
    count(*) FILTER (WHERE above_band) AS excursion_readings,
    round(100.0 * count(*) FILTER (WHERE above_band) / count(*) FILTER (WHERE temp_c IS NOT NULL), 2) AS excursion_pct,
    round(100.0 * count(*) FILTER (WHERE below_band) / count(*) FILTER (WHERE temp_c IS NOT NULL), 2) AS below_band_pct
FROM marts.fact_cold_chain_reading
WHERE reading_ts_utc BETWEEN $start_date AND $end_date
GROUP BY warehouse_name, telemetry_vendor, date_trunc('month', reading_ts_utc)
ORDER BY month, warehouse_name, telemetry_vendor;
