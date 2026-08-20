# KPI Catalogue

Kestrel Provisions — Analytical Foundation. Every metric defined here has a
runnable query in `sql/kpis/`, using the same name.

Status: work in progress -- built incrementally alongside the pipeline, in
the order the underlying fact tables became available. See DECISIONS.md
for what's deliberately not covered yet.

---

## Gross Sales

**Definition.** Total value of goods sold, before any discount or tax
deduction: `unit_price x qty`, summed. The standard "top line" retail sales
figure.

**Grain.** Channel x business date (the true IST calendar day of sale, not
the date the POS file happened to land -- see `staging/stg_pos_transactions.sql`).

**Filters / exclusions.** None by default. Exact duplicate POS rows are
already removed upstream in staging (DEFECT L3).

**Source.** `marts.fact_sales`, itself built from `pos_transactions` (raw)
via `staging.pos_transactions` and `clean.dim_outlet`.

**Owner.** Finance.

**Known limitations.**
- Uses raw `qty`, not `qty_eaches`. Checked against the generator: `unit_price`,
  `qty`, `discount_amount`, and `tax_amount` are all computed from each other as
  one internally consistent group in the source data -- case-vs-each packaging
  plays no part in that math. Using `qty_eaches` here would overstate revenue
  on case-sold lines (~19% of pre-drift rows) by up to the case pack size, and
  would stop reconciling against `discount_amount`/`tax_amount` on those same
  rows. Verified empirically -- see `scripts/verify_gross_sales_formula.py`.
- Reports `channel_master` (the point-in-time ERP outlet channel), not
  `channel_pos` (what the till captured). The two can disagree; `channel_pos`
  is preserved in `fact_sales` for diagnosing that disagreement, which is a
  separate question from "what were gross sales."
- Does not reconcile to `legacy_finance_weekly_report.csv` -- see the
  reconciliation report for why an exact match isn't achievable from this data.

**Query.** `sql/kpis/gross_sales_by_channel.sql`

---

## Units Sold (Eaches)

**Definition.** Total quantity sold, converted to individual retail units
("eaches") regardless of whether the original sale was recorded by the case
or the each.

**Grain.** Business date (illustrative question 3 asks for a single total;
add `channel`/`category` to the `GROUP BY` for a breakdown).

**Filters / exclusions.** None by default.

**Source.** `marts.fact_sales`.

**Owner.** Commercial / Sales Operations.

**Known limitations.**
- For POS rows recorded after the 2025-10-01 schema drift, `uom` no longer
  exists as a field (dropped in the drift), so these rows are *assumed*
  already-eaches, on the strength of the renamed column being called
  `quantity_units`. This is a stated assumption, not a confirmed fact -- the
  vendor release note that would confirm it is the one nobody can find.
- Case-to-eaches conversion uses `dim_product.case_pack`, not
  `reference/uom_conversion.csv` (which is missing ~4.2% of SKUs by design --
  DEFECT L16). Verified the two sources agree everywhere they overlap
  (see `fact_sales.sql`).

**Query.** `sql/kpis/units_sold_eaches.sql`

---

## Basket Count

**Definition.** Number of distinct shopping baskets (`basket_id` -- "groups
lines into one shopper transaction" per the feed contract) -- i.e., shopping
trips, not receipt lines and not units.

**Grain.** Channel x business date.

**Filters / exclusions.** None by default.

**Source.** `marts.fact_sales`.

**Owner.** Commercial / Sales Operations.

**Known limitations.** None identified yet beyond the general POS caveats
already covered under Gross Sales (late arrival, duplicates, timezone --
all already handled upstream in staging).

**Query.** `sql/kpis/basket_count.sql`

---

*More entries land here as the remaining fact tables (cold chain, WMS
cycle time) get their numbers confirmed, plus service level, channel
reclassification, and feed completeness.*
