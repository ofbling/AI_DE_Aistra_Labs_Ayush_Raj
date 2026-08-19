-- Marts fact: fact_sales
--
-- Grain: one row per pos_transactions line (txn_id, txn_line_no), after
-- Phase 2's dedup. Same grain as staging.pos_transactions -- no aggregation
-- happens here, so this table can still answer "show me the row" for any
-- number derived from it (the CFO's traceability requirement).
--
-- Outlet and product context are joined POINT-IN-TIME against the SCD2
-- dimensions (event_ts falls inside [valid_from, valid_to)), not against
-- is_current. Joining to "current" would reproduce exactly the bug
-- KP-3155 complained about: old sales silently reattributed to today's
-- channel/category if it changed since. This is the whole reason
-- dim_outlet/dim_product were built as history tables in the first place.
--
-- The join uses event_ts_utc, NOT event_ts_ist, deliberately. First pass
-- used event_ts_ist here and it was wrong: dim_outlet/dim_product's
-- valid_from/valid_to come straight from erp_cdc's __op_ts with no offset
-- applied (there's no documented reason CDC timestamps need an IST
-- correction the way POS's did), so comparing an IST-shifted sale time
-- against un-shifted CDC boundaries silently misaligned every version
-- transition by ~5.5 hours. The run_marts.py integrity check caught this
-- as ~19k/~14k non-null misses out of 4M rows -- both sides of a
-- point-in-time comparison just need to share ONE clock; which clock
-- doesn't matter as long as it's the same on both sides. business_date
-- still correctly uses the IST-shifted value -- that fix was never wrong,
-- it just wasn't the right timestamp to reuse for this join.

-- A small fraction of sales still won't find a matching outlet/product
-- version even with that fix -- verified this is NOT a bug. outlet_code/
-- sku_code updates and deletes are assigned independent random days in the
-- generator, so a key can be deleted and later "resurrected" by an update
-- purely by chance (insert -> update -> DELETE on day 300 -> update on day
-- 400). The gap between the delete and the later update is a period where
-- the entity genuinely had no active master record; a sale falling in that
-- window correctly finds nothing. Confirmed via pipeline/run_marts.py:
-- every miss decomposes exactly into deleted-and-never-reinstated (~6.5k
-- outlet-lines, ~7.9k product-lines) or exactly this kind of gap (~12.6k /
-- ~5.6k), with zero left unexplained. Not "fixed" here on purpose --
-- doing so would mean inventing outlet/product attributes for a period the
-- source system itself says didn't have any.

--
-- Both channel_pos (from the till, as captured at point of sale) and
-- channel_master (from the outlet master, at that same point in time) are
-- kept, not collapsed into one column. They're two independent sources and
-- can legitimately disagree (till not yet updated after a reclassification,
-- or vice versa) -- that disagreement is itself worth being able to see,
-- not something to silently pick a winner on.
--
-- qty_eaches: pre-drift rows use uom to decide whether qty needs
-- CS->EA conversion; post-drift rows (uom is NULL -- the column didn't
-- exist after the schema change) are assumed already-eaches, because the
-- renamed column is literally called quantity_units. This is a stated
-- ASSUMPTION, not a confirmed fact -- the vendor release note that would
-- confirm it is the one nobody can find (per 02_Feed_Contracts.md).
--
-- Eaches-per-case comes from dim_product.case_pack, not
-- reference/uom_conversion.csv. Checked, not assumed: both are generated
-- from the same underlying value in generate_dataset.py, so they agree
-- everywhere uom_conversion.csv has a row -- but uom_conversion.csv is
-- missing ~4.2% of SKUs (DEFECT L16) and dim_product isn't. Verified
-- empirically in pipeline/run_marts.py, not just inferred from source.
--
-- All joins are LEFT JOINs on purpose. A POS line with no matching outlet
-- or product version should still show up here, visibly NULL, rather than
-- silently vanish -- run_marts.py counts these as an explicit check.

CREATE OR REPLACE TABLE marts.fact_sales AS
SELECT
    p.txn_id,
    p.txn_line_no,
    p.basket_id,
    p.outlet_code,
    p.sku_code,
    p.business_date,
    p.event_ts_utc,
    p.event_ts_ist,
    p.channel AS channel_pos,
    o.channel AS channel_master,
    o.outlet_format,
    o.city AS outlet_city,
    o.route_code,
    o.warehouse_code,
    pr.category,
    pr.brand,
    pr.is_chilled,
    pr.gst_rate_pct,
    p.qty,
    p.uom,
    CASE WHEN p.uom = 'CS' THEN p.qty * pr.case_pack ELSE p.qty END AS qty_eaches,
    p.unit_price,
    p.discount_amount,
    p.tax_amount,
    p.payment_mode,
    p.promo_code,
    p.source_path
FROM staging.pos_transactions p
LEFT JOIN clean.dim_outlet o
    ON p.outlet_code = o.outlet_code
   AND p.event_ts_utc >= o.valid_from
   AND p.event_ts_utc <  COALESCE(o.valid_to, TIMESTAMP '9999-12-31')
LEFT JOIN clean.dim_product pr
    ON p.sku_code = pr.sku_code
   AND p.event_ts_utc >= pr.valid_from
   AND p.event_ts_utc <  COALESCE(pr.valid_to, TIMESTAMP '9999-12-31');
