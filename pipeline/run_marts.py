"""
Phase 4 -- marts layer.

Loads reference dimensions (dim_date, dim_warehouse, dim_carrier) and the
fact tables. Reads from staging.*/clean.* and data/reference/ only -- never
from data/raw/ directly, except for the reference CSVs which have no
staged/cleaned equivalent.

Run after staging and clean:
    python pipeline/run_staging.py
    python pipeline/run_clean.py
    python pipeline/run_marts.py
"""
from pathlib import Path

import duckdb

DB_PATH = "warehouse.duckdb"
SQL_FILES = [
    "sql/marts/dim_date.sql",
    "sql/marts/dim_warehouse.sql",
    "sql/marts/dim_carrier.sql",
    "sql/marts/fact_sales.sql",
]


def main() -> None:
    con = duckdb.connect(DB_PATH)

    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    for table in ["marts.dim_date", "marts.dim_warehouse", "marts.dim_carrier", "marts.fact_sales"]:
        n = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n:,} rows")

    print(
        "\nNOTE: dim_carrier has no fact table joining to it yet, and none of "
        "the raw feeds carry a carrier_id or a route_code -> carrier mapping. "
        "Illustrative question 4 ('by carrier') cannot be answered from this "
        "dataset as given -- see DECISIONS.md."
    )

    orphans = con.sql("""
        SELECT
            count(*) FILTER (WHERE channel_master IS NULL) AS outlet_join_misses,
            count(*) FILTER (WHERE category IS NULL) AS product_join_misses,
            count(*) AS total_rows
        FROM marts.fact_sales
    """).df()
    print("\nfact_sales referential integrity check (point-in-time joins):")
    print(orphans.to_string(index=False))

    outlet_breakdown = con.sql("""
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
    print("\noutlet_join_misses breakdown (why each one is unmatched):")
    print(outlet_breakdown.to_string(index=False))

    product_breakdown = con.sql("""
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
    print("\nproduct_join_misses breakdown (why each one is unmatched):")
    print(product_breakdown.to_string(index=False))

    mismatch = con.sql("""
        SELECT count(*) AS disagreements
        FROM read_csv_auto('data/reference/uom_conversion.csv') u
        JOIN clean.dim_product p ON u.sku_code = p.sku_code AND p.is_current
        WHERE u.eaches_per_case != p.case_pack
    """).fetchone()[0]
    print(f"\nuom_conversion.csv vs dim_product.case_pack disagreements: {mismatch:,} "
          f"(0 confirms it's safe to source eaches-per-case from dim_product, "
          f"which has no L16 gaps)")


if __name__ == "__main__":
    main()
