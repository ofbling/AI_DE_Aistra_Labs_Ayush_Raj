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

## Cold Chain Integrity (Excursion Rate)

**Definition.** Percentage of chilled-vehicle temperature readings above
the target band (2-8 degrees Celsius) -- "excursion," per the feed
contract's literal wording ("any reading above the band"). A below-band
reading is tracked separately, not counted as an excursion by this
definition (see fact_cold_chain_reading.sql).

**Grain.** Reading level; aggregated here by warehouse x vendor x month.
No trip/journey grain exists in the source data.

**Filters / exclusions.** Readings with a null temp_value (sensor
dropouts, DEFECT L8, ~0.6% of readings) are excluded from both numerator
and denominator.

**Source.** `marts.fact_cold_chain_reading`.

**Owner.** Supply Chain Operations (Divya Raghavan's team).

**This is the headline finding of the whole engagement.** Measured
directly, not estimated:

| | Naive (raw temp_value, no unit fix) | Normalized (temp_c) |
|---|---|---|
| Overall | 38.29% | **7.19%** |
| COLDEYE only | 100.0% | 7.2% |
| THERMLOG only | 7.2% | 7.2% |

THERMLOG (already Celsius) shows an identical rate either way -- expected,
and itself a sanity check that normalization isn't distorting anything.
COLDEYE (Fahrenheit, DEFECT L6) shows literally 100% naive, because almost
any Fahrenheit reading is numerically far above a Celsius threshold of 8,
regardless of whether the truck is actually running cold and safe. Once
correctly converted, COLDEYE's true rate lands at exactly THERMLOG's rate.

**Conclusion for the business:** the true cold chain excursion rate is
approximately **7%**, not "about a third." COLDEYE devices are exactly
1/3 of the fleet by assignment, and 100% of them misread as excursions
under naive, unit-blind math -- almost certainly the exact origin of the
"~1/3" figure Divya described. This was a units bug in whatever prior
analysis produced that number, not a cold chain operations problem.

**Known limitations.**
- "Excursion" excludes below-band (too cold) readings by the contract's
  literal definition; `below_band` is tracked as a separate signal.
- No carrier breakdown possible -- no linkage exists in any raw feed
  (see dim_carrier.sql).
- No trip/journey grain -- this is a reading-level rate, not "percent of
  trips with an excursion." The source schema has no concept of a trip.
- DEFECT L10 (GW-017 outage) and L18 (one excluded truncated file) both
  reduce reading coverage; neither is corrected here -- see the
  completeness report.

**Query.** `sql/kpis/cold_chain_excursion_rate.sql`

---

## Warehouse Cycle Time (Dock-to-Dispatch)

**Definition -- as asked for.** Illustrative question 5 and Divya's brief
both ask for median dock-to-dispatch cycle time by warehouse: how long,
per job, from a RECEIVE scan to the DISPATCH scan for the same goods.

**This cannot be computed from the data as shipped.** Checked directly: no
field in wms_scan_events links a RECEIVE scan to the DISPATCH scan for the
same physical item. `warehouse_code`, `order_number`, `sku_code`,
`batch_id`, and `pallet_id` are all assigned independently at random per
scan in the generator -- there is no shared "job" identifier anywhere in
this feed. Confirmed empirically too, not just by reading source: matching
a DISPATCH event to a same-pallet RECEIVE at the same warehouse succeeds
at ~3.76% of the time, almost exactly what pure random chance predicts
(~3.8%, worked out from `pallet_id`'s 400,000 possible values) -- nowhere
near the near-100% match rate a real link would produce. This is a genuine
data gap, distinct from DEFECT L11 (missing scans) -- even with zero
missing scans, there would still be no key to stitch on.

**What's offered instead: a coarse, warehouse-level PROXY, not a true
cycle time.** For each warehouse and day, the gap between the typical
(median) time-of-day a RECEIVE happens and the typical time-of-day a
DISPATCH happens, averaged across days. This tracks no single item's
journey -- it is only a rough sense of how spread out handling activity
is across a warehouse's day.

**Grain.** Warehouse (averaged across days in the requested range).

**Filters / exclusions.** Days where a warehouse has zero RECEIVE or zero
DISPATCH events are excluded from the average (can happen from DEFECT L11,
missing scans, on top of the fact that this measure was never going to be
precise regardless).

**Source.** `marts.fact_wms_scan_event`.

**Owner.** Supply Chain Operations (Divya Raghavan's team).

**Known limitations.**
- Not a per-job metric. Treat any number this query returns as a coarse
  operational signal, never as "the average time an order takes to ship."
- The generator assigns each scan's time as a random base time plus a
  fixed +15 minutes per handling stage (RECEIVE=+0 ... DISPATCH=+75min).
  If this proxy lands close to 75 minutes at every warehouse regardless of
  real differences between them, that confirms the number reflects this
  data-generation mechanic rather than genuine warehouse performance --
  worth checking before ever comparing warehouses on this number.
- DEFECT L11 (~6.5% of scan events never emitted) reduces the data this
  proxy is built on, on top of everything above.

**Query.** `sql/kpis/warehouse_cycle_time_proxy.sql`

---

*More entries land here as service level, channel reclassification, order
value comparability, and feed completeness get written up.*
