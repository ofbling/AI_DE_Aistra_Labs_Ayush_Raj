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
]


def main() -> None:
    con = duckdb.connect(DB_PATH)

    for path in SQL_FILES:
        print(f"running {path} ...")
        con.execute(Path(path).read_text(encoding="utf-8"))

    n_versions = con.sql("SELECT count(*) FROM clean.dim_outlet").fetchone()[0]
    n_current = con.sql("SELECT count(*) FROM clean.dim_outlet WHERE is_current").fetchone()[0]
    n_outlets_raw = con.sql("""
        SELECT count(DISTINCT outlet_code)
        FROM read_parquet('data/raw/erp_cdc/outlet_master/*/*.parquet')
    """).fetchone()[0]

    print(f"clean.dim_outlet: {n_versions:,} historical versions, "
          f"{n_current:,} currently active outlets "
          f"(raw CDC stream covers {n_outlets_raw:,} distinct outlet_code values)")

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


if __name__ == "__main__":
    main()
