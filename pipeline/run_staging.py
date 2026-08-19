"""
Phase 2 -- staging layer.

Builds staging.* tables in warehouse.duckdb from the raw feeds. Each model
here does schema unification, type/timezone correction, and dedup only --
no joins to reference or master data, no business logic. That belongs in
later layers.

Run after generating and validating the raw dataset:
    python pipeline/run_staging.py
"""
import duckdb

DB_PATH = "warehouse.duckdb"
SQL_FILES = [
    "sql/staging/stg_pos_transactions.sql",
]


def main() -> None:
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")

    for path in SQL_FILES:
        print(f"running {path} ...")
        with open(path, encoding="utf-8") as f:
            con.execute(f.read())

    n = con.sql("SELECT count(*) FROM staging.pos_transactions").fetchone()[0]
    raw_n = con.sql("""
        SELECT count(*) FROM read_parquet(
            'data/raw/pos_transactions/*/*.parquet', union_by_name=true
        )
    """).fetchone()[0]
    print(f"staging.pos_transactions: {n:,} rows "
          f"({raw_n - n:,} exact duplicates dropped from {raw_n:,} raw rows)")


if __name__ == "__main__":
    main()
