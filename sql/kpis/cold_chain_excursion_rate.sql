-- KPI: Cold Chain Integrity / Excursion Rate
--
-- "Excursion" = above the 2-8C band only, per the feed contract's literal
-- wording -- not "outside" the band. below_band is exposed separately.
-- Null temp_c (DEFECT L8, sensor dropouts) is correctly excluded from
-- both numerator and denominator by normal SQL null handling; do not
-- coalesce above_band to a boolean before aggregating, or that stops
-- working.
--
-- Grain here is warehouse x month x vendor, matching illustrative
-- question 4's phrasing ("by month and by carrier") as closely as this
-- data allows -- carrier itself is not answerable, see dim_carrier.sql.

SELECT
    warehouse_name,
    telemetry_vendor,
    date_trunc('month', reading_ts_utc) AS month,
    count(*) FILTER (WHERE temp_c IS NOT NULL) AS readings,
    count(*) FILTER (WHERE above_band) AS excursion_readings,
    round(100.0 * count(*) FILTER (WHERE above_band)
          / count(*) FILTER (WHERE temp_c IS NOT NULL), 2) AS excursion_pct,
    round(100.0 * count(*) FILTER (WHERE below_band)
          / count(*) FILTER (WHERE temp_c IS NOT NULL), 2) AS below_band_pct
FROM marts.fact_cold_chain_reading
WHERE reading_ts_utc BETWEEN $start_date AND $end_date
GROUP BY warehouse_name, telemetry_vendor, date_trunc('month', reading_ts_utc)
ORDER BY month, warehouse_name, telemetry_vendor;
