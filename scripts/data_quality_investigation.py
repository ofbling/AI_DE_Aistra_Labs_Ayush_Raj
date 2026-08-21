"""
one-time proofs behind three findings already written into the pipeline's
comments and the KPI catalogue. not part of the regular build -- these
already did their job. run standalone if you want to re-verify any of them.

    python pipeline/run_marts.py   (must run first, builds the tables)
    python scripts/data_quality_investigations.py
"""
import duckdb

con = duckdb.connect("warehouse.duckdb")


def outlet_product_gap_breakdown():
    print("=== fact_sales miss breakdown: outlet ===")
    outlet = con.sql("""
        WITH misses AS (
            SELECT p.outlet_code, p.event_ts_utc
            FROM staging.pos_transactions p
            LEFT JOIN clean.dim_outlet o
                ON p.outlet_code = o.outlet_code
               AND p.event_ts_utc >= o.valid_from
               AND p.event_ts_utc <  COALESCE(o.valid_to, TIMESTAMP '9999-12-31')
            WHERE o.outlet_code IS NULL
        ),
        bounds AS (
            SELECT outlet_code,
                   min(valid_from) AS first_seen,
                   max(COALESCE(valid_to, TIMESTAMP '9999-12-31')) AS last_seen
            FROM clean.dim_outlet
            GROUP BY outlet_code
        )
        SELECT
            count(*) AS total_misses,
            count(*) FILTER (WHERE b.outlet_code IS NULL) AS outlet_never_in_dim,
            count(*) FILTER (WHERE b.outlet_code IS NOT NULL AND m.event_ts_utc >= b.last_seen) AS sale_after_last_known_version,
            count(*) FILTER (WHERE b.outlet_code IS NOT NULL AND m.event_ts_utc < b.first_seen) AS sale_before_first_version,
            count(*) FILTER (WHERE b.outlet_code IS NOT NULL
                              AND m.event_ts_utc >= b.first_seen
                              AND m.event_ts_utc <  b.last_seen) AS sale_in_gap_between_versions
        FROM misses m
        LEFT JOIN bounds b ON m.outlet_code = b.outlet_code
    """).df()
    print(outlet.to_string(index=False))

    print("\n=== fact_sales miss breakdown: product ===")
    product = con.sql("""
        WITH misses AS (
            SELECT p.sku_code, p.event_ts_utc
            FROM staging.pos_transactions p
            LEFT JOIN clean.dim_product pr
                ON p.sku_code = pr.sku_code
               AND p.event_ts_utc >= pr.valid_from
               AND p.event_ts_utc <  COALESCE(pr.valid_to, TIMESTAMP '9999-12-31')
            WHERE pr.sku_code IS NULL
        ),
        bounds AS (
            SELECT sku_code,
                   min(valid_from) AS first_seen,
                   max(COALESCE(valid_to, TIMESTAMP '9999-12-31')) AS last_seen
            FROM clean.dim_product
            GROUP BY sku_code
        )
        SELECT
            count(*) AS total_misses,
            count(*) FILTER (WHERE b.sku_code IS NULL) AS sku_never_in_dim,
            count(*) FILTER (WHERE b.sku_code IS NOT NULL AND m.event_ts_utc >= b.last_seen) AS sale_after_last_known_version,
            count(*) FILTER (WHERE b.sku_code IS NOT NULL AND m.event_ts_utc < b.first_seen) AS sale_before_first_version,
            count(*) FILTER (WHERE b.sku_code IS NOT NULL
                              AND m.event_ts_utc >= b.first_seen
                              AND m.event_ts_utc <  b.last_seen) AS sale_in_gap_between_versions
        FROM misses m
        LEFT JOIN bounds b ON m.sku_code = b.sku_code
    """).df()
    print(product.to_string(index=False))
    print("\nfinding: gap = resurrection pattern (deleted, then an unrelated "
          "later update). documented in fact_sales.sql. not a bug.")


def cold_chain_naive_vs_normalized():
    print("\n=== excursion rate: naive vs normalized ===")
    overall = con.sql("""
        SELECT
            round(100.0 * count(*) FILTER (WHERE temp_value > 8 AND temp_value IS NOT NULL)
                  / count(*) FILTER (WHERE temp_value IS NOT NULL), 2) AS naive_pct,
            round(100.0 * count(*) FILTER (WHERE above_band)
                  / count(*) FILTER (WHERE temp_c IS NOT NULL), 2) AS normalized_pct
        FROM marts.fact_cold_chain_reading
    """).df()
    print(overall.to_string(index=False))

    by_vendor = con.sql("""
        SELECT telemetry_vendor,
               count(*) AS readings,
               round(100.0 * count(*) FILTER (WHERE temp_value > 8) / count(*), 1) AS naive_pct,
               round(100.0 * count(*) FILTER (WHERE above_band) / count(*), 1) AS normalized_pct
        FROM marts.fact_cold_chain_reading
        WHERE temp_c IS NOT NULL
        GROUP BY telemetry_vendor
        ORDER BY telemetry_vendor
    """).df()
    print(by_vendor.to_string(index=False))
    print("\nfinding: coldeye (fahrenheit) is ~100% naive, 7.2% normalized -- "
          "this is where divya's '~1/3 excursion rate' came from. documented "
          "in the KPI catalogue under Cold Chain Integrity.")


def wms_linkage_check():
    print("\n=== DISPATCH-to-RECEIVE pallet_id coincidence check ===")
    result = con.sql("""
        SELECT
            count(*) AS dispatch_events,
            count(*) FILTER (
                WHERE EXISTS (
                    SELECT 1 FROM marts.fact_wms_scan_event r
                    WHERE r.event_type = 'RECEIVE'
                      AND r.warehouse_code = d.warehouse_code
                      AND r.pallet_id = d.pallet_id
                      AND r.event_ts_ist < d.event_ts_ist
                )
            ) AS dispatch_with_prior_same_pallet_receive
        FROM marts.fact_wms_scan_event d
        WHERE d.event_type = 'DISPATCH'
    """).df()
    print(result.to_string(index=False))
    print("\nfinding: ~3.76% match rate, in line with pure chance (~3.8% "
          "expected given pallet_id's 400,000 possible values) -- confirms "
          "no real stitching key exists. documented in fact_wms_scan_event.sql.")


if __name__ == "__main__":
    outlet_product_gap_breakdown()
    cold_chain_naive_vs_normalized()
    wms_linkage_check()
