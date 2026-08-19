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
