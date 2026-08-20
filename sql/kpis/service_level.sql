-- KPI: Service Level (On-Time Order Completion Rate)
--
-- Neither the CFO nor Divya defined "service level" precisely -- Divya
-- named it as one of three things needing a proper definition, without
-- specifying one. This is the proposed definition, a judgment call:
--
--   Percentage of orders that reached DELIVERED status on or before their
--   requested_delivery_date.
--
-- Why this definition and not another: "on-time-in-full" (OTIF) is the
-- textbook standard, but "in full" needs a quantity-delivered-vs-quantity-
-- ordered comparison this data doesn't carry -- only line_count exists,
-- with no evidence of partial fulfillment tracking. Carrier SLA hours
-- (carrier_master.sla_hours) would be a natural alternative target, but
-- orders carry no carrier_id or route->carrier mapping -- the same gap as
-- dim_carrier (see dim_carrier.sql), showing up a third time now.
-- requested_delivery_date is what's actually available and is the ERP's
-- own record of the delivery commitment, so it's the defensible target.
--
-- Only orders whose requested_delivery_date has already passed, with a
-- 2-day buffer relative to the most recent order_date in the dataset, are
-- evaluated -- a recent order that hasn't had time to complete yet is not
-- a service failure, it's a data-cutoff artifact.
--
-- orders_current only stores the LATEST record per order, but that's
-- sufficient here: for an order whose current status is DELIVERED,
-- last_updated_ts IS the moment it became delivered (that status is what
-- the latest record set), so no intermediate history is needed for this
-- specific question.

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
