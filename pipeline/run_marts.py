"""builds marts.* -- dims + facts. run after run_staging.py and run_clean.py."""
from pathlib import Path
import duckdb

DB_PATH = "warehouse.duckdb"
SQL_FILES = [
    "sql/marts/dim_date.sql",
    "sql/marts/dim_warehouse.sql",
    "sql/marts/dim_carrier.sql",
    "sql/marts/fact_sales.sql",
    "sql/marts/fact_cold_chain_reading.sql",
    "sql/marts/fact_wms_scan_event.sql",
]


def main():
    con = duckdb.connect(DB_PATH)

    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    for table in [
        "marts.dim_date", "marts.dim_warehouse", "marts.dim_carrier",
        "marts.fact_sales", "marts.fact_cold_chain_reading", "marts.fact_wms_scan_event",
    ]:
        n = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n:,} rows")

    # no fact table joins to dim_carrier -- no carrier_id anywhere in the raw feeds
    print("\nNOTE: dim_carrier has nothing to join to -- see DECISIONS.md")

    orphans = con.sql("""
        SELECT
            count(*) FILTER (WHERE channel_master IS NULL) AS outlet_join_misses,
            count(*) FILTER (WHERE category IS NULL) AS product_join_misses,
            count(*) AS total_rows
        FROM marts.fact_sales
    """).df()
    print("\nfact_sales join check:")
    print(orphans.to_string(index=False))

    # confirms it's safe to use dim_product.case_pack instead of
    # uom_conversion.csv (missing ~4% of skus on purpose)
    mismatch = con.sql("""
        SELECT count(*) AS disagreements
        FROM read_csv_auto('data/reference/uom_conversion.csv') u
        JOIN clean.dim_product p ON u.sku_code = p.sku_code AND p.is_current
        WHERE u.eaches_per_case != p.case_pack
    """).fetchone()[0]
    print(f"\nuom_conversion vs dim_product.case_pack disagreements: {mismatch:,}")

    wh_orphans = con.sql("""
        SELECT count(*) FILTER (WHERE warehouse_name IS NULL) AS warehouse_join_misses,
               count(*) AS total_readings
        FROM marts.fact_cold_chain_reading
    """).df()
    print("\nfact_cold_chain_reading warehouse join check:")
    print(wh_orphans.to_string(index=False))

    wms_orphans = con.sql("""
        SELECT count(*) FILTER (WHERE warehouse_name IS NULL) AS warehouse_join_misses,
               count(*) AS total_scans
        FROM marts.fact_wms_scan_event
    """).df()
    print("\nfact_wms_scan_event warehouse join check:")
    print(wms_orphans.to_string(index=False))

    print("\nDeeper investigations (miss breakdown, excursion naive-vs-normalized, "
          "WMS linkage check) moved to scripts/data_quality_investigations.py -- "
          "already-proven findings, not re-run on every build.")


if __name__ == "__main__":
    main()
