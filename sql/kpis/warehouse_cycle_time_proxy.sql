-- NOT a real per-job cycle time, see fact_wms_scan_event.sql for why
-- that's not possible. this is just median(dispatch time) minus
-- median(receive time) per warehouse per day, averaged
--
-- comes back 71-81 min at every warehouse, right around the 75 min the
-- generator's fixed per-stage time offset predicts -- this measures the
-- data generator, not real warehouse performance, don't rank on it

WITH daily AS (
    SELECT warehouse_name, event_date,
        median(event_ts_ist) FILTER (WHERE event_type = 'RECEIVE') AS med_receive,
        median(event_ts_ist) FILTER (WHERE event_type = 'DISPATCH') AS med_dispatch
    FROM marts.fact_wms_scan_event
    WHERE event_date BETWEEN $start_date AND $end_date
    GROUP BY warehouse_name, event_date
    HAVING med_receive IS NOT NULL AND med_dispatch IS NOT NULL
)
SELECT warehouse_name, count(*) AS days,
    round(avg(date_diff('minute', med_receive, med_dispatch)), 1) AS avg_gap_minutes
FROM daily
GROUP BY warehouse_name
ORDER BY warehouse_name;
