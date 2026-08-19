"""
Phase 4 -- marts layer.

Loads reference dimensions (dim_date, dim_warehouse, dim_carrier) and will
grow to hold the fact tables next. Reads from staging.*/clean.* and
data/reference/ only -- never from data/raw/ directly, except for these
reference CSVs which have no raw-feed equivalent.

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
]


def main() -> None:
    con = duckdb.connect(DB_PATH)

    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    for table in ["marts.dim_date", "marts.dim_warehouse", "marts.dim_carrier"]:
        n = con.sql(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"{table}: {n:,} rows")

    print(
        "\nNOTE: dim_carrier has no fact table joining to it yet, and none of "
        "the raw feeds carry a carrier_id or a route_code -> carrier mapping. "
        "Illustrative question 4 ('by carrier') cannot be answered from this "
        "dataset as given -- see DECISIONS.md."
    )


if __name__ == "__main__":
    main()
