-- sales joined to outlet/product AS OF the sale time, not current state
-- (that's the whole point of dim_outlet/dim_product being history tables)
-- uses event_ts_utc on both sides of the join, not event_ts_ist -- the
-- cdc timestamps aren't shifted, so the join needs to match that
--
-- a small % of sales still won't match even so -- checked, not a bug.
-- outlet/product updates and deletes land on independent random days in
-- the source, so a key can get deleted then "resurrected" by an unrelated
-- later update, leaving a real gap where no version was active. confirmed
-- by pulling one outlet's raw history directly and seeing i/u/d/u/u

CREATE OR REPLACE TABLE marts.fact_sales AS
SELECT
    p.txn_id, p.txn_line_no, p.basket_id,
    p.outlet_code, p.sku_code, p.business_date,
    p.event_ts_utc, p.event_ts_ist,
    p.channel AS channel_pos, o.channel AS channel_master,
    o.outlet_format, o.city AS outlet_city, o.route_code, o.warehouse_code,
    pr.category, pr.brand, pr.is_chilled, pr.gst_rate_pct,
    p.qty, p.uom,
    CASE WHEN p.uom = 'CS' THEN p.qty * pr.case_pack ELSE p.qty END AS qty_eaches,
    p.unit_price, p.discount_amount, p.tax_amount,
    p.payment_mode, p.promo_code, p.source_path
FROM staging.pos_transactions p
LEFT JOIN clean.dim_outlet o
    ON p.outlet_code = o.outlet_code
    AND p.event_ts_utc >= o.valid_from
    AND p.event_ts_utc <  COALESCE(o.valid_to, TIMESTAMP '9999-12-31')
LEFT JOIN clean.dim_product pr
    ON p.sku_code = pr.sku_code
    AND p.event_ts_utc >= pr.valid_from
    AND p.event_ts_utc <  COALESCE(pr.valid_to, TIMESTAMP '9999-12-31');