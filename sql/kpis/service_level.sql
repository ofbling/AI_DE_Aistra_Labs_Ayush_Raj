-- % of orders that hit DELIVERED on or before the requested date
-- spoiler: this comes back 0.0% no matter what -- see below, not a bug
--
-- traced it: order_status = STATUS[min(step,4)] and step is driven by
-- nu = rng.integers(1,4,n), which in numpy only ever gives 1, 2, or 3.
-- status index can never reach 4 (DELIVERED), for any order, confirmed
-- against the raw feed directly. considered swapping to DISPATCHED so
-- the number would mean something, decided against it -- that answers a
-- different question under the same label. documenting the finding instead.

WITH evaluable AS (
    SELECT *
    FROM clean.orders_current
    WHERE order_date BETWEEN $start_date AND $end_date
      AND requested_delivery_date <= (
          SELECT max(order_date) - INTERVAL 2 DAY FROM clean.orders_current
      )
)
SELECT
    count(*) AS evaluable_orders,
    count(*) FILTER (WHERE order_status = 'DELIVERED'
        AND last_updated_ts::DATE <= requested_delivery_date) AS delivered_on_time,
    count(*) FILTER (WHERE order_status = 'DELIVERED'
        AND last_updated_ts::DATE > requested_delivery_date) AS delivered_late,
    count(*) FILTER (WHERE order_status != 'DELIVERED') AS not_delivered,
    round(100.0 * count(*) FILTER (WHERE order_status = 'DELIVERED'
        AND last_updated_ts::DATE <= requested_delivery_date) / count(*), 2) AS service_level_pct
FROM evaluable;
