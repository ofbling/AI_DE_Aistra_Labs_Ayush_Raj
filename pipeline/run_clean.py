"""
Phase 3 -- clean layer.

Builds clean.* dimension/fact tables in warehouse.duckdb by replaying CDC
history. Unlike staging, this layer carries real business logic:
point-in-time reconstruction, tie-breaking, delete handling -- not just
typing and dedup.

Run after the staging layer:
    python pipeline/run_staging.py
    python pipeline/run_clean.py
"""
from pathlib import Path

import duckdb

DB_PATH = "warehouse.duckdb"
SQL_FILES = [
    "sql/clean/dim_outlet.sql",
    "sql/clean/dim_product.sql",
    "sql/clean/orders_current.sql",
]


def summarize(con, table, key_col, raw_glob):
    n_versions = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
    n_current = con.sql(f"SELECT count(*) FROM {table} WHERE is_current").fetchone()[0]
    n_raw = con.sql(f"""
        SELECT count(DISTINCT {key_col}) FROM read_parquet('{raw_glob}')
    """).fetchone()[0]
    print(f"{table}: {n_versions:,} historical versions, {n_current:,} currently active "
          f"(raw CDC stream covers {n_raw:,} distinct {key_col} values)")


def main() -> None:
    con = duckdb.connect(DB_PATH)

    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    summarize(con, "clean.dim_outlet", "outlet_code", "data/raw/erp_cdc/outlet_master/*/*.parquet")
    summarize(con, "clean.dim_product", "sku_code", "data/raw/erp_cdc/product_master/*/*.parquet")

    tie_sample = con.sql("""
        SELECT outlet_code, credit_limit, valid_from, valid_to, is_current
        FROM clean.dim_outlet
        WHERE outlet_code IN (
            SELECT outlet_code FROM clean.dim_outlet
            GROUP BY outlet_code HAVING count(*) > 1
        )
        ORDER BY outlet_code, valid_from
        LIMIT 10
    """).df()
    print("\nSample multi-version outlets (spot-check L12/L13 by eye):")
    print(tie_sample.to_string(index=False))

    n_orders = con.sql("SELECT count(*) FROM clean.orders_current").fetchone()[0]
    n_orders_raw = con.sql("""
        SELECT count(DISTINCT order_number)
        FROM read_parquet('data/raw/erp_cdc/sales_order_header/*/*.parquet')
    """).fetchone()[0]
    print(f"\nclean.orders_current: {n_orders:,} active orders "
          f"({n_orders_raw - n_orders:,} order_numbers excluded as tombstoned, "
          f"out of {n_orders_raw:,} distinct order_numbers seen in raw CDC)")

    by_source = con.sql("""
        SELECT source_system,
               count(*) AS orders,
               round(avg(order_value_gross), 0) AS avg_order_value_gross
        FROM clean.orders_current
        GROUP BY source_system
        ORDER BY source_system
    """).df()
    print("\nAverage order value by source system (Q7 -- are these comparable?):")
    print(by_source.to_string(index=False))


if __name__ == "__main__":
    main()
