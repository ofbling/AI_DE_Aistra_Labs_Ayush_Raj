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
- CONFIRMED, not just predicted: this proxy lands between 71.1 and 81.4
  minutes at all 8 warehouses (average ~76.3 minutes), tightly clustered
  around the 75-minute value implied by the generator's fixed +15
  minutes-per-stage time offset (RECEIVE=+0 ... DISPATCH=+75min). The
  warehouse-to-warehouse spread here is sampling noise, not a real
  operational difference -- this proxy reflects how the data was
  generated, not genuine warehouse performance. Do not rank or compare
  warehouses on this number.
- DEFECT L11 (~6.5% of scan events never emitted) reduces the data this
  proxy is built on, on top of everything above.

**Query.** `sql/kpis/warehouse_cycle_time_proxy.sql`x

---

## Channel Reclassification History

**Definition.** Every instance where an outlet's channel (GT/MT/HORECA/ECOM)
changed from one value to a different value, with the date it happened and
what it changed from/to. Directly answers illustrative question 6.

**Grain.** One row per reclassification event (not per outlet, not per
day -- an outlet that changed channel three times produces three rows).

**Filters / exclusions.** An outlet's very first recorded version is never
counted as a reclassification -- there's no "before" state to compare
against, it's an initial assignment.

**Source.** `clean.dim_outlet` -- this metric only exists because that
table was built as full SCD2 history (see `dim_outlet.sql`), not a
current-state lookup. A simpler "latest wins" outlet table could not
answer this question at all.

**Owner.** Commercial / Sales Operations (channel strategy).

**Known limitations.**
- This tracks the ERP master's channel (what `dim_outlet` represents), not
  the till's channel (`channel_pos`, visible in `fact_sales`) -- the two
  can disagree at the point of an actual sale; this KPI is about the
  authoritative record, not point-of-sale capture.
- Correctness note for anyone editing this query: the date-range filter
  must be applied AFTER the `LAG()` comparison runs over full history, not
  folded into the same `WHERE` clause -- see the SQL comment for why
  getting this wrong silently corrupts results at the boundary of
  whatever range is requested.

**Query.** `sql/kpis/channel_reclassification_history.sql`

---

## Order Value by Source System

**Definition.** Total and average order value (`order_value_gross`),
broken down by which system the order originated from (`SFA_MOBILE`,
`ERP_WEB`, `PARTNER_API`). Directly answers illustrative question 7.

**Grain.** Source system (aggregated across the requested date range).

**Filters / exclusions.** Uses current-state order value per
`orders_current` -- tombstoned (deleted) orders are excluded (DEFECT L15).

**Source.** `clean.orders_current`.

**Owner.** Finance.

**Are the three sources comparable? No.** Confirmed directly:

| Source | Orders | Avg order value (INR) |
|---|---|---|
| SFA_MOBILE | 190,371 | 240,653 |
| ERP_WEB | 94,942 | 241,384 |
| PARTNER_API | 31,807 | **262,143** |

`SFA_MOBILE` and `ERP_WEB` agree closely (within 0.3% of each other).
`PARTNER_API` runs about 8.8% higher -- consistent with the known ~8.5%
freight double-count (DEFECT L14, an open Finance ticket never closed
out). This is not real order-size variation; it's the defect.

**Known limitations.**
- `PARTNER_API` values are reported as-is, not adjusted -- see
  `orders_current.sql` for why silently correcting a Finance-owned number
  isn't this pipeline's call to make. `partner_api_freight_flag` in
  `orders_current` makes affected orders queryable if exclusion is wanted.
- `source_system` can, in principle, differ across an order's own update
  history in this data (see `orders_current.sql`) -- this reports whatever
  the latest known record says, same as every other column there.

**Query.** `sql/kpis/order_value_by_source_system.sql`

---

## Service Level

**Definition attempted.** Divya asked for "service level" to be properly
defined but did not specify a definition. The literal, textbook version --
percentage of orders reaching DELIVERED status on or before their
requested_delivery_date -- was implemented first.

**Finding: this cannot be measured from the data as shipped.**
`DELIVERED` never occurs anywhere in this dataset. Traced to the
generator: order status is driven by `nu = rng.integers(1, 4, n)`, which
in numpy only ever produces 1, 2, or 3 -- never enough to advance the
status index far enough to reach `DELIVERED`. `DISPATCHED` is the highest
status any order in this dataset ever reaches, for any order, at any
point in its lifecycle.

**Grain.** N/A -- the metric returns 0.0% unconditionally regardless of
grain, date range, or any real operational change.

**Source.** `clean.orders_current`.

**Owner.** Supply Chain Operations (Divya Raghavan's team) -- and worth
raising with whoever owns the order-status field in the source ERP, since
a status value that's defined but never populated is itself worth their
attention, independent of this pipeline.

**Known limitations.**
- Reported as measured, not adjusted. A `DISPATCHED`-based proxy
  definition was considered and deliberately not substituted here --
  that would be answering a different question than the one asked, and
  presenting it as "service level" without saying so would misrepresent
  what was actually measured. If leadership wants a workable proxy metric
  instead, that's a follow-up decision for them to make explicitly.

**Query.** `sql/kpis/service_level.sql`

---

## Feed Completeness

**Definition.** Which partitions, in any feed, are missing or don't match
what the ingestion job itself recorded -- directly answers illustrative
question 8: "which days are missing data, and how would we know without
being told."

**Grain.** Partition level for the 3 manifested feeds; gateway-day level
for the reefer_telemetry gap check; partition-presence only for the 3
erp_cdc feeds, which have no manifest to check against at all.

**Source.** All 6 raw feeds directly, plus `_manifest/expected_partitions.csv`.

**Owner.** Data Engineering / whoever owns the ingestion job.

**What it checks, and why one check isn't enough:**
1. Per-partition row counts vs the manifest -- catches a partition that's
   present and counted in the manifest but is actually broken (DEFECT L18:
   one reefer_telemetry file is truncated to 72% of its bytes after the
   manifest was written; the manifest still claims the original count).
2. Gateway-level day gaps within reefer_telemetry, found generically --
   for every gateway, is there a day inside its normal active range with
   zero readings? Not hardcoded to any specific gateway or date -- this is
   what actually surfaces DEFECT L10 (the GW-017 outage) without already
   knowing to look for it.
3. Partition presence for the three `erp_cdc/*` feeds, which have **no
   manifest at all** -- `expected_partitions.csv` only ever covers
   `pos_transactions`, `reefer_telemetry`, and `wms_scan_events`. Nothing
   in this dataset checks ERP completeness at the ingestion-job level;
   this is the closest thing that exists.

**Known limitations.**
- The erp_cdc check can only confirm a partition folder exists, not that
  its row count is right -- there's no baseline to compare against.
- Row-count matching (check 1) can't catch a partition missing entirely
  with zero rows recorded anywhere, including the manifest -- if the
  ingestion job itself never ran and never wrote a manifest row, this
  check has nothing to compare against either. It only catches drift
  between what the manifest says and what's actually on disk.

**Query.** `scripts/feed_completeness_report.py`

---


*More entries land here as feed completeness gets written up.*