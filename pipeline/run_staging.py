"""
Phase 2 -- staging layer.

Builds staging.* tables in warehouse.duckdb from the raw feeds. Each model
here does schema unification, type/timezone correction, and dedup only --
no joins to reference or master data, no business logic. That belongs in
later layers.

Run after generating and validating the raw dataset:
    python pipeline/run_staging.py
"""
from pathlib import Path

import duckdb

DB_PATH = "warehouse.duckdb"
DATA_DIR = Path("data")
RAW = DATA_DIR / "raw"

# DEFECT L18: truncated, unreadable, but still counted in the manifest.
# Every model that scans reefer_telemetry has to exclude it explicitly.
BAD_REEFER_FILE = RAW / "reefer_telemetry" / "dt=2025-07-14" / "part-00000.parquet"

SQL_FILES = [
    "sql/staging/stg_pos_transactions.sql",
    "sql/staging/stg_reefer_telemetry.sql",
]


def reefer_file_list_literal() -> str:
    paths = sorted((RAW / "reefer_telemetry").glob("*/*.parquet"))
    paths = [p for p in paths if p != BAD_REEFER_FILE]
    quoted = ", ".join(f"'{p.as_posix()}'" for p in paths)
    return f"[{quoted}]"


def main() -> None:
    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")

    for path in SQL_FILES:
        print(f"running {path} ...")
        sql = Path(path).read_text(encoding="utf-8")
        sql = sql.replace("{{REEFER_FILES}}", reefer_file_list_literal())
        con.execute(sql)

    n_pos = con.sql("SELECT count(*) FROM staging.pos_transactions").fetchone()[0]
    raw_pos = con.sql("""
        SELECT count(*) FROM read_parquet(
            'data/raw/pos_transactions/*/*.parquet', union_by_name=true
        )
    """).fetchone()[0]
    print(f"staging.pos_transactions:  {n_pos:,} rows "
          f"({raw_pos - n_pos:,} exact duplicates dropped from {raw_pos:,} raw rows)")

    n_tel = con.sql("SELECT count(*) FROM staging.reefer_telemetry").fetchone()[0]
    print(f"staging.reefer_telemetry:  {n_tel:,} rows "
          f"(excludes 1 truncated file -- DEFECT L18)")


if __name__ == "__main__":
    main()
