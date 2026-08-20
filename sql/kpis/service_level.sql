-- KPI: Service Level (On-Time Order Completion Rate)
--
-- Neither the CFO nor Divya defined "service level" precisely -- Divya
-- named it as one of three things needing a proper definition, without
-- specifying one. Definition used here, the literal/textbook one:
--
--   Percentage of orders that reached DELIVERED status on or before their
--   requested_delivery_date.
--
-- RESULT: 0.0%, for every order, always. This is not a bug and not
-- something to chase further. Traced in the generator: order_status is
-- assigned as STATUS[min(step, 4)] where STATUS = [CREATED, CONFIRMED,
-- PICKED, DISPATCHED, DELIVERED] (indices 0-4), and step is driven by
-- nu = rng.integers(1, 4, n) -- which in numpy only ever produces 1, 2,
-- or 3 (the upper bound is exclusive). step therefore never exceeds 3,
-- and order_status can never reach index 4. DELIVERED is structurally
-- unreachable anywhere in this dataset -- not an operational problem, a
-- property of how the source system's status field was generated.
--
-- This is the finding, not a defect to fix: the honest answer to "what
-- percentage of orders are delivered on time" is that this dataset cannot
-- distinguish "delivered on time" from "delivered late" from "never
-- delivered," because it never reaches delivery at all. Reported as-is
-- rather than silently substituting a different completion status
-- (e.g. DISPATCHED) the business never asked for.

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
                                       AND last_updated_ts::DATE <= requested_delivery_date)
          / count(*), 2) AS service_level_pct
FROM evaluable;
