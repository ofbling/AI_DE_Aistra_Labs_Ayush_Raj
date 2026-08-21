"""builds clean.* -- point-in-time replay, real business logic lives here."""
from pathlib import Path
import duckdb

DB_PATH = "warehouse.duckdb"
SQL_FILES = [
    "sql/clean/dim_outlet.sql",
    "sql/clean/dim_product.sql",
    "sql/clean/orders_current.sql",
]


def summarize(con, table, key_col, raw_glob):
    n = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
    cur = con.sql(f"SELECT count(*) FROM {table} WHERE is_current").fetchone()[0]
    raw_n = con.sql(f"SELECT count(DISTINCT {key_col}) FROM read_parquet('{raw_glob}')").fetchone()[0]
    print(f"{table}: {n:,} versions, {cur:,} active, {raw_n:,} distinct {key_col}")


def main():
    con = duckdb.connect(DB_PATH)
    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    summarize(con, "clean.dim_outlet", "outlet_code", "data/raw/erp_cdc/outlet_master/*/*.parquet")
    summarize(con, "clean.dim_product", "sku_code", "data/raw/erp_cdc/product_master/*/*.parquet")

    n_orders = con.sql("SELECT count(*) FROM clean.orders_current").fetchone()[0]
    print(f"orders_current: {n_orders:,} active orders")


if __name__ == "__main__":
    main()
